"""Shared fixtures: an isolated storage, a stand-in for the model, and a test client."""

from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.services.model import GRID, ModelUnavailableError, RawOutput
from app.services.storage import Storage

REPO_DIR = Path(__file__).resolve().parents[3]
MODEL_PATH = REPO_DIR / "model" / "lungscan.onnx"
SAMPLES_DIR = REPO_DIR / "model" / "samples"


class FakeClassifier:
    """Stands in for the ONNX model with fixed logits and a fixed Grad-CAM map."""

    source = "fake/model@0000000"
    runtime = "Fake runtime (server)"

    def __init__(self, logits=(0.5, 3.0, -2.0, 0.5), cam=None, available=True):
        self.logits = np.array(logits, dtype=np.float32)
        if cam is None:
            cam = np.zeros((GRID, GRID), dtype=np.float32)
            cam[2, 4] = 1.0
            cam[2, 5] = 0.6
        self.cam = np.asarray(cam, dtype=np.float32)
        self.available = available
        self.model_path = Path("/nonexistent/lungscan.onnx")
        self.calls = 0

    def run(self, image):
        if not self.available:
            raise ModelUnavailableError("The model is not available in this test")
        self.calls += 1
        return RawOutput(self.logits, self.cam, image.width, image.height, inference_ms=12.5)


def png_bytes(width=64, height=48, value=90) -> bytes:
    image = Image.new("RGB", (width, height), (value, value, value))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def storage(tmp_path) -> Storage:
    return Storage(tmp_path / "data", tmp_path / "uploads")


@pytest.fixture
def classifier() -> FakeClassifier:
    return FakeClassifier()


@pytest.fixture
def client(storage, classifier):
    with TestClient(create_app(storage, classifier)) as test_client:
        yield test_client
