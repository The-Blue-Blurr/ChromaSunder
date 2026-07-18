"""Atomic, metadata-free PNG and JPEG output helpers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PIL import Image, ImageColor

from .validation import ValidationError


def suggest_output_path(
    source_path: str | Path, suffix: str = "_pxsorted", output_format: str = "PNG"
) -> Path:
    source = Path(source_path)
    extension = ".jpg" if output_format.upper() in {"JPEG", "JPG"} else ".png"
    return source.with_name(f"{source.stem}{suffix}{extension}")


def _atomic_save(image: Image.Image, destination: str | Path, format_name: str, **options) -> Path:
    target = Path(destination).expanduser()
    parent = target.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            image.save(temporary, format=format_name, **options)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    except OSError as exc:
        raise ValidationError(
            f"Unable to write the output file: {target}", category="permission-failure"
        ) from exc
    return target


def save_png(image: Image.Image, destination: str | Path) -> Path:
    clean = image.convert("RGBA")
    try:
        return _atomic_save(clean, destination, "PNG", compress_level=9)
    finally:
        clean.close()


def _background_color(value: str | tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(value, tuple):
        return value
    try:
        return ImageColor.getrgb(value)
    except ValueError as exc:
        raise ValidationError("The JPEG background color is invalid.") from exc


def save_jpeg(
    image: Image.Image,
    destination: str | Path,
    *,
    quality: int = 95,
    background: str | tuple[int, int, int] = "black",
) -> Path:
    if not 1 <= quality <= 100:
        raise ValidationError("JPEG quality must be between 1 and 100.")
    rgba = image.convert("RGBA")
    canvas = Image.new("RGB", rgba.size, _background_color(background))
    try:
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return _atomic_save(canvas, destination, "JPEG", quality=quality, optimize=True)
    finally:
        rgba.close()
        canvas.close()
