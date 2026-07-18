from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from chromasunder.core.models import PixelSortSettings
from chromasunder.gui.batch.model import (
    BatchItem,
    BatchSnapshot,
    ConflictPolicy,
    OutputMode,
    numeric_suffix_path,
    preflight_outputs,
)
from chromasunder.gui.history import SettingsHistory


class HistoryAndBatchTests(unittest.TestCase):
    def test_history_is_settings_only_and_limited(self):
        history = SettingsHistory(limit=2)
        first = PixelSortSettings(seed=1)
        second = PixelSortSettings(seed=2)
        third = PixelSortSettings(seed=3)
        history.seed(first)
        history.push(second)
        history.push(third)
        self.assertTrue(history.can_undo)
        self.assertEqual(history.undo(), second)
        self.assertEqual(history.redo(), third)

    def test_conflict_preflight_and_numeric_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "photo.png"
            source.write_bytes(b"placeholder")
            output = Path(directory) / "photo_pxsorted.png"
            output.write_bytes(b"existing")
            item = BatchItem(str(source), source_format="PNG", dimensions=(2, 2))
            snapshot = BatchSnapshot(
                PixelSortSettings(seed=1),
                directory,
                OutputMode.PNG,
                conflict_policy=ConflictPolicy.SKIP,
            )
            report = preflight_outputs([item], snapshot)
            self.assertTrue(report.has_conflicts)
            chosen = numeric_suffix_path(output)
            self.assertEqual(chosen.name, "photo_pxsorted_1.png")


if __name__ == "__main__":
    unittest.main()
