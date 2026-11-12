"""Tests of the real network. They skip unless the model (or PyTorch) is installed.

CI exports the model and runs them; locally, run `python -m tools.export_model` first.
"""

import json

import numpy as np
import pytest

from app.services.analysis import interpret
from app.services.model import Classifier, load_rgb
from app.tests.conftest import MODEL_PATH, SAMPLES_DIR

needs_model = pytest.mark.skipif(not MODEL_PATH.exists(), reason="model/lungscan.onnx is missing")


@pytest.mark.model
@needs_model
def test_the_model_reproduces_the_sample_reads():
    manifest = json.loads((SAMPLES_DIR / "samples.json").read_text())
    classifier = Classifier(MODEL_PATH)
    for case in manifest["cases"]:
        raw = classifier.run(load_rgb(SAMPLES_DIR / case["image"]))
        np.testing.assert_allclose(raw.logits, case["raw"]["logits"], atol=1e-4)
        np.testing.assert_allclose(raw.cam.flatten(), case["raw"]["cam"], atol=1e-5)
        result = interpret(raw, case["id"], classifier.source, classifier.runtime)
        want = case["result"]
        assert result.flagged == want["flagged"]
        assert result.subtype == want["subtype"]
        assert [r.model_dump(exclude={"evidence"}) for r in result.regions] == [
            {k: v for k, v in r.items() if k != "evidence"} for r in want["regions"]
        ]


@pytest.mark.torch
def test_the_graph_computes_grad_cam_exactly():
    torch = pytest.importorskip("torch")
    from tools.network import ExplainedNet, LungCancerNet, autograd_cam

    torch.manual_seed(1)
    net = LungCancerNet().eval()
    for module in net.modules():
        if isinstance(module, torch.nn.BatchNorm2d):
            module.running_mean.uniform_(-0.1, 0.1)
            module.running_var.uniform_(0.5, 1.5)
    x = torch.randn(3, 3, 224, 224)
    with torch.no_grad():
        logits, cam = ExplainedNet(net).eval()(x)
        torch.testing.assert_close(logits, net(x))
    want = autograd_cam(net, x)
    assert want.abs().max() > 0
    torch.testing.assert_close(cam, want, rtol=1e-4, atol=1e-7)
