"""Sequential batch execution built on the isolated worker controller."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chromasunder.worker.controller import WorkerController

from .model import (
    BatchItem,
    BatchSnapshot,
    BatchStatus,
    BatchSummary,
    ConflictPolicy,
    OutputMode,
    assign_proposed_outputs,
    validate_batch_dimensions,
)

BatchCallback = Callable[[str, BatchItem | None, dict[str, Any]], None]
LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class BatchRunner:
    """A non-blocking state machine polled by the GTK main loop."""

    worker: WorkerController
    items: list[BatchItem] = field(default_factory=list)
    snapshot: BatchSnapshot | None = None
    current_index: int = -1
    summary: BatchSummary | None = None
    callback: BatchCallback | None = None
    _cache_path: Path | None = None
    _preview_path: Path | None = None
    _done_sent: bool = False

    def start(
        self,
        items: list[BatchItem],
        snapshot: BatchSnapshot,
        *,
        callback: BatchCallback | None = None,
    ) -> None:
        if self.worker.active:
            raise RuntimeError("A batch is already active.")
        validate_batch_dimensions(items, snapshot)
        for item in items:
            if item.status is not BatchStatus.SKIPPED:
                item.status = BatchStatus.PENDING
                item.message = ""
        if snapshot.conflict_policy is not ConflictPolicy.NUMERIC_SUFFIX:
            assign_proposed_outputs(items, snapshot)
        self.items = items
        self.snapshot = snapshot
        self.current_index = -1
        self.summary = BatchSummary(
            len(items),
            skipped=sum(item.status is BatchStatus.SKIPPED for item in items),
        )
        self.callback = callback
        self._cache_path = None
        self._preview_path = None
        self._done_sent = False
        self._prepare_next()

    @property
    def active(self) -> bool:
        return self.snapshot is not None and (
            self.worker.active or self.current_index < len(self.items)
        )

    @property
    def current_item(self) -> BatchItem | None:
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index]
        return None

    def _emit(self, event: str, item: BatchItem | None = None, **payload: Any) -> None:
        if self.callback:
            self.callback(event, item, payload)

    def _prepare_next(self) -> None:
        assert self.snapshot is not None
        self.current_index += 1
        if self.current_index >= len(self.items):
            self._finish()
            return
        item = self.items[self.current_index]
        if item.status not in {BatchStatus.PENDING, BatchStatus.PROCESSING}:
            self._prepare_next()
            return
        item.status = BatchStatus.PROCESSING
        self._emit("item-start", item)
        output_path = item.proposed_output or ""
        output_format = (
            "JPEG"
            if self.snapshot.output_mode is OutputMode.PRESERVE and item.source_format == "JPEG"
            else "PNG"
        )
        request = {
            "source_path": item.source_path,
            "settings": self.snapshot.settings.to_dict(),
            "mask_path": self.snapshot.mask_path,
            "interval_path": self.snapshot.interval_path,
            "output_path": output_path,
            "output_format": output_format,
            "jpeg_quality": self.snapshot.jpeg_quality,
            "jpeg_background": self.snapshot.jpeg_background,
        }
        self.worker.start(request)

    def poll(self) -> list[dict[str, Any]]:
        if not self.active:
            return []
        messages = self.worker.poll()
        for message in messages:
            kind = message.get("kind")
            payload = message.get("payload", {})
            item = self.current_item
            if kind == "progress":
                self._emit("progress", item, **payload)
            elif kind == "complete":
                self._complete_item(item)
            elif kind == "error":
                self._fail_item(item, payload.get("message", "Render failed."))
        process = self.worker.process
        if process is not None and not process.is_alive() and self.current_item is not None:
            if self.current_item.status == BatchStatus.PROCESSING:
                self._fail_item(self.current_item, "The render worker exited unexpectedly.")
        return messages

    def _complete_item(self, item: BatchItem | None) -> None:
        if item is None or self.snapshot is None:
            return
        item.status = BatchStatus.COMPLETED
        self.summary.completed += 1
        self._emit("item-complete", item)
        self.worker.finish()
        self._prepare_next()

    def _fail_item(self, item: BatchItem | None, message: str) -> None:
        if item is None or item.status != BatchStatus.PROCESSING:
            return
        item.status = BatchStatus.FAILED
        item.message = message
        self.summary.failed += 1
        self.worker.close()
        if self._cache_path:
            self._cache_path.unlink(missing_ok=True)
        if self._preview_path:
            self._preview_path.unlink(missing_ok=True)
        self._emit("item-failed", item, message=message)
        self._prepare_next()

    def cancel(self) -> None:
        if not self.active:
            return
        self.worker.cancel()
        for item in self.items[self.current_index :]:
            if item.status in {BatchStatus.PENDING, BatchStatus.PROCESSING}:
                item.status = BatchStatus.CANCELLED
                self.summary.cancelled += 1
        self._emit("cancelled", self.current_item)
        self._finish()

    def _finish(self) -> None:
        if self._done_sent:
            return
        self._done_sent = True
        self.worker.close()
        LOGGER.info(
            "Batch finished: total=%s completed=%s skipped=%s failed=%s cancelled=%s",
            self.summary.total,
            self.summary.completed,
            self.summary.skipped,
            self.summary.failed,
            self.summary.cancelled,
        )
        self._emit("finished", None, summary=self.summary)
        self.snapshot = None
