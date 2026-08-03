"""GUI-facing settings mutation and mode sensitivity rules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from chromasunder.core.enums import IntervalFunction
from chromasunder.core.models import PixelSortSettings
from chromasunder.core.validation import validate_settings

from .history import SettingsHistory


@dataclass(frozen=True, slots=True)
class ModeSensitivity:
    lower: bool
    upper: bool
    length: bool
    interval_image: bool


def sensitivity_for_mode(mode: IntervalFunction | str) -> ModeSensitivity:
    selected = IntervalFunction(mode)
    return {
        IntervalFunction.THRESHOLD: ModeSensitivity(True, True, False, False),
        IntervalFunction.EDGES: ModeSensitivity(True, False, False, False),
        IntervalFunction.RANDOM: ModeSensitivity(False, False, True, False),
        IntervalFunction.WAVES: ModeSensitivity(False, False, True, False),
        IntervalFunction.FILE: ModeSensitivity(False, False, False, True),
        IntervalFunction.FILE_EDGES: ModeSensitivity(True, False, False, True),
        IntervalFunction.NONE: ModeSensitivity(False, False, False, False),
    }[selected]


class SettingsController:
    def __init__(self, settings: PixelSortSettings | None = None) -> None:
        self.settings = settings or PixelSortSettings()
        validate_settings(self.settings)
        self.history = SettingsHistory()
        self.history.seed(self.settings)
        self._listeners: list[Callable[[PixelSortSettings], None]] = []

    def add_listener(self, listener: Callable[[PixelSortSettings], None]) -> None:
        self._listeners.append(listener)

    def update(self, **changes: Any) -> PixelSortSettings:
        updated = replace(self.settings, **changes)
        validate_settings(updated)
        self.history.push(updated)
        self.settings = updated
        for listener in self._listeners:
            listener(updated)
        return updated

    def apply_preset(self, settings: PixelSortSettings) -> None:
        validate_settings(settings)
        self.history.push(settings)
        self.settings = settings
        for listener in self._listeners:
            listener(settings)

    def restore(self, settings: PixelSortSettings) -> None:
        """Set persisted startup state without creating an undo action."""
        validate_settings(settings)
        self.settings = settings
        self.history.clear()
        self.history.seed(settings)
        for listener in self._listeners:
            listener(settings)

    def undo(self) -> PixelSortSettings | None:
        result = self.history.undo()
        if result is not None:
            self.settings = result
            for listener in self._listeners:
                listener(result)
        return result

    def redo(self) -> PixelSortSettings | None:
        result = self.history.redo()
        if result is not None:
            self.settings = result
            for listener in self._listeners:
                listener(result)
        return result

    def reset(self) -> PixelSortSettings:
        return self.update(
            interval_function=PixelSortSettings().interval_function,
            sorting_function=PixelSortSettings().sorting_function,
            lower_threshold=0.25,
            upper_threshold=0.8,
            characteristic_length=50,
            angle=0.0,
            randomness=0.0,
        )

    def new_variation(self) -> PixelSortSettings:
        seed = PixelSortSettings().seed
        while seed == self.settings.seed:
            seed = PixelSortSettings().seed
        return self.update(seed=seed)
