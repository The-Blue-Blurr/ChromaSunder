"""Frozen pre-V1.3 renderer used only for byte-equivalence tests.

Keep this implementation mechanically equivalent to the renderer that shipped
before the V1.3 performance work. It intentionally duplicates production code.
"""

from __future__ import annotations

import colorsys
import math
import random
from collections.abc import Callable, Sequence

from PIL import Image

from chromasunder.core.enums import IntervalFunction, SortingFunction
from chromasunder.core.models import PixelSortSettings
from chromasunder.core.validation import ValidationError, validate_settings


class ReferenceRenderCancelled(Exception):
    pass


ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]


def _sorting_key(pixel: Sequence[int], function: SortingFunction | str) -> float:
    selected = SortingFunction(function)
    red, green, blue = (channel / 255.0 for channel in pixel[:3])
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    if selected is SortingFunction.LIGHTNESS:
        return lightness
    if selected is SortingFunction.HUE:
        return hue
    if selected is SortingFunction.SATURATION:
        return saturation
    if selected is SortingFunction.INTENSITY:
        return (red + green + blue) / 3.0
    if selected is SortingFunction.MINIMUM:
        return min(red, green, blue)
    raise ValueError(f"Unsupported sorting function: {function}")


def _luminance(pixel: Sequence[int]) -> float:
    return _sorting_key(pixel, "lightness")


def _runs(flags: Sequence[bool], *, minimum_length: int = 2) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    start: int | None = None
    for index, enabled in enumerate(flags):
        if enabled and start is None:
            start = index
        elif not enabled and start is not None:
            if index - start >= minimum_length:
                intervals.append((start, index))
            start = None
    if start is not None and len(flags) - start >= minimum_length:
        intervals.append((start, len(flags)))
    return intervals


def _detect_intervals(
    row: Sequence[Sequence[int]],
    function: IntervalFunction | str,
    lower_threshold: float,
    upper_threshold: float,
    characteristic_length: int,
    rng: random.Random,
    interval_row: Sequence[int] | None = None,
) -> list[tuple[int, int]]:
    selected = IntervalFunction(function)
    if selected is IntervalFunction.THRESHOLD:
        return _runs([lower_threshold <= _luminance(pixel) <= upper_threshold for pixel in row])
    if selected is IntervalFunction.EDGES:
        if len(row) < 2:
            return []
        boundaries = [0]
        previous = _luminance(row[0])
        for index in range(1, len(row)):
            current = _luminance(row[index])
            if abs(current - previous) >= lower_threshold:
                boundaries.append(index)
            previous = current
        boundaries.append(len(row))
        return [
            (start, end)
            for start, end in zip(boundaries, boundaries[1:], strict=False)
            if end - start >= 2
        ]
    if selected is IntervalFunction.RANDOM:
        intervals = []
        start = 0
        while start < len(row):
            size = max(1, int(characteristic_length * rng.random()))
            end = min(len(row), start + size)
            if end - start >= 2:
                intervals.append((start, end))
            start = end
        return intervals
    if selected is IntervalFunction.WAVES:
        intervals = []
        start = 0
        while start < len(row):
            end = min(len(row), start + characteristic_length + rng.randint(0, 10))
            if end - start >= 2:
                intervals.append((start, end))
            start = end
        return intervals
    if selected is IntervalFunction.NONE:
        return [(0, len(row))] if len(row) >= 2 else []
    if selected is IntervalFunction.FILE:
        return _runs([bool(value) for value in (interval_row or ())])
    if selected is IntervalFunction.FILE_EDGES:
        values = [1.0 if value else 0.0 for value in (interval_row or ())]
        if not values:
            return []
        boundaries = [0]
        previous = 0.0
        for index, current in enumerate(values):
            if abs(current - previous) >= lower_threshold:
                boundaries.append(index)
            previous = current
        boundaries.append(len(values))
        boundaries = list(dict.fromkeys(boundaries))
        return [
            (start, end)
            for start, end in zip(boundaries, boundaries[1:], strict=False)
            if end - start >= 2
        ]
    raise ValueError(f"Unsupported interval function: {function}")


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
    source_row: Sequence[tuple[int, int, int, int]],
    output_pixels,
    y: int,
    intervals: list[tuple[int, int]],
    mask_row: Sequence[int] | None,
    settings: PixelSortSettings,
    rng: random.Random,
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
            key=lambda pixel: _sorting_key(pixel, settings.sorting_function),
        )
        for index, pixel in zip(positions, sorted_pixels, strict=True):
            output_pixels[index, y] = pixel


def reference_process_image(
    source: Image.Image,
    settings: PixelSortSettings,
    *,
    mask: Image.Image | None = None,
    interval_image: Image.Image | None = None,
    rng: random.Random | None = None,
    cancel: CancelCallback | None = None,
    progress: ProgressCallback | None = None,
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
    generator = rng or random.Random(settings.seed)
    output = working_source.copy()
    source_pixels = working_source.load()
    output_pixels = output.load()
    mask_pixels = working_mask.load() if working_mask is not None else None
    interval_pixels = working_interval.load() if working_interval is not None else None
    total_rows = working_source.height
    for y in range(total_rows):
        if cancel is not None and cancel():
            raise ReferenceRenderCancelled
        row = [source_pixels[x, y] for x in range(working_source.width)]
        mask_row = [mask_pixels[x, y] for x in range(working_source.width)] if mask_pixels else None
        interval_row = (
            [interval_pixels[x, y] for x in range(working_source.width)]
            if interval_pixels
            else None
        )
        intervals = _detect_intervals(
            row,
            settings.interval_function,
            settings.lower_threshold,
            settings.upper_threshold,
            settings.characteristic_length,
            generator,
            interval_row,
        )
        _sort_row(row, output_pixels, y, intervals, mask_row, settings, generator)
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
