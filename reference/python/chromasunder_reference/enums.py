from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python 3.10 compatibility

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
