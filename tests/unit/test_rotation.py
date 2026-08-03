from __future__ import annotations

import pytest
from PIL import Image

from chromasunder.core.models import PixelSortSettings
from chromasunder.core.processing import _crop_center, _rotate, process_image


def unique_rgba(size: tuple[int, int] = (3, 2)) -> Image.Image:
    image = Image.new("RGBA", size)
    image.putdata(
        [
            (10, 20, 30, 0),
            (40, 50, 60, 51),
            (70, 80, 90, 102),
            (100, 110, 120, 153),
            (130, 140, 150, 204),
            (160, 170, 180, 255),
        ]
    )
    return image


@pytest.mark.parametrize(
    ("angle", "transpose"),
    [
        (90, Image.Transpose.ROTATE_90),
        (180, Image.Transpose.ROTATE_180),
        (270, Image.Transpose.ROTATE_270),
        (-90, Image.Transpose.ROTATE_270),
        (450, Image.Transpose.ROTATE_90),
    ],
)
def test_exact_right_angles_match_pillow_transpose(angle, transpose):
    source = unique_rgba()
    expected = source.transpose(transpose)
    actual = _rotate(source, angle)
    try:
        assert actual.mode == "RGBA"
        assert actual.size == expected.size
        assert actual.tobytes() == expected.tobytes()
    finally:
        actual.close()
        expected.close()
        source.close()


def test_full_turn_is_an_exact_copy():
    source = unique_rgba()
    actual = _rotate(source, 360)
    try:
        assert actual is not source
        assert actual.size == source.size
        assert actual.tobytes() == source.tobytes()
    finally:
        actual.close()
        source.close()


@pytest.mark.parametrize("angle", [90, 180, 270, -90, 360, 450])
def test_right_angle_forward_and_inverse_preserve_coordinates_and_alpha(angle):
    source = unique_rgba()
    forward = _rotate(source, -angle)
    inverse = _rotate(forward, angle)
    restored = _crop_center(inverse, source.size)
    try:
        assert restored.size == source.size
        assert restored.mode == "RGBA"
        assert restored.tobytes() == source.tobytes()
    finally:
        restored.close()
        inverse.close()
        forward.close()
        source.close()


@pytest.mark.parametrize("kind", ["mask", "interval"])
@pytest.mark.parametrize("angle", [90, 180, 270])
def test_asymmetric_binary_auxiliary_rotation_matches_source(kind, angle):
    source = unique_rgba()
    binary = Image.new("1", source.size, 0)
    binary.putpixel((0, 0), 1)
    binary.putpixel((2, 1), 1)
    settings = PixelSortSettings(
        interval_function="file" if kind == "interval" else "none",
        angle=angle,
        seed=5,
    )
    kwargs = {"mask": binary} if kind == "mask" else {"interval_image": binary}
    rendered = process_image(source, settings, **kwargs)
    try:
        assert rendered.size == source.size
        assert rendered.mode == "RGBA"
    finally:
        rendered.close()
        binary.close()
        source.close()
