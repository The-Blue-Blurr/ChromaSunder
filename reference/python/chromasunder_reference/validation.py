import math

from .models import PixelSortSettings


class ValidationError(ValueError):
    def __init__(self, message: str, category: str = "validation") -> None:
        super().__init__(message)
        self.category = category


def validate_settings(settings: PixelSortSettings) -> None:
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
