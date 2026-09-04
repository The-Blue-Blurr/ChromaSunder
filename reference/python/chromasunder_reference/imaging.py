from pathlib import Path

from PIL import Image, ImageOps

from .validation import ValidationError


def normalize_image(path: str | Path) -> Image.Image:
    source = Path(path).expanduser()
    try:
        with Image.open(source) as opened:
            opened.verify()
        with Image.open(source) as opened:
            if getattr(opened, "is_animated", False) or getattr(opened, "n_frames", 1) > 1:
                raise ValidationError(
                    "Animated and multipage images are not supported.",
                    category="animated-or-multipage",
                )
            oriented = ImageOps.exif_transpose(opened)
            return oriented.convert("RGBA").copy()
    except ValidationError:
        raise
    except (OSError, ValueError) as exc:
        raise ValidationError(f"Unable to read image: {source.name}", "corrupt-image") from exc


def normalize_binary_image(path: str | Path, dimensions: tuple[int, int]) -> Image.Image:
    normalized = normalize_image(path)
    if normalized.size != dimensions:
        normalized.close()
        raise ValidationError(
            "The auxiliary image must match the source image dimensions.", "dimension-mismatch"
        )
    grayscale = normalized.convert("L")
    normalized.close()
    try:
        return grayscale.point(lambda value: 255 if value >= 128 else 0, mode="1")
    finally:
        grayscale.close()
