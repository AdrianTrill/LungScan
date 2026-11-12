/**
 * Turns the network's raw output into a read, as backend/app/services/analysis.py does:
 * the same thresholds, the same order of operations, and rounding half up, so that the
 * browser and the server give the same read for the same output. A test checks every
 * sample slice against the server's read (src/tests/interpret.test.ts).
 */
import { percent, probability, roundHalfUp } from "../format";
import { CANCER, LABEL_NAMES, LABELS } from "../labels";
import type { AnalyzeResult, Label, Region } from "../types";
import { CROP_OFFSET, CROP_SIZE, RESIZED_SIZE } from "./preprocess";

export const GRID = 7;
const CELL = CROP_SIZE / GRID;
const FLAG_THRESHOLD = 0.5;
const REGION_THRESHOLD = 0.5;
const MAX_REGIONS = 3;

export interface RawOutput {
  logits: ArrayLike<number>;
  cam: ArrayLike<number>;
  width: number;
  height: number;
  inferenceMs: number;
}

export function softmax(logits: ArrayLike<number>): number[] {
  const z = Array.from(logits);
  const top = Math.max(...z);
  const e = z.map((v) => Math.exp(v - top));
  const total = e.reduce((sum, v) => sum + v, 0);
  return e.map((v) => v / total);
}

/** Index of the largest value; ties go to the first. */
function argmax(values: number[], indices: readonly number[]): number {
  let best = indices[0];
  for (const i of indices) if (values[i] > values[best]) best = i;
  return best;
}

export function position(gx: number, gy: number): string {
  const rows = ["upper", "middle", "lower"];
  const cols = ["left", "center", "right"];
  const row = rows[Math.min(2, Math.floor((gy * 3) / GRID))];
  const col = cols[Math.min(2, Math.floor((gx * 3) / GRID))];
  return row === "middle" && col === "center" ? "center" : `${row} ${col}`;
}

/** Group grid cells with at least half the peak evidence into 8-connected regions. */
export function findRegions(
  rel: number[][],
  cancer: number,
  width: number,
  height: number
): Region[] {
  const seen = rel.map((row) => row.map(() => false));
  const components: [number, number][][] = [];
  for (let i = 0; i < GRID; i++) {
    for (let j = 0; j < GRID; j++) {
      if (seen[i][j] || rel[i][j] < REGION_THRESHOLD) continue;
      seen[i][j] = true;
      const stack: [number, number][] = [[i, j]];
      const cells: [number, number][] = [];
      while (stack.length) {
        const [a, b] = stack.pop()!;
        cells.push([a, b]);
        for (const da of [-1, 0, 1]) {
          for (const db of [-1, 0, 1]) {
            const na = a + da;
            const nb = b + db;
            if (na >= 0 && na < GRID && nb >= 0 && nb < GRID && !seen[na][nb]) {
              if (rel[na][nb] >= REGION_THRESHOLD) {
                seen[na][nb] = true;
                stack.push([na, nb]);
              }
            }
          }
        }
      }
      components.push(cells.sort((p, q) => p[0] - q[0] || p[1] - q[1]));
    }
  }

  const found = components.map((cells) => {
    let weight = 0;
    let sx = 0;
    let sy = 0;
    let peak = 0;
    for (const [a, b] of cells) {
      const w = rel[a][b];
      weight += w;
      sx += w * (b + 0.5);
      sy += w * (a + 0.5);
      peak = Math.max(peak, w);
    }
    return { peak, count: cells.length, gx: sx / weight, gy: sy / weight };
  });
  found.sort((p, q) => q.peak - p.peak || q.count - p.count || p.gy - q.gy || p.gx - q.gx);

  const sxScale = width / RESIZED_SIZE;
  const syScale = height / RESIZED_SIZE;
  return found.slice(0, MAX_REGIONS).map(({ peak, count, gx, gy }, k) => {
    const radiusCells = Math.sqrt(count / Math.PI);
    return {
      id: `r${k + 1}`,
      x: roundHalfUp((CROP_OFFSET + gx * CELL) * sxScale),
      y: roundHalfUp((CROP_OFFSET + gy * CELL) * syScale),
      radius: roundHalfUp(radiusCells * CELL * Math.sqrt(sxScale * syScale)),
      evidence: roundHalfUp(peak * cancer, 4),
      cells: count,
      explanation:
        `Grad-CAM evidence for cancer peaks here at ${percent(peak)} of the slice's ` +
        `maximum, over ${count} of ${GRID * GRID} grid cells, in the ` +
        `${position(gx, gy)} of the image.`,
    };
  });
}

export function summarize(
  cancer: number,
  flagged: boolean,
  subtype: Label | null,
  share: number,
  regions: number
): string {
  if (!flagged || !subtype) {
    return `Cancer probability ${probability(cancer)}: the model reads this slice as normal.`;
  }
  const plural = regions === 1 ? "" : "s";
  return (
    `Cancer probability ${probability(cancer)}: the model reads this slice as cancer. ` +
    `Most likely subtype: ${LABEL_NAMES[subtype]} (${probability(share)} of the cancer ` +
    "probability), though the model's subtype calls are unreliable. " +
    `Grad-CAM marks ${regions} region${plural} that raised the cancer score.`
  );
}

export function interpret(
  raw: RawOutput,
  caseId: string,
  source: string,
  runtime: string,
  analyzedAt = new Date()
): AnalyzeResult {
  const p = softmax(raw.logits);
  const cancer = p[CANCER[0]] + p[CANCER[1]] + p[CANCER[2]];
  const flagged = cancer >= FLAG_THRESHOLD;
  const predicted = LABELS[argmax(p, [0, 1, 2, 3])];
  const best = argmax(p, CANCER);
  const subtype = flagged ? LABELS[best] : null;
  const share = cancer > 0 ? p[best] / cancer : 0;

  const cam: number[][] = [];
  for (let i = 0; i < GRID; i++) {
    cam.push(Array.from({ length: GRID }, (_, j) => raw.cam[i * GRID + j]));
  }
  const peak = Math.max(...cam.map((row) => Math.max(...row)));
  const rel = cam.map((row) => row.map((v) => (peak > 0 ? v / peak : 0)));
  const regions = flagged && peak > 0 ? findRegions(rel, cancer, raw.width, raw.height) : [];

  const sx = raw.width / RESIZED_SIZE;
  const sy = raw.height / RESIZED_SIZE;
  const probabilities = Object.fromEntries(
    LABELS.map((label, i) => [label, roundHalfUp(p[i], 6)])
  ) as Record<Label, number>;
  return {
    case_id: caseId,
    cancer_probability: roundHalfUp(cancer, 6),
    flagged,
    predicted_class: predicted,
    subtype,
    probabilities,
    heatmap: {
      size: GRID,
      values: rel.flat().map((v) => roundHalfUp(v * cancer, 4)),
      box: {
        x: roundHalfUp(CROP_OFFSET * sx, 2),
        y: roundHalfUp(CROP_OFFSET * sy, 2),
        width: roundHalfUp(CROP_SIZE * sx, 2),
        height: roundHalfUp(CROP_SIZE * sy, 2),
      },
    },
    regions,
    summary: summarize(cancer, flagged, subtype, share, regions.length),
    model: { name: "ResNet-50 lung CT classifier", source, runtime },
    inference_ms: roundHalfUp(raw.inferenceMs, 1),
    analyzed_at: analyzedAt.toISOString(),
  };
}
