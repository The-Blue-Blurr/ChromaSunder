"""Full-resolution row-streaming pixel sorting."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence

from PIL import Image

from .enums import IntervalFunction
from .imaging import normalize_binary_image, normalize_image
from .intervals import detect_intervals
from .models import PixelSortSettings
from .sorting import SortingKey, sorting_key_function
from .validation import ValidationError, validate_settings


class RenderCancelled(Exception):
    """Raised when a cooperative render cancellation callback requests a stop."""


ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]


class _PixelAccessRows:
    """Private row storage boundary backed by Pillow PixelAccess objects."""

    def __init__(
        self,
        source: Image.Image,
        output: Image.Image,
        mask: Image.Image | None,
        interval_image: Image.Image | None,
    ) -> None:
        self.width = source.width
        self.source_pixels = source.load()
        self.output_pixels = output.load()
        self.mask_pixels = mask.load() if mask is not None else None
        self.interval_pixels = interval_image.load() if interval_image is not None else None

    def read_source(self, y: int) -> list[tuple[int, int, int, int]]:
        return [self.source_pixels[x, y] for x in range(self.width)]

    def read_mask(self, y: int) -> list[int] | None:
        if self.mask_pixels is None:
            return None
        return [self.mask_pixels[x, y] for x in range(self.width)]

    def read_interval(self, y: int) -> list[int] | None:
        if self.interval_pixels is None:
            return None
        return [self.interval_pixels[x, y] for x in range(self.width)]

    def commit(
        self,
        y: int,
        positions: list[int],
        pixels: list[tuple[int, int, int, int]],
    ) -> None:
        for index, pixel in zip(positions, pixels, strict=True):
            self.output_pixels[index, y] = pixel


def _rotation_size(size: tuple[int, int], angle: float) -> tuple[int, int]:
    radians = math.radians(angle % 180)
    width, height = size
    expanded_width = abs(width * math.cos(radians)) + abs(height * math.sin(radians))
    expanded_height = abs(width * math.sin(radians)) + abs(height * math.cos(radians))
    result = max(1, math.ceil(expanded_width)), max(1, math.ceil(expanded_height))
    if result[0] * result[1] > 200_000_000 or max(result) > 20_000:
        raise ValidationError(
            "This rotation would require an unreasonably large working image.",
            category="out-of-memory",
        )
    return result


def _rotate(image: Image.Image, angle: float, *, binary: bool = False) -> Image.Image:
    if abs(angle) < 1e-9 or abs(angle) % 360 < 1e-9:
        return image.copy()
    _rotation_size(image.size, angle)
    return image.rotate(
        angle,
        resample=Image.Resampling.NEAREST if binary else Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=0 if binary else (0, 0, 0, 0),
    )


def _crop_center(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    width, height = size
    left = max(0, (image.width - width) // 2)
    top = max(0, (image.height - height) // 2)
    cropped = image.crop((left, top, left + width, top + height))
    if cropped.size == size:
        return cropped
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(cropped, ((width - cropped.width) // 2, (height - cropped.height) // 2))
    cropped.close()
    return canvas


def _sort_row(
    source_row: list[tuple[int, int, int, int]],
    rows: _PixelAccessRows,
    y: int,
    intervals: list[tuple[int, int]],
    mask_row: Sequence[int] | None,
    settings: PixelSortSettings,
    rng: random.Random,
    sort_key: SortingKey,
) -> None:
    for start, end in intervals:
        if settings.randomness and rng.random() * 100.0 < settings.randomness:
            continue
        positions = [
            index for index in range(start, end) if mask_row is None or mask_row[index] > 0
        ]
        if len(positions) < 2:
            continue
        sorted_pixels = sorted(
            (source_row[index] for index in positions),
            key=sort_key,
        )
        rows.commit(y, positions, sorted_pixels)


def process_image(
    source: Image.Image,
    settings: PixelSortSettings,
    *,
    mask: Image.Image | None = None,
    interval_image: Image.Image | None = None,
    rng: random.Random | None = None,
    cancel: CancelCallback | None = None,
    progress: ProgressCallback | None = None,
) -> Image.Image:
    """Sort a normalized RGBA image and return a new RGBA image.

    Only one row of pixels is assembled at a time. Random state belongs to the
    render call, which makes repeated batch images reproducible.
    """

    validate_settings(settings)
    if source.mode != "RGBA":
        source = source.convert("RGBA")
    if settings.interval_function in (IntervalFunction.FILE, IntervalFunction.FILE_EDGES):
        if interval_image is None:
            raise ValidationError(
                "An interval image is required for the selected interval function.",
                "missing-interval-image",
            )
    original_size = source.size
    angle = settings.angle
    working_source = _rotate(source, -angle)
    working_mask = _rotate(mask, -angle, binary=True) if mask is not None else None
    working_interval = (
        _rotate(interval_image, -angle, binary=True) if interval_image is not None else None
    )
    if working_mask is not None and working_mask.size != working_source.size:
        working_source.close()
        working_mask.close()
        if working_interval is not None:
            working_interval.close()
        raise ValidationError(
            "Rotating the mask produced dimensions that do not match the source image.",
            "dimension-mismatch",
        )
    if working_interval is not None and working_interval.size != working_source.size:
        working_source.close()
        if working_mask is not None:
            working_mask.close()
        working_interval.close()
        raise ValidationError(
            "Rotating the interval image produced dimensions that do not match the source image.",
            "dimension-mismatch",
        )
    generator = rng or random.Random(settings.seed)
    sort_key = sorting_key_function(settings.sorting_function)
    output = working_source.copy()
    rows = _PixelAccessRows(working_source, output, working_mask, working_interval)
    total_rows = working_source.height
    for y in range(total_rows):
        if cancel is not None and cancel():
            raise RenderCancelled
        row = rows.read_source(y)
        mask_row = rows.read_mask(y)
        interval_row = rows.read_interval(y)
        intervals = detect_intervals(
            row,
            settings.interval_function,
            settings.lower_threshold,
            settings.upper_threshold,
            settings.characteristic_length,
            generator,
            interval_row,
        )
        _sort_row(row, rows, y, intervals, mask_row, settings, generator, sort_key)
        if progress is not None:
            progress(y + 1, total_rows)

    working_source.close()
    if working_mask is not None:
        working_mask.close()
    if working_interval is not None:
        working_interval.close()
    if abs(angle) >= 1e-9 and abs(angle) % 360 >= 1e-9:
        restored = _rotate(output, angle)
        output.close()
        output = _crop_center(restored, original_size)
        restored.close()
    return output


def render_file(
    source_path: str,
    settings: PixelSortSettings,
    *,
    mask_path: str | None = None,
    interval_path: str | None = None,
    cancel: CancelCallback | None = None,
    progress: ProgressCallback | None = None,
) -> Image.Image:
    """Normalize selected files and render one image."""

    source = normalize_image(source_path)
    mask = None
    interval_image = None
    try:
        if mask_path:
            mask = normalize_binary_image(mask_path, source.dimensions)
        if interval_path:
            interval_image = normalize_binary_image(interval_path, source.dimensions)
        return process_image(
            source.image,
            settings,
            mask=mask,
            interval_image=interval_image,
            cancel=cancel,
            progress=progress,
        )
    finally:
        source.image.close()
        if mask is not None:
            mask.close()
        if interval_image is not None:
            interval_image.close()
