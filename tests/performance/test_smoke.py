from __future__ import annotations

import unittest

from PIL import Image

from chromasunder.core.models import PixelSortSettings
from chromasunder.core.processing import process_image


class PerformanceSmokeTests(unittest.TestCase):
    def test_medium_image_completes_without_unbounded_image_cache(self):
        image = Image.new("RGBA", (256, 128), (100, 140, 180, 255))
        rendered = process_image(image, PixelSortSettings(interval_function="none", seed=1))
        self.assertEqual(rendered.size, image.size)
        self.assertEqual(rendered.mode, "RGBA")
        rendered.close()
        image.close()
