"""Settings-only .csunder JSON presets."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from chromasunder import __version__

from .models import PixelSortSettings
from .validation import ValidationError, validate_settings

FORMAT_NAME = "chromasunder-preset"
SCHEMA_VERSION = 1


class PresetError(ValidationError):
    """A malformed or unsupported preset."""


def _payload(settings: PixelSortSettings) -> dict[str, Any]:
    return {
        "format": FORMAT_NAME,
        "schema_version": SCHEMA_VERSION,
        "application_version": __version__,
        "settings": settings.to_dict(),
    }


def save_preset(path: str | Path, settings: PixelSortSettings) -> Path:
    validate_settings(settings)
    target = Path(path).expanduser()
    if target.suffix.lower() != ".csunder":
        target = target.with_name(f"{target.name}.csunder")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(_payload(settings), indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise PresetError(f"Unable to save preset: {target}", "preset-save-failure") from exc
    return target


def load_preset(path: str | Path) -> PixelSortSettings:
    try:
        payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PresetError("The preset is not valid UTF-8 JSON.", "invalid-preset") from exc
    if not isinstance(payload, dict) or payload.get("format") != FORMAT_NAME:
        raise PresetError("This file is not a ChromaSunder preset.", "invalid-preset")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise PresetError("This preset schema is not supported.", "unsupported-preset-schema")
    values = payload.get("settings")
    required = {
        "interval_function",
        "sorting_function",
        "lower_threshold",
        "upper_threshold",
        "characteristic_length",
        "angle",
        "randomness",
        "seed",
    }
    if not isinstance(values, dict) or not required.issubset(values):
        raise PresetError("The preset is missing required settings.", "invalid-preset")
    if set(values) != required:
        raise PresetError("The preset contains unknown settings.", "invalid-preset")
    numeric_fields = {"lower_threshold", "upper_threshold", "angle", "randomness"}
    if (
        not isinstance(values["interval_function"], str)
        or not isinstance(values["sorting_function"], str)
        or any(
            isinstance(values[name], bool) or not isinstance(values[name], (int, float))
            for name in numeric_fields
        )
        or isinstance(values["characteristic_length"], bool)
        or not isinstance(values["characteristic_length"], int)
        or isinstance(values["seed"], bool)
        or not isinstance(values["seed"], int)
    ):
        raise PresetError("The preset contains invalid setting types.", "invalid-preset")
    try:
        settings = PixelSortSettings.from_dict(values)
        validate_settings(settings)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise PresetError("The preset contains invalid settings.", "invalid-preset") from exc
    return settings
