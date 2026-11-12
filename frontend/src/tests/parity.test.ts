/**
 * @jest-environment node
 *
 * The browser runtime reimplements parts of the server. These tests hold it to the
 * server's own output: fixtures written by backend/tools/make_fixtures.py, and the
 * sample reads written by backend/tools/make_samples.py.
 */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { displayFilename } from "@/lib/api/browser";
import { interpret } from "@/lib/inference/interpret";
import { resized, toInput } from "@/lib/inference/preprocess";
import { resizeBilinear } from "@/lib/inference/resample";
import { generateTextReport } from "@/lib/report";
import type { AnalyzeResult, CaseDetail, Label, Patient } from "@/lib/types";

const fixtures = join(__dirname, "fixtures");
const read = (path: string) => readFileSync(path, "utf8");
const samples = JSON.parse(
  read(join(__dirname, "..", "..", "..", "model", "samples", "samples.json"))
);
const decode = (b64: string) => new Uint8Array(Buffer.from(b64, "base64"));

describe("preprocessing", () => {
  const fixture = JSON.parse(read(join(fixtures, "resample.json")));
  const input = decode(fixture.input);
  const image = { rgb: input, width: fixture.width, height: fixture.height };

  const sizes: { width: number; height: number; pixels: string }[] = fixture.resized;
  it.each(sizes)(
    "resizes to $width x $height exactly as Pillow does",
    ({ width, height, pixels }) => {
      const ours = resizeBilinear(input, fixture.width, fixture.height, width, height);
      expect(Buffer.from(ours).equals(Buffer.from(decode(pixels)))).toBe(true);
    }
  );

  it("makes the same 256x256 image as the server", () => {
    expect(createHash("sha256").update(resized(image)).digest("hex")).toBe(fixture.pipeline_sha256);
  });

  it("makes the same network input as NumPy", () => {
    const x = toInput(image);
    expect(Array.from(x.slice(0, 6))).toEqual(fixture.tensor.first);
    expect(Array.from(x.slice(-6))).toEqual(fixture.tensor.last);
    expect(x.reduce((sum, v) => sum + v, 0)).toBeCloseTo(fixture.tensor.sum, 6);
  });
});

interface Sample {
  id: string;
  raw: { logits: number[]; cam: number[]; width: number; height: number };
  result: AnalyzeResult;
}

describe("interpretation", () => {
  const cases: Sample[] = samples.cases;
  it.each(cases)("reads $id exactly as the server does", (sample) => {
    const want = sample.result;
    const got = interpret(
      { ...sample.raw, inferenceMs: want.inference_ms },
      sample.id,
      want.model.source,
      want.model.runtime,
      new Date(want.analyzed_at)
    );
    const { analyzed_at: gotTime, ...ours } = got;
    const { analyzed_at: wantTime, ...theirs } = { ...want, case_id: sample.id };
    expect(ours).toEqual(theirs);
    expect(new Date(gotTime).getTime()).toBe(new Date(wantTime).getTime());
  });
});

describe("the report", () => {
  it("matches the server's, character for character", () => {
    const inputs = JSON.parse(read(join(fixtures, "report.json")));
    const sample = samples.cases.find((c: { id: string }) => c.id === inputs.case_id);
    const person = samples.patients.find((p: Patient) => p.id === sample.patient_id);
    const detail: CaseDetail = {
      case: {
        id: sample.id,
        filename: sample.filename,
        patient_id: person.id,
        status: "analyzed",
        created_at: inputs.created_at,
        updated_at: inputs.created_at,
        cancer_probability: sample.result.cancer_probability,
        flagged: sample.result.flagged,
        dataset_label: sample.label as Label,
      },
      patient: { ...person, created_at: inputs.created_at },
      analysis_result: { ...sample.result, case_id: sample.id },
      notes: null,
    };
    expect(generateTextReport(detail, inputs.notes, new Date(inputs.generated_at))).toBe(
      read(join(fixtures, "report.txt"))
    );
  });
});

describe("display filenames", () => {
  const cases: { name: string; extension: string; display: string }[] = JSON.parse(
    read(join(fixtures, "filenames.json"))
  );
  it.each(cases)("names $name as the server does", ({ name, extension, display }) => {
    expect(displayFilename(name, extension)).toBe(display);
  });
});
