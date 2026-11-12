"""Tests for turning the network's output into a read."""

import math

import numpy as np
import pytest

from app.services.analysis import (
    interpret,
    percent,
    position,
    probability,
    round_half_up,
    softmax,
)
from app.services.model import GRID, RawOutput


def raw(logits, cam=None, width=256, height=256):
    if cam is None:
        cam = np.zeros((GRID, GRID), dtype=np.float32)
    return RawOutput(np.array(logits, np.float32), np.asarray(cam, np.float32), width, height, 5.0)


def test_rounding_is_half_up():
    assert round_half_up(0.125, 2) == 0.13
    assert round_half_up(2.5) == 3
    assert percent(0.0005) == "0.1%"
    assert percent(1.0) == "100.0%"


def test_probabilities_never_round_to_certainty():
    assert probability(0.99969) == ">99.9%"
    assert probability(0.9994) == "99.9%"
    assert probability(0.0001) == "<0.1%"
    assert probability(0.0) == "0.0%"


def test_softmax_sums_to_one():
    p = softmax([1.0, 2.0, 3.0, 4.0])
    assert math.isclose(sum(p), 1.0)
    assert p == sorted(p)


def test_a_normal_read_has_no_regions():
    cam = np.ones((GRID, GRID))
    result = interpret(raw([0, 0, 5, 0], cam), "c", "s", "r")
    assert not result.flagged
    assert result.subtype is None
    assert result.predicted_class == "normal"
    assert result.regions == []
    assert result.summary.endswith("the model reads this slice as normal.")
    assert result.cancer_probability == pytest.approx(
        3 * math.exp(-5) / (1 + 3 * math.exp(-5)), abs=1e-6
    )
    # The heat map fades with the cancer probability.
    assert max(result.heatmap.values) == pytest.approx(result.cancer_probability, abs=1e-4)


def test_the_cancer_probability_sums_the_three_cancer_classes():
    result = interpret(raw([1.0, 0.0, 0.0, 1.0]), "c", "s", "r")
    p = softmax([1.0, 0.0, 0.0, 1.0])
    assert result.cancer_probability == pytest.approx(p[0] + p[1] + p[3], abs=1e-6)
    assert result.flagged
    # Ties go to the first class, as in the browser.
    assert result.subtype == "adenocarcinoma"


def test_regions_follow_the_peaks_of_the_map():
    cam = np.zeros((GRID, GRID))
    cam[1, 1] = 1.0
    cam[2, 2] = 0.8  # diagonal neighbor: same region
    cam[5, 5] = 0.7
    cam[5, 6] = 0.4  # below half the peak: not part of a region
    result = interpret(raw([0, 4, 0, 0], cam), "c", "s", "r")
    assert [r.cells for r in result.regions] == [2, 1]
    first, second = result.regions
    assert first.id == "r1" and first.evidence == pytest.approx(result.cancer_probability, abs=1e-4)
    gx = (1.0 * 1.5 + 0.8 * 2.5) / 1.8
    assert first.x == math.floor(16 + gx * 32 + 0.5)
    assert first.y == first.x
    assert first.radius == math.floor(math.sqrt(2 / math.pi) * 32 + 0.5)
    assert second.x == second.y == 16 + 5 * 32 + 16
    assert "upper left" in first.explanation
    assert "lower right" in second.explanation
    assert "2 regions" in result.summary


def test_regions_scale_to_the_original_image():
    cam = np.zeros((GRID, GRID))
    cam[3, 3] = 1.0
    result = interpret(raw([0, 4, 0, 0], cam, width=512, height=1024), "c", "s", "r")
    (region,) = result.regions
    assert (region.x, region.y) == (256, 512)
    box = result.heatmap.box
    assert (box.x, box.y, box.width, box.height) == (32, 64, 448, 896)
    assert "center of the image" in region.explanation


def test_at_most_three_regions():
    cam = np.zeros((GRID, GRID))
    for i, (a, b) in enumerate([(0, 0), (0, 6), (6, 0), (6, 6), (3, 3)]):
        cam[a, b] = 1.0 - i * 0.05
    result = interpret(raw([0, 4, 0, 0], cam), "c", "s", "r")
    assert len(result.regions) == 3
    assert [r.evidence for r in result.regions] == sorted(
        (r.evidence for r in result.regions), reverse=True
    )


def test_position_names_the_thirds_of_the_grid():
    assert position(0.5, 0.5) == "upper left"
    assert position(3.5, 3.5) == "center"
    assert position(6.9, 3.5) == "middle right"
    assert position(3.5, 6.9) == "lower center"
