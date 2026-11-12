"""Export the classifier to ONNX, with its Grad-CAM output, and check the export.

    cd backend
    pip install -r requirements-model.txt
    python -m tools.export_model            # writes ../model/lungscan.onnx and lungscan.json

The weights come from Hugging Face, pinned to one revision. Most convolution weights are
stored as int8 blocks (tools/quantize.py), which makes the file a third of its float32
size. Before the manifest is written, the export is checked three times: ONNX Runtime
must reproduce PyTorch's logits with the same weights, the Grad-CAM the graph computes
must match the one autograd computes, and the file must read every sample slice as the
published float32 weights do.
"""

import argparse
import hashlib
import json
import platform
import tempfile
from pathlib import Path

import numpy as np
import onnx
import onnxruntime
import torch
from huggingface_hub import hf_hub_download

from app.core.config import REPO_DIR
from app.services.analysis import softmax
from app.services.model import CANCER, CROP_SIZE, LABELS, MEAN, STD, load_rgb, preprocess
from tools.network import ExplainedNet, LungCancerNet, autograd_cam
from tools.quantize import GROUP, KEEP_FLOAT, fuse_batchnorm, quantize_convolutions, store_int8

HF_REPO = "dorsar/lung-cancer-detection"
HF_REVISION = "aa7426d75fbc0567fc6f0b36d47776fefae103f1"
HF_WEIGHTS = "Model/lung_cancer_detection_model.pth"
OPSET = 17
# The largest change in a sample slice's cancer probability that int8 weights may cause.
# On the 367 validation and test slices, the largest change is 0.015.
INT8_TOLERANCE = 0.02


def load_net() -> LungCancerNet:
    path = hf_hub_download(HF_REPO, HF_WEIGHTS, revision=HF_REVISION)
    net = LungCancerNet(len(LABELS))
    net.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    return net.eval()


def check(net: LungCancerNet, onnx_path: Path) -> dict:
    """Compare the ONNX file with PyTorch, using the same weights, on random inputs.

    Returns the largest errors.
    """
    torch.manual_seed(0)
    x = torch.randn(4, 3, CROP_SIZE, CROP_SIZE)
    with torch.no_grad():
        want_logits = net(x).numpy()
    want_cam = autograd_cam(net, x).numpy()
    session = onnxruntime.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    logits, cam = session.run(["logits", "cam"], {"image": x.numpy()})
    errors = {
        "logits": float(np.abs(logits - want_logits).max()),
        "cam": float(np.abs(cam - want_cam).max()),
        "cam_scale": float(np.abs(want_cam).max()),
    }
    if errors["logits"] > 1e-3 or errors["cam"] > 1e-4 * max(errors["cam_scale"], 1.0):
        raise SystemExit(f"The export does not match PyTorch: {errors}")
    return errors


def check_int8(full: LungCancerNet, onnx_path: Path) -> dict:
    """Read the sample slices with the file and with the float32 weights; they must agree."""
    images = sorted((REPO_DIR / "model" / "samples" / "images").glob("*.png"))
    if not images:
        raise SystemExit("No sample slices to check the int8 weights with (model/samples/images)")
    session = onnxruntime.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    largest = 0.0
    for path in images:
        x = preprocess(load_rgb(path))
        with torch.no_grad():
            want = np.array(softmax(full(torch.from_numpy(x)).numpy()[0]))
        got = np.array(softmax(session.run(["logits"], {"image": x})[0][0]))
        want_cancer, got_cancer = float(want[list(CANCER)].sum()), float(got[list(CANCER)].sum())
        if want.argmax() != got.argmax() or (want_cancer >= 0.5) != (got_cancer >= 0.5):
            raise SystemExit(f"The int8 weights change the read of {path.name}")
        largest = max(largest, abs(want_cancer - got_cancer))
    if largest > INT8_TOLERANCE:
        raise SystemExit(f"The int8 weights move a cancer probability by {largest:.4f}")
    return {"slices": len(images), "largest_cancer_probability_change": largest}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=REPO_DIR / "model" / "lungscan.onnx")
    args = parser.parse_args()

    full = load_net()
    net = fuse_batchnorm(full)
    stored = quantize_convolutions(net)
    explained = ExplainedNet(net).eval()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "lungscan.onnx"
        torch.onnx.export(
            explained,
            torch.zeros(1, 3, CROP_SIZE, CROP_SIZE),
            str(tmp_path),
            input_names=["image"],
            output_names=["logits", "cam"],
            dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}, "cam": {0: "batch"}},
            opset_version=OPSET,
            dynamo=False,
        )
        model = onnx.load(str(tmp_path))
        replaced = store_int8(model, stored)
        if replaced != len(stored):
            raise SystemExit(f"Found {replaced} of the {len(stored)} int8 weights in the graph")
        onnx.checker.check_model(model)
        model.doc_string = (
            f"{HF_REPO}@{HF_REVISION} (MIT), with int8 convolution weights in blocks of "
            f"{GROUP}. Outputs: logits over {list(LABELS)}, and cam, the Grad-CAM map of the "
            "log-odds of cancer on the last 7x7 feature map."
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        onnx.save(model, str(args.out))

    errors = check(net, args.out)
    int8 = check_int8(full, args.out)
    data = args.out.read_bytes()
    manifest = {
        "file": args.out.name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "source": {
            "repo": HF_REPO,
            "revision": HF_REVISION,
            "weights": HF_WEIGHTS,
            "license": "MIT",
        },
        "weights": {
            "int8": f"{len(stored)} convolutions, in blocks of {GROUP} values with a float32 scale",
            "float32": f"{', '.join(KEEP_FLOAT)}, the biases (BatchNorm folded in), and the head",
            "check": int8,
        },
        "inputs": {"image": [None, 3, CROP_SIZE, CROP_SIZE]},
        "outputs": {"logits": [None, len(LABELS)], "cam": [None, 7, 7]},
        "labels": list(LABELS),
        "preprocessing": {
            "steps": ["resize 250x250 bilinear", "resize 256x256 bilinear", "center crop 224"],
            "mean": MEAN.tolist(),
            "std": STD.tolist(),
        },
        "exported_with": {
            "torch": torch.__version__,
            "onnx": onnx.__version__,
            "opset": OPSET,
            "python": platform.python_version(),
        },
        "check": errors,
    }
    args.out.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {args.out} ({len(data) / 1e6:.1f} MB), sha256 {manifest['sha256'][:12]}")
    print(
        f"Largest difference from PyTorch: logits {errors['logits']:.2e}, cam {errors['cam']:.2e}"
    )
    print(
        f"Int8 weights: {len(stored)} convolutions; on {int8['slices']} sample slices, the "
        f"cancer probability moves by at most {int8['largest_cancer_probability_change']:.4f}"
    )


if __name__ == "__main__":
    main()
