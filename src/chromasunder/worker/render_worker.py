"""Worker entrypoint. It intentionally imports no GUI modules."""

from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import Any

from chromasunder.core.exporting import save_png
from chromasunder.core.imaging import display_copy
from chromasunder.core.models import PixelSortSettings
from chromasunder.core.processing import RenderCancelled, render_file
from chromasunder.logging_setup import configure_logging

LOGGER = logging.getLogger(__name__)


def render_worker(request: dict[str, Any], messages) -> None:
    """Render one file and put small structured messages on a queue."""

    configure_logging()

    def send(kind: str, **payload: Any) -> None:
        messages.put({"kind": kind, "payload": payload})

    try:
        settings = PixelSortSettings.from_dict(request["settings"])

        def progress(done: int, total: int) -> None:
            if total and (done == total or done % max(1, total // 50) == 0):
                send("progress", done=done, total=total)

        image = render_file(
            request["source_path"],
            settings,
            mask_path=request.get("mask_path"),
            interval_path=request.get("interval_path"),
            progress=progress,
        )
        try:
            cache_path = Path(request["cache_path"])
            preview_path = Path(request["preview_path"])
            save_png(image, cache_path)
            preview = display_copy(image)
            try:
                save_png(preview, preview_path)
            finally:
                preview.close()
            send(
                "complete",
                cache_path=str(cache_path),
                preview_path=str(preview_path),
                dimensions=list(image.size),
            )
        finally:
            image.close()
    except RenderCancelled:
        send("cancelled")
    except MemoryError:
        LOGGER.exception("Render worker ran out of memory")
        send("error", category="out-of-memory", message="The image was too large to render safely.")
    except Exception as exc:  # worker boundary must convert every failure to a message
        LOGGER.exception("Render worker failed")
        send(
            "error",
            category=getattr(exc, "category", "worker-crash"),
            message=str(exc) or "The render worker failed.",
            details=traceback.format_exc(limit=8),
        )


def main_for_tests(request: dict[str, Any], messages) -> None:
    """Stable function name for tests and multiprocessing spawn."""

    render_worker(request, messages)
