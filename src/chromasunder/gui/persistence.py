"""GSettings adapter with a small development fallback when schemas are not installed."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCHEMA_ID = "io.github.the_blue_blurr.ChromaSunder"


class SettingsStore:
    def __init__(self) -> None:
        self._gio = None
        self._settings = None
        try:
            import gi

            gi.require_version("Gio", "2.0")
            from gi.repository import Gio

            self._gio = Gio
            self._settings = Gio.Settings.new(SCHEMA_ID)
        except Exception:
            self._settings = None
        self._fallback_path = (
            Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            / "chromasunder"
            / "settings.json"
        )
        self._fallback: dict[str, Any] = {}
        if self._settings is None and self._fallback_path.exists():
            try:
                self._fallback = json.loads(self._fallback_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._fallback = {}

    def get(self, key: str, default: Any = None) -> Any:
        schema_key = key.replace("_", "-")
        if self._settings is not None:
            try:
                value = self._settings.get_value(schema_key).unpack()
                if isinstance(value, str) and default is not None and not isinstance(default, str):
                    return json.loads(value)
                return value
            except Exception:
                return default
        return self._fallback.get(key, default)

    def set(self, key: str, value: Any) -> None:
        schema_key = key.replace("_", "-")
        if self._settings is not None:
            try:
                from gi.repository import GLib

                current = self._settings.get_value(schema_key)
                if current.get_type_string() == "s":
                    self._settings.set_string(
                        schema_key, json.dumps(value) if not isinstance(value, str) else value
                    )
                elif current.get_type_string() == "i":
                    self._settings.set_int(schema_key, int(value))
                elif current.get_type_string() == "b":
                    self._settings.set_boolean(schema_key, bool(value))
                else:
                    self._settings.set_value(schema_key, GLib.Variant("s", json.dumps(value)))
                return
            except Exception:
                pass
        self._fallback[key] = value
        self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self._fallback_path.write_text(
            json.dumps(self._fallback, indent=2) + "\n", encoding="utf-8"
        )
