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


@pytest.mark.torch
def test_folding_batchnorm_keeps_the_outputs():
    torch = pytest.importorskip("torch")
    from tools.network import LungCancerNet
    from tools.quantize import fuse_batchnorm

    torch.manual_seed(3)
    net = LungCancerNet().eval()
    for module in net.modules():
        if isinstance(module, torch.nn.BatchNorm2d):
            module.running_mean.uniform_(-0.1, 0.1)
            module.running_var.uniform_(0.5, 1.5)
            module.weight.data.uniform_(0.5, 1.5)
            module.bias.data.uniform_(-0.1, 0.1)
    fused = fuse_batchnorm(net)
    assert not any(isinstance(m, torch.nn.BatchNorm2d) for m in fused.modules())
    x = torch.randn(2, 3, 224, 224)
    with torch.no_grad():
        want = net(x)
        torch.testing.assert_close(fused(x), want, rtol=1e-4, atol=1e-4 * want.abs().max())


@pytest.mark.torch
def test_int8_weights_load_as_the_rounded_network(tmp_path):
    torch = pytest.importorskip("torch")
    onnx = pytest.importorskip("onnx")
    import onnxruntime

    from tools.quantize import GROUP, quantize_convolutions, store_int8

    torch.manual_seed(2)
    net = torch.nn.Sequential(
        torch.nn.Conv2d(32, 64, 3, padding=1), torch.nn.ReLU(), torch.nn.Conv2d(64, 8, 1)
    ).eval()
    before = [net[0].weight.detach().clone(), net[2].weight.detach().clone()]
    stored = quantize_convolutions(net, keep=())
    assert len(stored) == 2
    for original, module in zip(before, (net[0], net[2]), strict=True):
        blocks = original.reshape(original.shape[0], -1, GROUP)
        step = blocks.abs().amax(dim=2, keepdim=True) / 127
        error = (module.weight.detach().reshape(blocks.shape) - blocks).abs()
        assert (error <= step / 2 * 1.0001).all()

    path = tmp_path / "net.onnx"
    torch.onnx.export(
        net,
        torch.zeros(1, 32, 8, 8),
        str(path),
        input_names=["x"],
        output_names=["y"],
        opset_version=17,
        dynamo=False,
    )
    model = onnx.load(str(path))
    assert store_int8(model, stored) == 2
    onnx.checker.check_model(model)
    assert not [
        t.name
        for t in model.graph.initializer
        if t.data_type == onnx.TensorProto.FLOAT and len(t.dims) == 4
    ]
    onnx.save(model, str(path))

    x = torch.randn(1, 32, 8, 8)
    with torch.no_grad():
        want = net(x).numpy()
    session = onnxruntime.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    np.testing.assert_allclose(session.run(None, {"x": x.numpy()})[0], want, rtol=1e-5, atol=1e-6)
