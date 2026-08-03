from __future__ import annotations

import hashlib

import pytest
from PIL import Image

from chromasunder.core.models import PixelSortSettings
from chromasunder.core.processing import process_image
from tests.reference_renderer import reference_process_image


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
