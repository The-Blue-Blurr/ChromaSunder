from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from chromasunder.core.models import PixelSortSettings
from chromasunder.worker.controller import WorkerController, new_render_paths


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


if __name__ == "__main__":
    unittest.main()
