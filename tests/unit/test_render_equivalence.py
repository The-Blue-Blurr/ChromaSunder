from __future__ import annotations

import hashlib

import pytest
from PIL import Image

from chromasunder.core.models import PixelSortSettings
from chromasunder.core.processing import process_image
from tests.reference_renderer import reference_process_image

INTERVAL_MODES = ("none", "threshold", "edges", "random", "waves", "file", "file-edges")
SORTING_MODES = ("lightness", "hue", "saturation", "intensity", "minimum")
ANGLES = (0, 90, 180, 270, 45, 315)
MASK_KINDS = ("none", "alternating", "sparse", "dense", "all-enabled", "all-disabled")


def asymmetric_image(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size)
    image.putdata(
        [
            (
                (x * 73 + y * 19) % 256,
                (x * 29 + y * 101) % 256,
                ((x // 2) * 53 + y * 41) % 256,
                (x * 47 + y * 67) % 256,
            )
            for y in range(height)
            for x in range(width)
        ]
    )
    return image


def matrix_image() -> Image.Image:
    image = asymmetric_image((7, 5))
    image.putpixel((0, 0), (0, 0, 0, 0))
    image.putpixel((1, 0), (255, 255, 255, 255))
    image.putpixel((2, 0), (255, 0, 0, 64))
    image.putpixel((3, 0), (0, 255, 0, 128))
    image.putpixel((4, 0), (0, 0, 255, 192))
    image.putpixel((5, 0), (20, 40, 60, 32))
    image.putpixel((6, 0), (60, 40, 20, 224))
    return image


def binary_fixture(kind: str) -> Image.Image | None:
    if kind == "none":
        return None
    image = Image.new("1", (7, 5), 0)
    for y in range(image.height):
        for x in range(image.width):
            enabled = {
                "alternating": (x + y) % 2 == 0,
                "sparse": (x + y * image.width) % 7 == 0,
                "dense": (x + y * image.width) % 7 != 0,
                "all-enabled": True,
                "all-disabled": False,
            }[kind]
            image.putpixel((x, y), int(enabled))
    return image


def interval_fixture(kind: str = "stripes") -> Image.Image:
    image = Image.new("1", (7, 5), 0)
    for y in range(image.height):
        for x in range(image.width):
            enabled = {
                "black": False,
                "white": True,
                "alternating": (x + y) % 2 == 0,
                "stripes": x in (1, 2, 5, 6),
                "gradient": x >= 3,
            }[kind]
            image.putpixel((x, y), int(enabled))
    return image


def assert_reference_equal(
    source: Image.Image,
    settings: PixelSortSettings,
    *,
    mask: Image.Image | None = None,
    interval_image: Image.Image | None = None,
) -> None:
    expected = reference_process_image(source, settings, mask=mask, interval_image=interval_image)
    actual = process_image(source, settings, mask=mask, interval_image=interval_image)
    try:
        assert actual.mode == expected.mode
        assert actual.size == expected.size
        assert actual.tobytes() == expected.tobytes()
    finally:
        expected.close()
        actual.close()


@pytest.mark.parametrize("size", [(1, 1), (2, 1), (3, 2), (7, 5), (16, 9)])
def test_initial_asymmetric_reference_cases(size):
    source = asymmetric_image(size)
    try:
        assert_reference_equal(
            source,
            PixelSortSettings(interval_function="none", sorting_function="lightness", seed=19),
        )
    finally:
        source.close()


def test_initial_golden_render_bytes():
    source = asymmetric_image((7, 5))
    rendered = process_image(
        source,
        PixelSortSettings(interval_function="none", sorting_function="lightness", seed=19),
    )
    try:
        assert hashlib.sha256(rendered.tobytes()).hexdigest() == (
            "6d531cb901809fbc43671d434f380aca1dc07c7152a1b69a112c6c025943d5ef"
        )
    finally:
        rendered.close()
        source.close()


@pytest.mark.parametrize("interval_mode", INTERVAL_MODES)
@pytest.mark.parametrize("sorting_mode", SORTING_MODES)
@pytest.mark.parametrize("angle", ANGLES)
@pytest.mark.parametrize("mask_kind", MASK_KINDS)
def test_full_reference_equivalence_matrix(interval_mode, sorting_mode, angle, mask_kind):
    source = matrix_image()
    mask = binary_fixture(mask_kind)
    interval = interval_fixture() if interval_mode in {"file", "file-edges"} else None
    try:
        assert_reference_equal(
            source,
            PixelSortSettings(
                interval_function=interval_mode,
                sorting_function=sorting_mode,
                lower_threshold=0.2,
                upper_threshold=0.8,
                characteristic_length=3,
                randomness=25,
                angle=angle,
                seed=8675309,
            ),
            mask=mask,
            interval_image=interval,
        )
    finally:
        source.close()
        if mask is not None:
            mask.close()
        if interval is not None:
            interval.close()


@pytest.mark.parametrize("interval_mode", ["file", "file-edges"])
@pytest.mark.parametrize("kind", ["black", "white", "alternating", "stripes", "gradient"])
def test_interval_image_reference_cases(interval_mode, kind):
    source = matrix_image()
    interval = interval_fixture(kind)
    try:
        assert_reference_equal(
            source,
            PixelSortSettings(
                interval_function=interval_mode,
                sorting_function="lightness",
                lower_threshold=0.5,
                seed=23,
            ),
            interval_image=interval,
        )
    finally:
        interval.close()
        source.close()


@pytest.mark.parametrize("interval_mode", ["random", "waves"])
def test_seeded_modes_repeat_reference_rng_sequence(interval_mode):
    source = matrix_image()
    settings = PixelSortSettings(
        interval_function=interval_mode,
        characteristic_length=3,
        randomness=50,
        seed=31,
    )
    try:
        assert_reference_equal(source, settings)
        assert_reference_equal(source, settings)
    finally:
        source.close()
