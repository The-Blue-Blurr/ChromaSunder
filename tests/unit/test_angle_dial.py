from __future__ import annotations

import math

import pytest

from chromasunder.gui.angle_dial import angle_from_point, normalize_angle, point_for_angle


@pytest.mark.parametrize(
    ("angle", "expected"),
    ((0, 0), (90, 90), (360, 0), (-90, 270), (450, 90)),
)
def test_normalize_angle(angle, expected):
    assert normalize_angle(angle) == expected


def test_normalize_angle_can_preserve_an_entered_full_turn():
    assert normalize_angle(360, preserve_full_turn=True) == 360
    assert normalize_angle(720, preserve_full_turn=True) == 360
    assert normalize_angle(0, preserve_full_turn=True) == 0


@pytest.mark.parametrize(
    ("point", "expected"),
    (((20, 10), 0), ((10, 0), 90), ((0, 10), 180), ((10, 20), 270)),
)
def test_angle_from_cardinal_point(point, expected):
    assert angle_from_point(*point, 10, 10) == expected


@pytest.mark.parametrize("angle", (0, 45, 90, 180, 270, 359, 360))
def test_point_conversion_round_trips(angle):
    point = point_for_angle(angle, 50, 50, 25)
    converted = angle_from_point(*point, 50, 50)
    assert math.isclose(converted, angle % 360, abs_tol=1e-9)
