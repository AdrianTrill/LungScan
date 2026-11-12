"""The classifier in PyTorch, and the wrapper that adds Grad-CAM to its forward pass."""

import torch
from torch import nn
from torchvision import models

from app.services.model import CANCER, NORMAL


class LungCancerNet(nn.Module):
    """ResNet-50 with a two-layer head, laid out like the published checkpoint."""

    def __init__(self, num_classes: int = 4):
        super().__init__()
        self.resnet = models.resnet50(weights=None)
        in_features = self.resnet.fc.in_features
        self.resnet.fc = nn.Identity()
        self.fc = nn.Sequential(
            nn.Linear(in_features, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        return self.fc(self.resnet(x))


class ExplainedNet(nn.Module):
    """Returns the logits and a Grad-CAM map of the log-odds of cancer, in one pass.

    The score is s = logsumexp(cancer logits) - normal logit. Its gradient with respect
    to the pooled features is the classifier head's Jacobian, which the graph computes
    directly: the head is two linear layers around a ReLU. Global average pooling makes
    that gradient the same at every location of the last feature map, so Grad-CAM's
    channel weights are this gradient divided by the number of locations. No autograd is
    needed at inference time, so ONNX Runtime Web can produce the map in the browser.
    """

    def __init__(self, net: LungCancerNet):
        super().__init__()
        r = net.resnet
        self.features = nn.Sequential(
            r.conv1, r.bn1, r.relu, r.maxpool, r.layer1, r.layer2, r.layer3, r.layer4
        )
        self.fc1 = net.fc[0]
        self.fc2 = net.fc[3]
        select = torch.zeros(len(CANCER), net.fc[3].out_features)
        for row, col in enumerate(CANCER):
            select[row, col] = 1.0
        self.register_buffer("select", select)
        normal = torch.zeros(net.fc[3].out_features)
        normal[NORMAL] = 1.0
        self.register_buffer("normal", normal)

    def forward(self, x):
        a = self.features(x)
        pooled = a.mean(dim=(2, 3))
        hidden = self.fc1(pooled)
        logits = self.fc2(torch.relu(hidden))
        weights = torch.softmax(logits @ self.select.T, dim=1)
        dlogits = weights @ self.select - self.normal
        dhidden = (dlogits @ self.fc2.weight) * (hidden > 0).to(hidden.dtype)
        dpooled = dhidden @ self.fc1.weight
        alpha = dpooled / (a.shape[2] * a.shape[3])
        cam = torch.relu((alpha[:, :, None, None] * a).sum(dim=1))
        return logits, cam


def autograd_cam(net: LungCancerNet, x: torch.Tensor) -> torch.Tensor:
    """Grad-CAM of the same score with autograd, as a reference for tests."""
    captured = {}
    hook = net.resnet.layer4.register_forward_hook(lambda m, i, o: captured.setdefault("a", o))
    try:
        logits = net(x)
        a = captured["a"]
        score = torch.logsumexp(logits[:, list(CANCER)], dim=1) - logits[:, NORMAL]
        (grad,) = torch.autograd.grad(score.sum(), a)
    finally:
        hook.remove()
    alpha = grad.mean(dim=(2, 3))
    return torch.relu((alpha[:, :, None, None] * a).sum(dim=1)).detach()
