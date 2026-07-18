"""Settings-only undo and redo history."""

from __future__ import annotations

from chromasunder.core.models import PixelSortSettings


class SettingsHistory:
    def __init__(self, limit: int = 100) -> None:
        self.limit = limit
        self._states: list[PixelSortSettings] = []
        self._index = -1

    def clear(self) -> None:
        self._states.clear()
        self._index = -1

    def seed(self, settings: PixelSortSettings) -> None:
        self.clear()
        self._states.append(settings)
        self._index = 0

    def push(self, settings: PixelSortSettings) -> None:
        if self._states and self._states[self._index] == settings:
            return
        self._states = self._states[: self._index + 1]
        self._states.append(settings)
        if len(self._states) > self.limit:
            self._states.pop(0)
        self._index = len(self._states) - 1

    @property
    def can_undo(self) -> bool:
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        return 0 <= self._index < len(self._states) - 1

    def undo(self) -> PixelSortSettings | None:
        if not self.can_undo:
            return None
        self._index -= 1
        return self._states[self._index]

    def redo(self) -> PixelSortSettings | None:
        if not self.can_redo:
            return None
        self._index += 1
        return self._states[self._index]
