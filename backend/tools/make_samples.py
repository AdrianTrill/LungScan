"""Build the sample slices the app starts with, and their reference reads.

    cd backend
    python -m tools.make_samples            # writes ../model/samples/
    python -m tools.make_samples --check    # re-runs the model, compares with samples.json

The slices are unique images from the model's test split (none is a copy of a training
image), chosen to show what the model gets right and wrong. samples.json keeps the
network's raw outputs next to each read, so the browser's interpretation can be tested
against the server's without running the network (frontend/src/lib/inference/).
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from huggingface_hub import hf_hub_download

from app.core.config import REPO_DIR
from app.services.analysis import interpret
from app.services.model import Classifier, load_rgb
from tools.export_model import HF_REPO, HF_REVISION

PATIENTS = [
    ("patient-001", "John", "Smith", "1975-03-15", "MRN-2024-001"),
    ("patient-002", "Sarah", "Johnson", "1982-07-22", "MRN-2024-002"),
    ("patient-003", "Michael", "Williams", "1968-11-08", "MRN-2024-003"),
    ("patient-004", "Emily", "Brown", "1990-05-30", "MRN-2024-004"),
    ("patient-005", "Robert", "Davis", "1955-12-10", "MRN-2024-005"),
]

# Oldest first: the app lists the last one at the top of the worklist.
SAMPLES = [
    ("sample-07", "Data/test/adenocarcinoma/000158 (2).png", "patient-001", "slice-000158.png", ""),
    ("sample-06", "Data/test/normal/23.png", "patient-005", "slice-normal-23.png", ""),
    (
        "sample-05",
        "Data/test/large.cell.carcinoma/000136 (2).png",
        "patient-003",
        "slice-000136.png",
        "",
    ),
    ("sample-04", "Data/test/normal/25.png", "patient-004", "slice-normal-25.png", ""),
    ("sample-03", "Data/test/adenocarcinoma/000126 (6).png", "patient-003", "slice-000126.png", ""),
    (
        "sample-02",
        "Data/test/squamous.cell.carcinoma/000116 (5).png",
        "patient-002",
        "slice-000116.png",
        "",
    ),
    (
        "sample-01",
        "Data/test/adenocarcinoma/000120.png",
        "patient-001",
        "slice-000120.png",
        "Demo note. The model flags this slice, and its Grad-CAM evidence sits in the upper "
        "left of the image (the patient's right). Review the full series before reporting.",
    ),
]

FOLDER_LABELS = {
    "adenocarcinoma": "adenocarcinoma",
    "large.cell.carcinoma": "large_cell_carcinoma",
    "normal": "normal",
    "squamous.cell.carcinoma": "squamous_cell_carcinoma",
}


def build(classifier: Classifier, out: Path) -> dict:
    runtime = classifier.runtime.replace("(server)", "(precomputed sample)")
    cases = []
    for case_id, hf_path, patient_id, filename, notes in SAMPLES:
        source = Path(hf_hub_download(HF_REPO, hf_path, revision=HF_REVISION))
        image_name = f"images/{case_id}.png"
        (out / "images").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, out / image_name)
        raw = classifier.run(load_rgb(source))
        result = interpret(
            raw,
            case_id,
            source=classifier.source,
            runtime=runtime,
            analyzed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        cases.append(
            {
                "id": case_id,
                "image": image_name,
                "filename": filename,
                "label": FOLDER_LABELS[hf_path.split("/")[2]],
                "source_path": hf_path,
                "patient_id": patient_id,
                "notes": notes,
                "raw": {
                    "logits": [float(v) for v in raw.logits],
                    "cam": [float(v) for v in np.asarray(raw.cam).flatten()],
                    "width": raw.width,
                    "height": raw.height,
                },
                "result": result.model_dump(mode="json", exclude={"case_id"}),
            }
        )
    return {
        "source": {
            "repo": HF_REPO,
            "revision": HF_REVISION,
            "split": "test",
            "license": "MIT",
            "url": f"https://huggingface.co/{HF_REPO}/tree/{HF_REVISION}/Data/test",
        },
        "model_sha256": json.loads(classifier.model_path.with_suffix(".json").read_text())[
            "sha256"
        ],
        "patients": [
            {
                "id": pid,
                "first_name": first,
                "last_name": last,
                "date_of_birth": dob,
                "medical_record_number": mrn,
            }
            for pid, first, last, dob, mrn in PATIENTS
        ],
        "cases": cases,
    }


def compare(want: dict, got: dict) -> list[str]:
    """Differences between two builds beyond float noise (timings are ignored)."""
    problems = []
    for a, b in zip(want["cases"], got["cases"], strict=True):
        for key in ("logits", "cam"):
            diff = np.abs(np.array(a["raw"][key]) - np.array(b["raw"][key])).max()
            if diff > 1e-4:
                problems.append(f"{a['id']}: raw {key} differs by {diff:.2e}")
        ra, rb = dict(a["result"]), dict(b["result"])
        for r in (ra, rb):
            r.pop("inference_ms"), r.pop("analyzed_at"), r.pop("model")
        if abs(ra.pop("cancer_probability") - rb.pop("cancer_probability")) > 1e-4:
            problems.append(f"{a['id']}: cancer probability differs")
        pa, pb = ra.pop("probabilities"), rb.pop("probabilities")
        if any(abs(pa[k] - pb[k]) > 1e-4 for k in pa):
            problems.append(f"{a['id']}: probabilities differ")
        ha, hb = ra.pop("heatmap"), rb.pop("heatmap")
        if (
            ha["box"] != hb["box"]
            or max(abs(x - y) for x, y in zip(ha["values"], hb["values"], strict=True)) > 1e-3
        ):
            problems.append(f"{a['id']}: heat map differs")
        for r in (ra, rb):
            for region in r["regions"]:
                region.pop("evidence")
        if ra != rb:
            problems.append(f"{a['id']}: read differs: {ra} != {rb}")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", type=Path, default=REPO_DIR / "model" / "lungscan.onnx")
    parser.add_argument("--out", type=Path, default=REPO_DIR / "model" / "samples")
    parser.add_argument(
        "--check", action="store_true", help="compare with samples.json instead of writing"
    )
    args = parser.parse_args()

    classifier = Classifier(args.model)
    manifest_path = args.out / "samples.json"
    if args.check:
        want = json.loads(manifest_path.read_text())
        with __import__("tempfile").TemporaryDirectory() as tmp:
            got = build(classifier, Path(tmp))
        problems = compare(want, got)
        for problem in problems:
            print(problem)
        print(f"{len(want['cases'])} samples checked, {len(problems)} differences")
        sys.exit(1 if problems else 0)

    manifest = build(classifier, args.out)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    for case in manifest["cases"]:
        r = case["result"]
        print(
            f"{case['id']}  {case['label']:<24} cancer {r['cancer_probability']:.3f}  "
            f"subtype {str(r['subtype']):<24} regions {len(r['regions'])}"
        )
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
