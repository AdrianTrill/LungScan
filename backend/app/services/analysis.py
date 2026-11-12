"""Turns the network's raw output into a read: probabilities, heat map, regions, summary.

frontend/src/lib/inference/interpret.ts implements the same steps, and a test checks
that both give the same result on every sample slice. Keep the two in step: same
thresholds, same rounding (half up), same order of operations.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np

from app.core.schemas import AnalyzeResult, Box, Heatmap, ModelInfo, Region
from app.services.model import (
    CANCER,
    CROP_OFFSET,
    CROP_SIZE,
    GRID,
    LABEL_NAMES,
    LABELS,
    MODEL_NAME,
    RESIZED_SIZE,
    RawOutput,
)

FLAG_THRESHOLD = 0.5
REGION_THRESHOLD = 0.5
MAX_REGIONS = 3
CELL = CROP_SIZE / GRID


def round_half_up(value: float, digits: int = 0) -> float:
    scale = 10**digits
    return math.floor(value * scale + 0.5) / scale


def percent(value: float) -> str:
    return f"{round_half_up(value * 100, 1):.1f}%"


def probability(value: float) -> str:
    """A probability as a percentage that never rounds up to certainty."""
    if value >= 0.9995:
        return ">99.9%"
    if 0 < value < 0.0005:
        return "<0.1%"
    return percent(value)


def softmax(logits) -> list[float]:
    z = [float(v) for v in logits]
    top = max(z)
    e = [math.exp(v - top) for v in z]
    total = sum(e)
    return [v / total for v in e]


def position(gx: float, gy: float) -> str:
    rows = ("upper", "middle", "lower")
    cols = ("left", "center", "right")
    row = rows[min(2, math.floor(gy * 3 / GRID))]
    col = cols[min(2, math.floor(gx * 3 / GRID))]
    return "center" if (row, col) == ("middle", "center") else f"{row} {col}"


def find_regions(rel: list[list[float]], cancer: float, width: int, height: int) -> list[Region]:
    """Group grid cells with at least half the peak evidence into 8-connected regions."""
    seen = [[False] * GRID for _ in range(GRID)]
    components = []
    for i in range(GRID):
        for j in range(GRID):
            if seen[i][j] or rel[i][j] < REGION_THRESHOLD:
                continue
            seen[i][j] = True
            stack, cells = [(i, j)], []
            while stack:
                a, b = stack.pop()
                cells.append((a, b))
                for da in (-1, 0, 1):
                    for db in (-1, 0, 1):
                        na, nb = a + da, b + db
                        if 0 <= na < GRID and 0 <= nb < GRID and not seen[na][nb]:
                            if rel[na][nb] >= REGION_THRESHOLD:
                                seen[na][nb] = True
                                stack.append((na, nb))
            components.append(sorted(cells))

    found = []
    for cells in components:
        weight = 0.0
        sx = 0.0
        sy = 0.0
        peak = 0.0
        for a, b in cells:
            w = rel[a][b]
            weight += w
            sx += w * (b + 0.5)
            sy += w * (a + 0.5)
            peak = max(peak, w)
        gx, gy = sx / weight, sy / weight
        found.append((peak, len(cells), gx, gy))
    found.sort(key=lambda r: (-r[0], -r[1], r[3], r[2]))

    sx_scale = width / RESIZED_SIZE
    sy_scale = height / RESIZED_SIZE
    regions = []
    for k, (peak, count, gx, gy) in enumerate(found[:MAX_REGIONS], start=1):
        radius_cells = math.sqrt(count / math.pi)
        regions.append(
            Region(
                id=f"r{k}",
                x=int(round_half_up((CROP_OFFSET + gx * CELL) * sx_scale)),
                y=int(round_half_up((CROP_OFFSET + gy * CELL) * sy_scale)),
                radius=int(round_half_up(radius_cells * CELL * math.sqrt(sx_scale * sy_scale))),
                evidence=round_half_up(peak * cancer, 4),
                cells=count,
                explanation=(
                    f"Grad-CAM evidence for cancer peaks here at {percent(peak)} of the slice's "
                    f"maximum, over {count} of {GRID * GRID} grid cells, in the "
                    f"{position(gx, gy)} of the image."
                ),
            )
        )
    return regions


def summarize(cancer: float, flagged: bool, subtype: str | None, share: float, regions: int) -> str:
    if not flagged:
        return f"Cancer probability {probability(cancer)}: the model reads this slice as normal."
    plural = "" if regions == 1 else "s"
    return (
        f"Cancer probability {probability(cancer)}: the model reads this slice as cancer. "
        f"Most likely subtype: {LABEL_NAMES[subtype]} ({probability(share)} of the cancer "
        "probability), though the model's subtype calls are unreliable. "
        f"Grad-CAM marks {regions} region{plural} that raised the cancer score."
    )


def interpret(
    raw: RawOutput,
    case_id: str,
    source: str,
    runtime: str,
    analyzed_at: datetime | None = None,
) -> AnalyzeResult:
    p = softmax(raw.logits)
    cancer = p[CANCER[0]] + p[CANCER[1]] + p[CANCER[2]]
    flagged = cancer >= FLAG_THRESHOLD
    predicted = LABELS[max(range(len(p)), key=lambda i: (p[i], -i))]
    best = max(CANCER, key=lambda i: (p[i], -i))
    subtype = LABELS[best] if flagged else None
    share = p[best] / cancer if cancer > 0 else 0.0

    cam = [
        [float(v) for v in row] for row in np.asarray(raw.cam, dtype=np.float32).reshape(GRID, GRID)
    ]
    peak = max(max(row) for row in cam)
    rel = [[(v / peak if peak > 0 else 0.0) for v in row] for row in cam]
    regions = find_regions(rel, cancer, raw.width, raw.height) if flagged and peak > 0 else []

    sx = raw.width / RESIZED_SIZE
    sy = raw.height / RESIZED_SIZE
    heatmap = Heatmap(
        size=GRID,
        values=[round_half_up(v * cancer, 4) for row in rel for v in row],
        box=Box(
            x=round_half_up(CROP_OFFSET * sx, 2),
            y=round_half_up(CROP_OFFSET * sy, 2),
            width=round_half_up(CROP_SIZE * sx, 2),
            height=round_half_up(CROP_SIZE * sy, 2),
        ),
    )
    return AnalyzeResult(
        case_id=case_id,
        cancer_probability=round_half_up(cancer, 6),
        flagged=flagged,
        predicted_class=predicted,
        subtype=subtype,
        probabilities={label: round_half_up(p[i], 6) for i, label in enumerate(LABELS)},
        heatmap=heatmap,
        regions=regions,
        summary=summarize(cancer, flagged, subtype, share, len(regions)),
        model=ModelInfo(name=MODEL_NAME, source=source, runtime=runtime),
        inference_ms=round_half_up(raw.inference_ms, 1),
        analyzed_at=analyzed_at or datetime.now(timezone.utc),
    )


def analyze_image(classifier, image, case_id: str) -> AnalyzeResult:
    """Run the classifier on an RGB image and interpret its output."""
    raw = classifier.run(image)
    return interpret(raw, case_id, source=classifier.source, runtime=classifier.runtime)
