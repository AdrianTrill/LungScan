"""Measure the classifier on the test split it was published with, without duplicates.

    cd backend
    python -m tools.evaluate                # writes ../model/evaluation.json

The test images come from the model's Hugging Face repository, at the pinned revision.
Many of its normal slices are copies of training or validation images (some re-encoded
or resized), or of each other. A test image is dropped when its perceptual hash is within
DUPLICATE_BITS of a training or validation image, or of a test image already kept; the
counts are recorded in the output. Inference goes through the app's own Classifier, so
the numbers describe exactly what the app runs.
"""

import argparse
import hashlib
import json
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from huggingface_hub import hf_hub_download, list_repo_files
from PIL import Image

from app.core.config import REPO_DIR
from app.services.analysis import softmax
from app.services.model import CANCER, LABELS, MEAN, NORMAL, STD, Classifier, load_rgb, preprocess
from tools.export_model import HF_REPO, HF_REVISION

# Folder names in the repository's Data/ splits, in the model's class order.
FOLDERS = {
    "adenocarcinoma": "adenocarcinoma",
    "large.cell.carcinoma": "large_cell_carcinoma",
    "normal": "normal",
    "squamous.cell.carcinoma": "squamous_cell_carcinoma",
}


def label_of(path: str) -> str:
    folder = path.split("/")[2]
    for prefix, label in FOLDERS.items():
        if folder.startswith(prefix):
            return label
    raise ValueError(f"Unknown class folder: {folder}")


def download_split(split: str) -> list[tuple[str, Path, str]]:
    files = [
        f
        for f in list_repo_files(HF_REPO, revision=HF_REVISION)
        if f.startswith(f"Data/{split}/") and f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]

    def get(f):
        return f, Path(hf_hub_download(HF_REPO, f, revision=HF_REVISION)), label_of(f)

    with ThreadPoolExecutor(16) as pool:
        return sorted(pool.map(get, files))


# A 16x16 difference hash has 256 bits. Copies in this dataset are 0 to 3 bits apart;
# different slices, even neighboring ones, are more than 20 apart.
HASH_SIZE = 16
DUPLICATE_BITS = 10


def pixel_hash(path: Path) -> str:
    image = load_rgb(path)
    return hashlib.sha1(image.tobytes() + repr(image.size).encode()).hexdigest()


def perceptual_hash(path: Path) -> np.ndarray:
    """Difference hash: whether each pixel of a small grayscale copy is brighter than its left neighbor."""
    small = load_rgb(path).convert("L").resize((HASH_SIZE + 1, HASH_SIZE), Image.BILINEAR)
    a = np.asarray(small, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


def near(bits: np.ndarray, pool: list[np.ndarray]) -> bool:
    return bool(pool) and int((np.array(pool) != bits).sum(axis=1).min()) <= DUPLICATE_BITS


def wilson(k: int, n: int, z: float = 1.959964) -> list[float]:
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]


def auc(scores: np.ndarray, positive: np.ndarray) -> float:
    """Area under the ROC curve (the Mann-Whitney statistic, ties counted half)."""
    pos, neg = scores[positive], scores[~positive]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    greater = (pos[:, None] > neg[None, :]).sum()
    ties = (pos[:, None] == neg[None, :]).sum()
    return float((greater + 0.5 * ties) / (len(pos) * len(neg)))


def measure(probs: np.ndarray, labels: list[str]) -> dict:
    y = np.array([LABELS.index(label) for label in labels])
    cancer = y != NORMAL
    p_cancer = probs[:, list(CANCER)].sum(axis=1)
    flagged = p_cancer >= 0.5
    pred = probs.argmax(axis=1)
    confusion = np.zeros((len(LABELS), len(LABELS)), dtype=int)
    for t, q in zip(y, pred, strict=True):
        confusion[t, q] += 1
    per_class = {}
    for i, label in enumerate(LABELS):
        tp = confusion[i, i]
        precision = tp / max(confusion[:, i].sum(), 1)
        recall = tp / max(confusion[i].sum(), 1)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "f1": round(float(f1), 4),
            "support": int(confusion[i].sum()),
        }
    tp, fn = int((flagged & cancer).sum()), int((~flagged & cancer).sum())
    tn, fp = int((~flagged & ~cancer).sum()), int((flagged & ~cancer).sum())
    best_cancer = np.array(CANCER)[probs[:, list(CANCER)].argmax(axis=1)]
    subtype_right = int((best_cancer[cancer] == y[cancer]).sum())
    return {
        "images": int(len(y)),
        "cancer_vs_normal": {
            "threshold": 0.5,
            "accuracy": round(float((flagged == cancer).mean()), 4),
            "sensitivity": {"k": tp, "n": tp + fn, "ci95": wilson(tp, tp + fn)},
            "specificity": {"k": tn, "n": tn + fp, "ci95": wilson(tn, tn + fp)},
            "auc": round(auc(p_cancer, cancer), 4),
        },
        "four_class": {
            "accuracy": round(float((pred == y).mean()), 4),
            "confusion": confusion.tolist(),
            "per_class": per_class,
        },
        "subtype_on_cancers": {
            "k": subtype_right,
            "n": int(cancer.sum()),
            "accuracy": round(subtype_right / max(int(cancer.sum()), 1), 4),
            "chance": round(1 / len(CANCER), 4),
        },
    }


def _normalize(image: Image.Image, mean=MEAN, std=STD) -> np.ndarray:
    x = (np.asarray(image, dtype=np.float32) / 255.0 - mean) / std
    return np.ascontiguousarray(x.transpose(2, 0, 1)[None])


def _run_py(image: Image.Image) -> np.ndarray:
    """The model repository's run.py: Resize(256) on the shorter side, CenterCrop(224)."""
    w, h = image.size
    size = (256, int(256 * h / w)) if w <= h else (int(256 * w / h), 256)
    resized = image.resize(size, Image.BILINEAR)
    left, top = round((size[0] - 224) / 2), round((size[1] - 224) / 2)
    return _normalize(resized.crop((left, top, left + 224, top + 224)))


# Candidate preprocessing pipelines, compared on the validation split. The app uses the
# first: it is the model's training pipeline (preprocess.py resizes to 250x250 before
# architecture.py's Resize(256) and CenterCrop(224)), and it scores best there.
PIPELINES = {
    "training (250x250, 256, crop 224)": preprocess,
    "run.py (shorter side 256, crop 224)": _run_py,
    "stretch to 224x224": lambda im: _normalize(im.resize((224, 224), Image.BILINEAR)),
    "previous backend (stretch, red-channel statistics)": lambda im: _normalize(
        im.resize((224, 224), Image.BILINEAR),
        mean=np.float32([0.485] * 3),
        std=np.float32([0.229] * 3),
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", type=Path, default=REPO_DIR / "model" / "lungscan.onnx")
    parser.add_argument("--out", type=Path, default=REPO_DIR / "model" / "evaluation.json")
    args = parser.parse_args()

    splits = {s: download_split(s) for s in ("train", "valid", "test")}
    training = [perceptual_hash(p) for s in ("train", "valid") for _, p, _ in splits[s]]
    training_exact = {pixel_hash(p) for s in ("train", "valid") for _, p, _ in splits[s]}
    clean, kept = [], []
    removed = Counter()
    for item in splits["test"]:
        bits = perceptual_hash(item[1])
        if near(bits, training):
            exact = pixel_hash(item[1]) in training_exact
            removed[
                "exact_copies_of_train_or_valid" if exact else "near_copies_of_train_or_valid"
            ] += 1
            removed[f"from_{item[2]}"] += 1
        elif near(bits, kept):
            removed["repeats_within_test"] += 1
            removed[f"from_{item[2]}"] += 1
        else:
            clean.append(item)
            kept.append(bits)

    classifier = Classifier(args.model)

    def predict(items):
        return np.array([softmax(classifier.run(load_rgb(p)).logits) for _, p, _ in items])

    session = classifier.session()

    def compare(items):
        out = {}
        for name, pipeline in PIPELINES.items():
            probs = []
            for _, p, _ in items:
                logits, _ = session.run(["logits", "cam"], {"image": pipeline(load_rgb(p))})
                probs.append(softmax(logits[0]))
            m = measure(np.array(probs), [label for _, _, label in items])
            out[name] = {
                "four_class": m["four_class"]["accuracy"],
                "cancer_vs_normal": m["cancer_vs_normal"]["accuracy"],
                "subtype_on_cancers": m["subtype_on_cancers"]["accuracy"],
            }
        return out

    report = {
        "model": {
            "source": classifier.source,
            "sha256": json.loads(args.model.with_suffix(".json").read_text())["sha256"],
            "pipeline": "the app's: resize to 250x250, then 256x256, center crop 224, ImageNet normalization",
        },
        "data": {
            "repo": HF_REPO,
            "revision": HF_REVISION,
            "images": {s: len(v) for s, v in splits.items()},
            "duplicate_rule": f"perceptual hash ({HASH_SIZE}x{HASH_SIZE} dHash) within {DUPLICATE_BITS} bits",
            "test_removed": dict(sorted(removed.items())),
            "clean_test_per_class": dict(Counter(label for _, _, label in clean)),
        },
        "clean_test": measure(predict(clean), [label for _, _, label in clean]),
        "full_test": measure(predict(splits["test"]), [label for _, _, label in splits["test"]]),
        "validation": measure(predict(splits["valid"]), [label for _, _, label in splits["valid"]]),
        "pipelines": {"validation": compare(splits["valid"]), "clean_test": compare(clean)},
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")

    c = report["clean_test"]
    cn = c["cancer_vs_normal"]
    print(f"Clean test split: {c['images']} images {report['data']['clean_test_per_class']}")
    print(
        f"  cancer vs normal: sensitivity {cn['sensitivity']['k']}/{cn['sensitivity']['n']}, "
        f"specificity {cn['specificity']['k']}/{cn['specificity']['n']}, AUC {cn['auc']}"
    )
    print(
        f"  four classes: {c['four_class']['accuracy']:.3f}; subtype on cancers: "
        f"{c['subtype_on_cancers']['accuracy']:.3f} (chance {c['subtype_on_cancers']['chance']:.3f})"
    )
    print("Preprocessing pipelines (four-class / cancer vs normal / subtype accuracy):")
    for split, rows in report["pipelines"].items():
        for name, row in rows.items():
            print(
                f"  {split:<11} {name:<52} {row['four_class']:.3f} / "
                f"{row['cancer_vs_normal']:.3f} / {row['subtype_on_cancers']:.3f}"
            )
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
