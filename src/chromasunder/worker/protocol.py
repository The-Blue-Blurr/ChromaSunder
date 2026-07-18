"""Serializable messages exchanged with a render worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RenderRequest:
    source_path: str
    settings: dict[str, Any]
    cache_path: str
    preview_path: str
    mask_path: str | None = None
    interval_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "settings": self.settings,
            "cache_path": self.cache_path,
            "preview_path": self.preview_path,
            "mask_path": self.mask_path,
            "interval_path": self.interval_path,
        }


@dataclass(frozen=True, slots=True)
class WorkerMessage:
    kind: str
    payload: dict[str, Any]
