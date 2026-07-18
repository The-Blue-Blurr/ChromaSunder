"""Typed data contracts shared by the core, worker, and GUI."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .enums import IntervalFunction, SortingFunction


@dataclass(frozen=True, slots=True)
class PixelSortSettings:
    """The complete processing state that can be stored in a preset."""

    interval_function: IntervalFunction = IntervalFunction.THRESHOLD
    sorting_function: SortingFunction = SortingFunction.LIGHTNESS
    lower_threshold: float = 0.25
    upper_threshold: float = 0.80
    characteristic_length: int = 50
    angle: float = 0.0
    randomness: float = 0.0
    seed: int = field(default_factory=lambda: secrets.randbelow(2**31))

    def __post_init__(self) -> None:
        object.__setattr__(self, "interval_function", IntervalFunction(self.interval_function))
        object.__setattr__(self, "sorting_function", SortingFunction(self.sorting_function))

    def to_dict(self) -> dict[str, Any]:
        return {
            "interval_function": self.interval_function.value,
            "sorting_function": self.sorting_function.value,
            "lower_threshold": self.lower_threshold,
            "upper_threshold": self.upper_threshold,
            "characteristic_length": self.characteristic_length,
            "angle": self.angle,
            "randomness": self.randomness,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> PixelSortSettings:
        return cls(
            interval_function=IntervalFunction(values["interval_function"]),
            sorting_function=SortingFunction(values["sorting_function"]),
            lower_threshold=float(values["lower_threshold"]),
            upper_threshold=float(values["upper_threshold"]),
            characteristic_length=int(values["characteristic_length"]),
            angle=float(values["angle"]),
            randomness=float(values["randomness"]),
            seed=int(values["seed"]),
        )

    def changed(self, **changes: Any) -> PixelSortSettings:
        return replace(self, **changes)


@dataclass(frozen=True, slots=True)
class FileIdentity:
    path: str
    size: int
    modified_ns: int

    @classmethod
    def from_path(cls, path: str | Path) -> FileIdentity:
        resolved = Path(path).expanduser().resolve()
        stat = resolved.stat()
        return cls(str(resolved), stat.st_size, stat.st_mtime_ns)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size": self.size,
            "modified_ns": self.modified_ns,
        }


@dataclass(frozen=True, slots=True)
class RenderSnapshot:
    settings: PixelSortSettings
    source: FileIdentity
    mask: FileIdentity | None = None
    interval_image: FileIdentity | None = None
    engine_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "settings": self.settings.to_dict(),
            "source": self.source.to_dict(),
            "mask": self.mask.to_dict() if self.mask else None,
            "interval_image": self.interval_image.to_dict() if self.interval_image else None,
            "engine_version": self.engine_version,
        }


@dataclass(slots=True)
class NormalizedImage:
    image: Any
    path: str
    format: str
    dimensions: tuple[int, int]
    warning: str | None = None


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
