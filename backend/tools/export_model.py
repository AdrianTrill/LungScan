"""Export the classifier to ONNX, with its Grad-CAM output, and check the export.

    cd backend
    pip install -r requirements-model.txt
    python -m tools.export_model            # writes ../model/lungscan.onnx and lungscan.json

The weights come from Hugging Face, pinned to one revision. Before the manifest is
written, the export is checked twice: ONNX Runtime must reproduce PyTorch's logits, and
the Grad-CAM the graph computes must match the one autograd computes.
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
from app.services.model import CROP_SIZE, LABELS, MEAN, STD
from tools.network import ExplainedNet, LungCancerNet, autograd_cam

HF_REPO = "dorsar/lung-cancer-detection"
HF_REVISION = "aa7426d75fbc0567fc6f0b36d47776fefae103f1"
HF_WEIGHTS = "Model/lung_cancer_detection_model.pth"
OPSET = 17


def load_net() -> LungCancerNet:
    path = hf_hub_download(HF_REPO, HF_WEIGHTS, revision=HF_REVISION)
    net = LungCancerNet(len(LABELS))
    net.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    return net.eval()


def check(net: LungCancerNet, onnx_path: Path) -> dict:
    """Compare the ONNX file with PyTorch on random inputs; return the largest errors."""
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=REPO_DIR / "model" / "lungscan.onnx")
    args = parser.parse_args()

    net = load_net()
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
        onnx.checker.check_model(model)
        model.doc_string = (
            f"{HF_REPO}@{HF_REVISION} (MIT). Outputs: logits over {list(LABELS)}, and cam, "
            "the Grad-CAM map of the log-odds of cancer on the last 7x7 feature map."
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        onnx.save(model, str(args.out))

    errors = check(net, args.out)
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


if __name__ == "__main__":
    main()
