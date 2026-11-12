"""Write the fixtures the frontend's tests compare its ports of the server's code against.

    cd backend
    python -m tools.make_fixtures      # writes ../frontend/src/tests/fixtures/

The browser runtime reimplements three pieces of the server: Pillow's bilinear resize
(and with it the whole preprocessing), the plain-text report, and the display name of an
uploaded file. These fixtures are what the server produces; the frontend's tests check
that the browser produces exactly the same. CI regenerates them and fails if they change.
"""

import base64
import hashlib
import json
from datetime import datetime, timezone

import numpy as np
from PIL import Image

from app.core.config import REPO_DIR
from app.core.schemas import AnalyzeResult, Case, CaseDetail, Patient
from app.core.utils import display_filename
from app.services.model import preprocess
from app.services.report import generate_text_report

OUT = REPO_DIR / "frontend" / "src" / "tests" / "fixtures"
SAMPLES = REPO_DIR / "model" / "samples" / "samples.json"


def pixels(image: Image.Image) -> str:
    return base64.b64encode(np.asarray(image, dtype=np.uint8).tobytes()).decode()


def resample_fixture() -> dict:
    rng = np.random.default_rng(7)
    image = Image.fromarray(rng.integers(0, 256, size=(47, 61, 3), dtype=np.uint8), "RGB")
    sizes = [(25, 17), (70, 9), (61, 100), (13, 47), (61, 9), (40, 12)]
    staged = image.resize((250, 250), Image.BILINEAR).resize((256, 256), Image.BILINEAR)
    x = preprocess(image).astype(np.float64).flatten()
    return {
        "width": image.width,
        "height": image.height,
        "input": pixels(image),
        "resized": [
            {"width": w, "height": h, "pixels": pixels(image.resize((w, h), Image.BILINEAR))}
            for w, h in sizes
        ],
        "pipeline_sha256": hashlib.sha256(np.asarray(staged).tobytes()).hexdigest(),
        "tensor": {"sum": float(x.sum()), "first": x[:6].tolist(), "last": x[-6:].tolist()},
    }


def report_fixture() -> tuple[dict, str]:
    manifest = json.loads(SAMPLES.read_text())
    sample = next(c for c in manifest["cases"] if c["id"] == "sample-01")
    person = next(p for p in manifest["patients"] if p["id"] == sample["patient_id"])
    created = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
    detail = CaseDetail(
        case=Case(
            id=sample["id"],
            filename=sample["filename"],
            patient_id=person["id"],
            status="analyzed",
            created_at=created,
            updated_at=created,
            cancer_probability=sample["result"]["cancer_probability"],
            flagged=sample["result"]["flagged"],
            dataset_label=sample["label"],
        ),
        patient=Patient(**person, created_at=created),
        analysis_result=AnalyzeResult(**sample["result"], case_id=sample["id"]),
        notes=None,
    )
    notes = "Compare with the prior study.\nNo action needed."
    generated = datetime(2026, 2, 3, 4, 5, tzinfo=timezone.utc)
    inputs = {
        "case_id": sample["id"],
        "created_at": created.isoformat(),
        "generated_at": generated.isoformat(),
        "notes": notes,
    }
    return inputs, generate_text_report(detail, notes, generated)


def filename_fixture() -> list[dict]:
    names = [
        "slice.png",
        "My Scan (1).png",
        "  .hidden.jpeg",
        "ünïcode scan.jpg",
        "a.b.c.png",
        "....png",
        ".png",
        "trailing.",
        "",
    ]
    return [{"name": n, "extension": ".png", "display": display_filename(n, ".png")} for n in names]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "resample.json").write_text(json.dumps(resample_fixture()) + "\n")
    inputs, report = report_fixture()
    (OUT / "report.json").write_text(json.dumps(inputs, indent=2) + "\n")
    (OUT / "report.txt").write_text(report)
    (OUT / "filenames.json").write_text(json.dumps(filename_fixture(), indent=2) + "\n")
    print(f"Wrote the fixtures to {OUT}")


if __name__ == "__main__":
    main()
