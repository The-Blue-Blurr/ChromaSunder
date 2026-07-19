from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from chromasunder.core.models import PixelSortSettings
from chromasunder.core.presets import PresetError, load_preset, save_preset


class PresetTests(unittest.TestCase):
    def test_round_trip_and_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            path = save_preset(Path(directory) / "settings", PixelSortSettings(seed=123))
            self.assertEqual(path.suffix, ".csunder")
            self.assertEqual(load_preset(path), PixelSortSettings(seed=123))

    def test_invalid_preset_does_not_need_to_mutate_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csunder"
            path.write_text(
                json.dumps({"format": "chromasunder-preset", "schema_version": 1, "settings": {}})
            )
            with self.assertRaises(PresetError):
                load_preset(path)

    def test_future_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "future.csunder"
            path.write_text(
                json.dumps({"format": "chromasunder-preset", "schema_version": 999, "settings": {}})
            )
            with self.assertRaises(PresetError) as context:
                load_preset(path)
            self.assertEqual(context.exception.category, "unsupported-preset-schema")

    def test_bad_types_and_unknown_fields_are_rejected(self):
        settings = PixelSortSettings(seed=123).to_dict()
        cases = (
            {**settings, "seed": "123"},
            {**settings, "characteristic_length": 2.5},
            {**settings, "randomness": True},
            {**settings, "unexpected": 1},
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csunder"
            for values in cases:
                with self.subTest(values=values):
                    path.write_text(
                        json.dumps(
                            {
                                "format": "chromasunder-preset",
                                "schema_version": 1,
                                "settings": values,
                            }
                        )
                    )
                    with self.assertRaises(PresetError):
                        load_preset(path)
