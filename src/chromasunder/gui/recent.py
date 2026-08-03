"""Persistent histories for recently opened images and presets."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

IMAGE_LIMIT = 5
PRESET_LIMIT = 10


class RecentStore:
    """Store recent paths independently from application preferences."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
            path = state_home / "chromasunder" / "recent.json"
        self.path = Path(path)
        self.images: list[str] = []
        self.presets: list[str] = []
        self._load()

    def add_image(self, path: str | Path) -> None:
        self.images = self._updated(self.images, path, IMAGE_LIMIT)
        self._save()

    def add_preset(self, path: str | Path) -> None:
        self.presets = self._updated(self.presets, path, PRESET_LIMIT)
        self._save()

    def clear_images(self) -> None:
        self.images.clear()
        self._save()

    def clear_presets(self) -> None:
        self.presets.clear()
        self._save()

    @staticmethod
    def is_available(path: str) -> bool:
        return Path(path).is_file()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return
            self.images = self._clean(payload.get("images"), IMAGE_LIMIT)
            self.presets = self._clean(payload.get("presets"), PRESET_LIMIT)
        except (OSError, TypeError, ValueError):
            self.images = []
            self.presets = []

    def _save(self) -> None:
        payload = {"images": self.images, "presets": self.presets}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as temporary:
                temporary_path = temporary.name
                json.dump(payload, temporary, indent=2)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)

    @staticmethod
    def _canonical(path: str | Path) -> str:
        return str(Path(path).expanduser().resolve())

    @classmethod
    def _updated(cls, values: list[str], path: str | Path, limit: int) -> list[str]:
        canonical = cls._canonical(path)
        return [canonical, *(value for value in values if value != canonical)][:limit]

    @staticmethod
    def _clean(value, limit: int) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for path in value:
            if isinstance(path, str) and path and path not in result:
                result.append(path)
        return result[:limit]
