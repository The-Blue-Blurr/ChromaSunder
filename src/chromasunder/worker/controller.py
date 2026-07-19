"""Spawned worker lifecycle and cache management."""

from __future__ import annotations

import logging
import os
import queue
import time
import uuid
from collections import deque
from multiprocessing import get_context
from pathlib import Path
from typing import Any

from .render_worker import render_worker

LOGGER = logging.getLogger(__name__)


def cache_directory() -> Path:
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "chromasunder" / "renders"


def clean_abandoned_cache(max_age_seconds: int = 86_400) -> int:
    """Remove old render files while leaving recent active markers untouched."""

    directory = cache_directory()
    if not directory.exists():
        return 0
    removed = 0
    cutoff = time.time() - max_age_seconds
    for path in directory.iterdir():
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


class WorkerController:
    """One fresh spawn process per render request."""

    def __init__(self) -> None:
        self._context = get_context("spawn")
        self._process = None
        self._messages = None
        self._request: dict[str, Any] | None = None
        self._pending: deque[dict[str, Any]] = deque()

    @property
    def active(self) -> bool:
        return self._process is not None and self._process.is_alive()

    @property
    def process(self):
        return self._process

    def start(self, request: dict[str, Any]) -> None:
        if self.active:
            raise RuntimeError("A render is already active.")
        self.close()
        self._request = request
        self._messages = self._context.Queue()
        self._process = self._context.Process(target=render_worker, args=(request, self._messages))
        self._process.start()
        LOGGER.info(
            "Started %s worker pid=%s", request.get("operation", "render"), self._process.pid
        )

    def poll(self) -> list[dict[str, Any]]:
        if self._messages is None:
            return []
        messages = list(self._pending)
        self._pending.clear()
        while True:
            try:
                messages.append(self._messages.get_nowait())
            except queue.Empty:
                break
        return messages

    def wait(self, timeout: float | None = None) -> list[dict[str, Any]]:
        if self._process is None:
            return []
        started = time.monotonic()
        while self._process.is_alive():
            if timeout is not None and time.monotonic() - started >= timeout:
                break
            time.sleep(0.02)
        messages = self.poll()
        if not self._process.is_alive():
            messages.extend(self.poll())
        return messages

    def cancel(self) -> None:
        process = self._process
        if process is None:
            return
        if process.is_alive():
            process.terminate()
            process.join(timeout=0.5)
            if process.is_alive():
                process.kill()
                process.join(timeout=0.5)
        LOGGER.info("Cancelled worker pid=%s exitcode=%s", process.pid, process.exitcode)
        request = self._request or {}
        for key in ("cache_path", "preview_path", "output_path"):
            path = request.get(key)
            if path:
                target = Path(path)
                target.unlink(missing_ok=True)
                for temporary in target.parent.glob(f".{target.name}.*.tmp"):
                    temporary.unlink(missing_ok=True)
        if request.get("cache_path"):
            Path(request["cache_path"]).with_suffix(".active").unlink(missing_ok=True)
        self.close()

    def finish(self) -> None:
        """Dispose of a worker that already reported successful completion."""
        process = self._process
        if process is not None and process.is_alive():
            process.join(timeout=0.5)
            if process.is_alive():
                process.terminate()
                process.join(timeout=0.5)
        if process is not None:
            LOGGER.info("Worker pid=%s completed with exitcode=%s", process.pid, process.exitcode)
        self.close()

    def close(self) -> None:
        if self._process is not None and self._process.is_alive():
            self.cancel()
            return
        if self._messages is not None:
            self._messages.close()
            self._messages.join_thread()
        if self._request and self._request.get("cache_path"):
            Path(self._request["cache_path"]).with_suffix(".active").unlink(missing_ok=True)
        self._messages = None
        self._process = None
        self._request = None

    def __enter__(self) -> WorkerController:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


def new_render_paths() -> tuple[Path, Path]:
    directory = cache_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        directory = Path(os.environ.get("TMPDIR", "/tmp")) / "chromasunder" / "renders"
        directory.mkdir(parents=True, exist_ok=True)
    identifier = uuid.uuid4().hex
    cache_path = directory / f"{identifier}.png"
    cache_path.with_suffix(".active").touch()
    return cache_path, directory / f"{identifier}.preview.png"
