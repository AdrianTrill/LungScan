"""The lung CT classifier: preprocessing, download, and inference with ONNX Runtime.

The network is the ResNet-50 from dorsar/lung-cancer-detection, exported to ONNX by
tools/export_model.py with a second output: a Grad-CAM map of the evidence for cancer,
computed inside the graph from the same forward pass. The browser runs the same file
with ONNX Runtime Web (frontend/src/lib/inference/).
"""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

LABELS = ("adenocarcinoma", "large_cell_carcinoma", "normal", "squamous_cell_carcinoma")
LABEL_NAMES = {
    "adenocarcinoma": "Adenocarcinoma",
    "large_cell_carcinoma": "Large cell carcinoma",
    "normal": "Normal",
    "squamous_cell_carcinoma": "Squamous cell carcinoma",
}
NORMAL = 2
CANCER = (0, 1, 3)

# The model's own training pipeline: images resized to 250x250, then Resize(256) and
# CenterCrop(224), normalized with the ImageNet statistics.
STAGED_SIZE = 250
RESIZED_SIZE = 256
CROP_SIZE = 224
CROP_OFFSET = (RESIZED_SIZE - CROP_SIZE) // 2
GRID = 7
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

MODEL_NAME = "ResNet-50 lung CT classifier"
MODEL_SOURCE = "dorsar/lung-cancer-detection"


class ModelUnavailableError(RuntimeError):
    """Raised when the model file is missing and cannot be downloaded."""


@dataclass(frozen=True)
class RawOutput:
    """What the network returns for one image."""

    logits: np.ndarray
    cam: np.ndarray
    width: int
    height: int
    inference_ms: float


def load_rgb(path: Path) -> Image.Image:
    """Open an image file as 8-bit RGB, dropping any alpha channel."""
    with Image.open(path) as image:
        return image.convert("RGB")


def preprocess(image: Image.Image) -> np.ndarray:
    """Turn an RGB image into the network's 1x3x224x224 input."""
    staged = image.resize((STAGED_SIZE, STAGED_SIZE), Image.BILINEAR)
    resized = staged.resize((RESIZED_SIZE, RESIZED_SIZE), Image.BILINEAR)
    end = CROP_OFFSET + CROP_SIZE
    crop = resized.crop((CROP_OFFSET, CROP_OFFSET, end, end))
    x = (np.asarray(crop, dtype=np.float32) / 255.0 - MEAN) / STD
    return np.ascontiguousarray(x.transpose(2, 0, 1)[None])


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_model(url: str, path: Path) -> Path:
    """Download the model and its manifest, and check the file against the manifest."""
    manifest_url = url.rsplit(".", 1)[0] + ".json"
    logger.info("Downloading the model manifest from %s", manifest_url)
    try:
        with urllib.request.urlopen(manifest_url, timeout=30) as response:
            manifest = json.load(response)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".part", delete=False) as tmp:
            logger.info(
                "Downloading the model (%s MB) from %s", manifest["bytes"] // 1_000_000, url
            )
            with urllib.request.urlopen(url, timeout=60) as response:
                for chunk in iter(lambda: response.read(1 << 20), b""):
                    tmp.write(chunk)
        part = Path(tmp.name)
    except Exception as error:  # noqa: BLE001
        raise ModelUnavailableError(
            f"The model is not at {path} and could not be downloaded from {url} ({error}). "
            "Export it with `python -m tools.export_model` (see backend/requirements-model.txt)."
        ) from error
    if file_sha256(part) != manifest["sha256"]:
        part.unlink(missing_ok=True)
        raise ModelUnavailableError(f"The model downloaded from {url} does not match its manifest")
    part.chmod(0o644)
    part.replace(path)
    (path.with_suffix(".json")).write_text(json.dumps(manifest, indent=2) + "\n")
    return path


class Classifier:
    """Runs the exported ONNX model on the CPU, loading it on first use."""

    def __init__(self, model_path: Path, model_url: str | None = None):
        self.model_path = Path(model_path)
        self.model_url = model_url
        self._session = None
        self._lock = threading.Lock()

    @property
    def runtime(self) -> str:
        import onnxruntime

        return f"ONNX Runtime {onnxruntime.__version__} (server)"

    @property
    def source(self) -> str:
        manifest = self.model_path.with_suffix(".json")
        if manifest.exists():
            revision = json.loads(manifest.read_text())["source"]["revision"]
            return f"{MODEL_SOURCE}@{revision[:7]}"
        return MODEL_SOURCE

    def session(self):
        with self._lock:
            if self._session is None:
                import onnxruntime

                if not self.model_path.exists():
                    if not self.model_url:
                        raise ModelUnavailableError(f"The model is not at {self.model_path}")
                    download_model(self.model_url, self.model_path)
                self._session = onnxruntime.InferenceSession(
                    str(self.model_path), providers=["CPUExecutionProvider"]
                )
                logger.info("Loaded the model from %s", self.model_path)
            return self._session

    def run(self, image: Image.Image) -> RawOutput:
        x = preprocess(image)
        session = self.session()
        start = time.perf_counter()
        logits, cam = session.run(["logits", "cam"], {"image": x})
        elapsed = (time.perf_counter() - start) * 1000
        return RawOutput(
            logits=logits[0],
            cam=cam[0],
            width=image.width,
            height=image.height,
            inference_ms=elapsed,
        )
