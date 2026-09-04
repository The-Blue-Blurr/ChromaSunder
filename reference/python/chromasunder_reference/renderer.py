from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image

from .enums import IntervalFunction
from .imaging import normalize_binary_image, normalize_image
from .intervals import detect_intervals
from .models import PixelSortSettings
from .sorting import sorting_key
from .validation import ValidationError, validate_settings


def _rotation_size(size: tuple[int, int], angle: float) -> tuple[int, int]:
    radians = math.radians(angle % 180)
    width, height = size
    expanded_width = abs(width * math.cos(radians)) + abs(height * math.sin(radians))
    expanded_height = abs(width * math.sin(radians)) + abs(height * math.cos(radians))
    result = max(1, math.ceil(expanded_width)), max(1, math.ceil(expanded_height))
    if result[0] * result[1] > 200_000_000 or max(result) > 20_000:
        raise ValidationError(
            "This rotation would require an unreasonably large working image.", "out-of-memory"
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


def process_image(
    source: Image.Image,
    settings: PixelSortSettings,
    *,
    mask: Image.Image | None = None,
    interval_image: Image.Image | None = None,
) -> Image.Image:
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

    generator = random.Random(settings.seed)
    output = working_source.copy()
    source_pixels = working_source.load()
    output_pixels = output.load()
    mask_pixels = working_mask.load() if working_mask is not None else None
    interval_pixels = working_interval.load() if working_interval is not None else None
    for y in range(working_source.height):
        row = [source_pixels[x, y] for x in range(working_source.width)]
        mask_row = [mask_pixels[x, y] for x in range(working_source.width)] if mask_pixels else None
        interval_row = (
            [interval_pixels[x, y] for x in range(working_source.width)]
            if interval_pixels
            else None
        )
        intervals = detect_intervals(
            row,
            settings.interval_function,
            settings.lower_threshold,
            settings.upper_threshold,
            settings.characteristic_length,
            generator,
            interval_row,
        )
        for start, end in intervals:
            if settings.randomness and generator.random() * 100.0 < settings.randomness:
                continue
            positions = [
                index for index in range(start, end) if mask_row is None or mask_row[index] > 0
            ]
            if len(positions) < 2:
                continue
            sorted_pixels = sorted(
                (row[index] for index in positions),
                key=lambda pixel: sorting_key(pixel, settings.sorting_function),
            )
            for index, pixel in zip(positions, sorted_pixels, strict=True):
                output_pixels[index, y] = pixel

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
    source_path: str | Path,
    settings: PixelSortSettings,
    *,
    mask_path: str | Path | None = None,
    interval_path: str | Path | None = None,
) -> Image.Image:
    source = normalize_image(source_path)
    mask = normalize_binary_image(mask_path, source.size) if mask_path else None
    interval_image = normalize_binary_image(interval_path, source.size) if interval_path else None
    try:
        return process_image(source, settings, mask=mask, interval_image=interval_image)
    finally:
        source.close()
        if mask is not None:
            mask.close()
        if interval_image is not None:
            interval_image.close()
