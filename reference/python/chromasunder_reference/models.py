from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .enums import IntervalFunction, SortingFunction


@dataclass(frozen=True, slots=True)
class PixelSortSettings:
    interval_function: IntervalFunction = IntervalFunction.THRESHOLD
    sorting_function: SortingFunction = SortingFunction.LIGHTNESS
    lower_threshold: float = 0.25
    upper_threshold: float = 0.80
    characteristic_length: int = 50
    angle: float = 0.0
    randomness: float = 0.0
    seed: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "interval_function", IntervalFunction(self.interval_function))
        object.__setattr__(self, "sorting_function", SortingFunction(self.sorting_function))

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
