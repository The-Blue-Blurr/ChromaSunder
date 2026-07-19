from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image

from chromasunder.core.models import PixelSortSettings
from chromasunder.gui.batch.controller import BatchRunner
from chromasunder.gui.batch.model import BatchItem, BatchSnapshot, BatchStatus, OutputMode
from chromasunder.worker.controller import WorkerController


class BatchTests(unittest.TestCase):
    def _run(self, items, snapshot):
        events = []
        runner = BatchRunner(WorkerController())
        runner.start(
            items,
            snapshot,
            callback=lambda event, _item, payload: events.append((event, payload)),
        )
        deadline = time.monotonic() + 15
        while runner.active and time.monotonic() < deadline:
            runner.poll()
            time.sleep(0.02)
        self.assertFalse(runner.active, events)
        return events

    def test_batch_is_sequential_and_continues(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            output.mkdir()
            items = []
            for index in range(2):
                path = root / f"image-{index}.png"
                Image.new("RGBA", (20, 10), (index * 40, 100, 50, 255)).save(path)
                items.append(BatchItem(str(path), dimensions=(20, 10), source_format="PNG"))
            events = self._run(
                items,
                BatchSnapshot(
                    PixelSortSettings(interval_function="none", seed=1),
                    str(output),
                    OutputMode.PNG,
                ),
            )
            self.assertEqual([item.status for item in items], [BatchStatus.COMPLETED] * 2, events)
            self.assertEqual(len(list(output.glob("*.png"))), 2)
            self.assertTrue(any(event == "finished" for event, _payload in events), events)

    def test_failure_does_not_stop_later_items(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            valid = root / "valid.png"
            Image.new("RGBA", (8, 4), (20, 100, 50, 255)).save(valid)
            items = [
                BatchItem(str(root / "missing.png"), dimensions=(8, 4), source_format="PNG"),
                BatchItem(str(valid), dimensions=(8, 4), source_format="PNG"),
            ]
            events = self._run(
                items,
                BatchSnapshot(PixelSortSettings(interval_function="none", seed=1), str(output)),
            )
            self.assertEqual(
                [item.status for item in items],
                [BatchStatus.FAILED, BatchStatus.COMPLETED],
                events,
            )
            self.assertEqual(len(list(output.glob("*.png"))), 1)

    def test_preserve_mode_keeps_png_and_jpeg_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            png = root / "source-png.png"
            jpeg = root / "source-jpeg.jpg"
            Image.new("RGBA", (8, 4), (20, 100, 50, 128)).save(png)
            Image.new("RGB", (8, 4), (100, 20, 50)).save(jpeg)
            items = [
                BatchItem(str(png), dimensions=(8, 4), source_format="PNG"),
                BatchItem(str(jpeg), dimensions=(8, 4), source_format="JPEG"),
            ]
            events = self._run(
                items,
                BatchSnapshot(
                    PixelSortSettings(interval_function="none", seed=1),
                    str(output),
                    OutputMode.PRESERVE,
                ),
            )
            self.assertEqual([item.status for item in items], [BatchStatus.COMPLETED] * 2, events)
            with Image.open(output / "source-png_pxsorted.png") as saved_png:
                self.assertEqual(saved_png.format, "PNG")
                self.assertEqual(saved_png.mode, "RGBA")
            with Image.open(output / "source-jpeg_pxsorted.jpg") as saved_jpeg:
                self.assertEqual(saved_jpeg.format, "JPEG")
                self.assertEqual(saved_jpeg.mode, "RGB")


if __name__ == "__main__":
    unittest.main()
