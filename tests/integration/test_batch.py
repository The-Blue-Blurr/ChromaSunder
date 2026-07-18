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
            events = []
            runner = BatchRunner(WorkerController())
            runner.start(
                items,
                BatchSnapshot(
                    PixelSortSettings(interval_function="none", seed=1),
                    str(output),
                    OutputMode.PNG,
                ),
                callback=lambda event, _item, payload: events.append((event, payload)),
            )
            deadline = time.monotonic() + 15
            while runner.active and time.monotonic() < deadline:
                runner.poll()
                time.sleep(0.02)
            self.assertFalse(runner.active)
            self.assertEqual([item.status for item in items], [BatchStatus.COMPLETED] * 2, events)
            self.assertEqual(len(list(output.glob("*.png"))), 2)
            self.assertTrue(any(event == "finished" for event, _payload in events), events)


if __name__ == "__main__":
    unittest.main()
