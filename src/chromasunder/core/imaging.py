"""Image normalization and auxiliary-image loading."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

from .models import NormalizedImage
from .validation import ValidationError

SUPPORTED_FORMATS = {"PNG", "JPEG"}


def normalize_image(path: str | Path, *, auxiliary: bool = False) -> NormalizedImage:
    """Read a still image, apply orientation, and discard metadata."""

    source = Path(path).expanduser()
    try:
        with Image.open(source) as opened:
            opened.verify()
        with Image.open(source) as opened:
            image_format = (opened.format or "").upper()
            frames = getattr(opened, "n_frames", 1)
            if getattr(opened, "is_animated", False) or frames > 1:
                raise ValidationError(
                    "Animated and multipage images are not supported.",
                    category="animated-or-multipage",
                )
            oriented = ImageOps.exif_transpose(opened)
            image = oriented.convert("RGBA").copy()
    except ValidationError:
        raise
    except (OSError, ValueError) as exc:
        category = "unsupported-image" if source.exists() else "corrupt-image"
        raise ValidationError(
            f"Unable to read the {('auxiliary' if auxiliary else 'source')} image: {source.name}",
            category=category,
        ) from exc

    warning = None
    if image_format not in SUPPORTED_FORMATS:
        warning = (
            "This readable still format is experimental. PNG and JPEG are officially supported."
        )
    return NormalizedImage(image, str(source.resolve()), image_format, image.size, warning)


def normalize_binary_image(path: str | Path, dimensions: tuple[int, int]) -> Image.Image:
    """Load a black and white mask or interval image without resizing it."""

    normalized = normalize_image(path, auxiliary=True)
    if normalized.dimensions != dimensions:
        normalized.image.close()
        raise ValidationError(
            "The auxiliary image must match the source image dimensions.",
            category="dimension-mismatch",
        )
    grayscale = normalized.image.convert("L")
    normalized.image.close()
    return grayscale.point(lambda value: 255 if value >= 128 else 0, mode="L")


def display_copy(image: Image.Image, max_size: tuple[int, int] = (1200, 900)) -> Image.Image:
    """Return a display-sized copy while retaining the full-size source elsewhere."""

    preview = image.copy()
    preview.thumbnail(max_size, Image.Resampling.LANCZOS)
    return preview
