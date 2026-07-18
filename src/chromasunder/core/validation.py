"""Validation shared by UI preflight and worker execution."""

from __future__ import annotations

import math
from collections.abc import Iterable
from pathlib import Path

from .enums import IntervalFunction, SortingFunction
from .models import PixelSortSettings


class ValidationError(ValueError):
    """A user-correctable input or settings error."""

    def __init__(self, message: str, category: str = "validation") -> None:
        super().__init__(message)
        self.category = category


def validate_settings(settings: PixelSortSettings) -> None:
    try:
        IntervalFunction(settings.interval_function)
        SortingFunction(settings.sorting_function)
    except ValueError as exc:
        raise ValidationError("The selected processing function is not supported.") from exc

    numbers = (
        ("lower threshold", settings.lower_threshold, 0.0, 1.0),
        ("upper threshold", settings.upper_threshold, 0.0, 1.0),
        ("randomness", settings.randomness, 0.0, 100.0),
    )
    for label, value, low, high in numbers:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValidationError(f"The {label} must be finite.")
        if not low <= float(value) <= high:
            raise ValidationError(f"The {label} must be between {low} and {high}.")
    if settings.lower_threshold > settings.upper_threshold:
        raise ValidationError("The lower threshold cannot exceed the upper threshold.")
    if not isinstance(settings.characteristic_length, int) or settings.characteristic_length < 1:
        raise ValidationError("The characteristic length must be at least 1.")
    if not isinstance(settings.seed, int) or settings.seed < 0:
        raise ValidationError("The seed must be a nonnegative integer.")
    if not math.isfinite(float(settings.angle)):
        raise ValidationError("The angle must be finite.")


def require_existing_file(path: str | None, label: str) -> Path | None:
    if path is None or path == "":
        return None
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        raise ValidationError(f"The selected {label} does not exist or is not a file.")
    return candidate


def validate_dimensions(
    source_dimensions: tuple[int, int],
    auxiliary_dimensions: Iterable[tuple[int, int] | None],
) -> None:
    for dimensions in auxiliary_dimensions:
        if dimensions is not None and dimensions != source_dimensions:
            raise ValidationError(
                "The mask and interval image must match the source image dimensions.",
                category="dimension-mismatch",
            )


def validate_render_configuration(
    settings: PixelSortSettings,
    source_path: str | None,
    mask_path: str | None = None,
    interval_path: str | None = None,
) -> None:
    validate_settings(settings)
    require_existing_file(source_path, "source image")
    require_existing_file(mask_path, "mask image")
    require_existing_file(interval_path, "interval image")
    if settings.interval_function in (IntervalFunction.FILE, IntervalFunction.FILE_EDGES):
        if not interval_path:
            raise ValidationError(
                "An interval image is required for the selected interval function.",
                category="missing-interval-image",
            )
