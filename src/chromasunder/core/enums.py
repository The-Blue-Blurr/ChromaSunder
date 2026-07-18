"""Stable enum values used by presets and the processing engine."""

from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - kept for Python 3.10 Fedora images

    class StrEnum(str, Enum):
        def __str__(self) -> str:
            return self.value


class IntervalFunction(StrEnum):
    THRESHOLD = "threshold"
    EDGES = "edges"
    RANDOM = "random"
    WAVES = "waves"
    FILE = "file"
    FILE_EDGES = "file-edges"
    NONE = "none"


class SortingFunction(StrEnum):
    LIGHTNESS = "lightness"
    HUE = "hue"
    SATURATION = "saturation"
    INTENSITY = "intensity"
    MINIMUM = "minimum"


SUPPORTED_INTERVAL_FUNCTIONS = tuple(item.value for item in IntervalFunction)
SUPPORTED_SORTING_FUNCTIONS = tuple(item.value for item in SortingFunction)
