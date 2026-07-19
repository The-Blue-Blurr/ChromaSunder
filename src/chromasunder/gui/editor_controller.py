"""Single-image editor state, snapshots, and stale-render decisions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chromasunder import ENGINE_VERSION
from chromasunder.core.imaging import normalize_binary_image, normalize_image
from chromasunder.core.models import FileIdentity, RenderSnapshot
from chromasunder.core.validation import ValidationError, validate_render_configuration

from .settings_controller import SettingsController


@dataclass(slots=True)
class EditorState:
    source_path: str | None = None
    mask_path: str | None = None
    interval_path: str | None = None
    cache_path: str | None = None
    preview_path: str | None = None
    rendered_snapshot: RenderSnapshot | None = None


class EditorController:
    def __init__(self, settings: SettingsController | None = None) -> None:
        self.settings_controller = settings or SettingsController()
        self.state = EditorState()

    @property
    def settings(self):
        return self.settings_controller.settings

    @property
    def has_source(self) -> bool:
        return bool(self.state.source_path)

    @property
    def has_render(self) -> bool:
        return bool(self.state.cache_path and Path(self.state.cache_path).is_file())

    def open_source(self, path: str) -> None:
        normalized = normalize_image(path)
        normalized.image.close()
        self.state = EditorState(source_path=normalized.path)
        self.settings_controller.history.clear()
        self.settings_controller.history.seed(self.settings)

    def set_mask(self, path: str | None) -> None:
        self.state.mask_path = str(Path(path).expanduser().resolve()) if path else None

    def set_interval_image(self, path: str | None) -> None:
        self.state.interval_path = str(Path(path).expanduser().resolve()) if path else None

    def update_settings(self, **changes: Any) -> None:
        self.settings_controller.update(**changes)

    def snapshot(self) -> RenderSnapshot:
        if not self.state.source_path:
            raise ValidationError("Open an image before rendering.", "missing-source")
        validate_render_configuration(
            self.settings,
            self.state.source_path,
            self.state.mask_path,
            self.state.interval_path,
        )
        source = normalize_image(self.state.source_path)
        try:
            if self.state.mask_path:
                mask = normalize_binary_image(self.state.mask_path, source.dimensions)
                mask.close()
            if self.state.interval_path:
                interval = normalize_binary_image(self.state.interval_path, source.dimensions)
                interval.close()
        finally:
            source.image.close()
        return RenderSnapshot(
            settings=self.settings,
            source=FileIdentity.from_path(self.state.source_path),
            mask=FileIdentity.from_path(self.state.mask_path) if self.state.mask_path else None,
            interval_image=(
                FileIdentity.from_path(self.state.interval_path)
                if self.state.interval_path
                else None
            ),
            engine_version=ENGINE_VERSION,
        )

    def rendered_is_current(self) -> bool:
        if self.state.rendered_snapshot is None:
            return False
        try:
            return self.state.rendered_snapshot == self.snapshot()
        except (ValidationError, OSError):
            return False

    def mark_rendered(self, snapshot: RenderSnapshot, cache_path: str, preview_path: str) -> None:
        self.state.rendered_snapshot = snapshot
        self.state.cache_path = cache_path
        self.state.preview_path = preview_path

    def clear_render(self) -> None:
        for path in (self.state.cache_path, self.state.preview_path):
            if path:
                Path(path).unlink(missing_ok=True)
        self.state.cache_path = None
        self.state.preview_path = None
        self.state.rendered_snapshot = None
