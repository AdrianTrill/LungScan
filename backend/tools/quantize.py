"""Store the classifier's convolution weights as int8, in blocks that each have a scale.

Convolution weights are nearly all of the file. Each output channel's weights are split
into blocks of GROUP consecutive values, and each block is stored as int8 with one
float32 scale, so that its largest magnitude maps to 127: block-wise quantization, as is
common for the weights of large language models. The stem and layer 1 stay in float32.
They hold under 1% of the weights, but rounding them causes most of the error.

In the ONNX file, each of these weights is Reshape(Cast(int8 blocks) * scales). Every
input to those nodes is a constant, so ONNX Runtime folds them back into float32 weights
when it loads the file, on the server and in the browser alike. The network then runs in
float32, exactly as PyTorch runs it with the rounded weights.
"""

import copy
import hashlib
from dataclasses import dataclass

import numpy as np
import onnx
import torch
from onnx import TensorProto, helper, numpy_helper
from torch import nn
from torch.nn.utils.fusion import fuse_conv_bn_eval

from tools.network import LungCancerNet

GROUP = 32
KEEP_FLOAT = ("resnet.conv1", "resnet.layer1")


@dataclass
class Int8Weight:
    values: np.ndarray  # int8, (out channels, blocks, GROUP)
    scales: np.ndarray  # float32, (out channels, blocks, 1)
    shape: tuple[int, ...]


def fuse_batchnorm(net: LungCancerNet) -> LungCancerNet:
    """A copy of the network with each BatchNorm folded into the convolution before it."""
    net = copy.deepcopy(net).eval()
    r = net.resnet
    r.conv1, r.bn1 = fuse_conv_bn_eval(r.conv1, r.bn1), nn.Identity()
    for layer in (r.layer1, r.layer2, r.layer3, r.layer4):
        for block in layer:
            for i in (1, 2, 3):
                conv, bn = getattr(block, f"conv{i}"), getattr(block, f"bn{i}")
                setattr(block, f"conv{i}", fuse_conv_bn_eval(conv, bn))
                setattr(block, f"bn{i}", nn.Identity())
            if block.downsample is not None:
                conv, bn = block.downsample
                block.downsample = nn.Sequential(fuse_conv_bn_eval(conv, bn))
    return net


def _digest(weight: np.ndarray) -> bytes:
    return hashlib.sha256(np.ascontiguousarray(weight, dtype=np.float32).tobytes()).digest()


def quantize_convolutions(
    net: nn.Module, group: int = GROUP, keep: tuple[str, ...] = KEEP_FLOAT
) -> dict[bytes, Int8Weight]:
    """Round the weights of the convolutions outside `keep` to int8 blocks, in place.

    Returns the int8 form of each rounded weight, keyed by a hash of its float32 values,
    so that store_int8 can find the same tensors in the exported graph.
    """
    stored = {}
    for name, module in net.named_modules():
        if not isinstance(module, nn.Conv2d):
            continue
        if any(name == k or name.startswith(k + ".") for k in keep):
            continue
        weight = module.weight.data
        rows = weight.reshape(weight.shape[0], -1)
        if rows.shape[1] % group:
            raise ValueError(
                f"{name}: {rows.shape[1]} weights per channel are not blocks of {group}"
            )
        blocks = rows.reshape(weight.shape[0], -1, group)
        scales = blocks.abs().amax(dim=2, keepdim=True) / 127
        scales = scales.clamp(min=torch.finfo(torch.float32).tiny)
        values = torch.round(blocks / scales).clamp(-127, 127).to(torch.int8)
        module.weight.data = (values.to(torch.float32) * scales).reshape(weight.shape)
        stored[_digest(module.weight.data.numpy())] = Int8Weight(
            values.numpy(), scales.numpy(), tuple(weight.shape)
        )
    return stored


def store_int8(model: onnx.ModelProto, stored: dict[bytes, Int8Weight]) -> int:
    """Replace the rounded convolution weights in an exported graph with their int8 form.

    Returns how many weights were replaced.
    """
    graph = model.graph
    initializers = {tensor.name: tensor for tensor in graph.initializer}
    nodes = []
    for name in dict.fromkeys(node.input[1] for node in graph.node if node.op_type == "Conv"):
        tensor = initializers.get(name)
        int8 = stored.get(_digest(numpy_helper.to_array(tensor))) if tensor is not None else None
        if int8 is None:
            continue
        graph.initializer.remove(tensor)
        graph.initializer.extend(
            [
                numpy_helper.from_array(int8.values, f"{name}.int8"),
                numpy_helper.from_array(int8.scales, f"{name}.scale"),
                numpy_helper.from_array(np.array(int8.shape, dtype=np.int64), f"{name}.shape"),
            ]
        )
        nodes += [
            helper.make_node("Cast", [f"{name}.int8"], [f"{name}.blocks"], to=TensorProto.FLOAT),
            helper.make_node("Mul", [f"{name}.blocks", f"{name}.scale"], [f"{name}.scaled"]),
            helper.make_node("Reshape", [f"{name}.scaled", f"{name}.shape"], [name]),
        ]
    rest = list(graph.node)
    del graph.node[:]
    graph.node.extend(nodes + rest)
    return len(nodes) // 3
