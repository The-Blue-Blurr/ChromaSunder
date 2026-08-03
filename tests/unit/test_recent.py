from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from chromasunder.gui.recent import IMAGE_LIMIT, PRESET_LIMIT, RecentStore


class RecentStoreTests(unittest.TestCase):
    def test_images_are_deduplicated_and_limited(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / f"image-{index}.png" for index in range(IMAGE_LIMIT + 1)]
            store = RecentStore(root / "recent.json")

            for path in paths:
                store.add_image(path)
            store.add_image(paths[1])

            self.assertEqual(
                store.images,
                [str(paths[1]), str(paths[5]), str(paths[4]), str(paths[3]), str(paths[2])],
            )

    def test_presets_use_separate_limit_and_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "recent.json"
            store = RecentStore(path)
            presets = [root / f"preset-{index}.csunder" for index in range(PRESET_LIMIT + 1)]

            for preset in presets:
                store.add_preset(preset)

            restored = RecentStore(path)
            self.assertEqual(restored.presets, list(map(str, reversed(presets[1:]))))
            self.assertEqual(restored.images, [])

    def test_malformed_history_starts_empty_and_missing_paths_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recent.json"
            path.write_text("not json", encoding="utf-8")
            store = RecentStore(path)
            missing = Path(directory) / "missing.png"

            store.add_image(missing)

            self.assertEqual(store.images, [str(missing)])
            self.assertFalse(store.is_available(str(missing)))

    def test_clear_methods_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = RecentStore(root / "recent.json")
            store.add_image(root / "image.png")
            store.add_preset(root / "preset.csunder")

            store.clear_images()

            self.assertEqual(store.images, [])
            self.assertEqual(len(store.presets), 1)


if __name__ == "__main__":
    unittest.main()
