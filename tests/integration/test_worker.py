from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from chromasunder.core.models import PixelSortSettings
from chromasunder.worker.controller import (
    WorkerController,
    clean_abandoned_cache,
    new_render_paths,
)


class WorkerTests(unittest.TestCase):
    def test_spawn_worker_writes_cache_and_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            Image.new("RGBA", (12, 8), (20, 50, 100, 255)).save(source)
            cache, preview = new_render_paths()
            worker = WorkerController()
            try:
                worker.start(
                    {
                        "source_path": str(source),
                        "settings": PixelSortSettings(interval_function="none", seed=1).to_dict(),
                        "cache_path": str(cache),
                        "preview_path": str(preview),
                    }
                )
                messages = worker.wait(timeout=10)
                self.assertTrue(
                    any(message["kind"] == "complete" for message in messages), messages
                )
                self.assertTrue(cache.exists())
                self.assertTrue(preview.exists())
            finally:
                worker.close()
                cache.unlink(missing_ok=True)
                preview.unlink(missing_ok=True)

    def test_worker_reencodes_cached_render_for_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache.png"
            output = root / "export.jpg"
            Image.new("RGBA", (4, 3), (100, 50, 20, 128)).save(cache)
            worker = WorkerController()
            try:
                worker.start(
                    {
                        "operation": "export",
                        "cache_path": str(cache),
                        "output_path": str(output),
                        "output_format": "JPEG",
                        "jpeg_quality": 95,
                        "jpeg_background": "black",
                    }
                )
                messages = worker.wait(timeout=10)
                self.assertTrue(
                    any(message["kind"] == "complete" for message in messages), messages
                )
                with Image.open(output) as exported:
                    self.assertEqual(exported.format, "JPEG")
                    self.assertEqual(exported.mode, "RGB")
            finally:
                worker.finish()

    def test_worker_reports_engine_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            worker = WorkerController()
            worker.start(
                {
                    "source_path": str(root / "missing.png"),
                    "settings": PixelSortSettings(seed=1).to_dict(),
                    "cache_path": str(root / "cache.png"),
                    "preview_path": str(root / "preview.png"),
                }
            )
            messages = worker.wait(timeout=10)
            self.assertTrue(any(message["kind"] == "error" for message in messages), messages)
            worker.close()

    def test_cancellation_is_repeatable_and_removes_partial_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "large.png"
            cache = root / "cache.png"
            preview = root / "preview.png"
            Image.new("RGBA", (3000, 2000), (20, 50, 100, 255)).save(source)
            cache.write_bytes(b"partial")
            preview.write_bytes(b"partial")
            (root / ".cache.png.test.tmp").write_bytes(b"partial")
            worker = WorkerController()
            worker.start(
                {
                    "source_path": str(source),
                    "settings": PixelSortSettings(interval_function="none", seed=1).to_dict(),
                    "cache_path": str(cache),
                    "preview_path": str(preview),
                }
            )
            time.sleep(0.05)
            worker.cancel()
            worker.cancel()
            self.assertFalse(cache.exists())
            self.assertFalse(preview.exists())
            self.assertFalse((root / ".cache.png.test.tmp").exists())
            self.assertFalse(worker.active)

    def test_startup_cleanup_only_removes_old_cache_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            render_dir = root / "chromasunder" / "renders"
            render_dir.mkdir(parents=True)
            old = render_dir / "old.png"
            recent = render_dir / "recent.png"
            old.write_bytes(b"old")
            recent.write_bytes(b"recent")
            old_time = time.time() - 100
            old.touch()
            os.utime(old, (old_time, old_time))
            with patch.dict("os.environ", {"XDG_CACHE_HOME": directory}):
                self.assertEqual(clean_abandoned_cache(max_age_seconds=10), 1)
            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())


if __name__ == "__main__":
    unittest.main()
