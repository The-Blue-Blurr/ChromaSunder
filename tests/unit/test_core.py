from __future__ import annotations

import random
import unittest

from PIL import Image

from chromasunder.core.enums import IntervalFunction, SortingFunction
from chromasunder.core.exporting import save_jpeg, save_png
from chromasunder.core.imaging import normalize_binary_image, normalize_image
from chromasunder.core.intervals import detect_intervals
from chromasunder.core.models import PixelSortSettings
from chromasunder.core.processing import process_image
from chromasunder.core.sorting import sorting_key, sorting_key_function
from chromasunder.core.validation import ValidationError


def make_image(width: int = 16, height: int = 8) -> Image.Image:
    image = Image.new("RGBA", (width, height))
    for y in range(height):
        for x in range(width):
            image.putpixel((x, y), ((x * 17) % 256, (y * 31) % 256, ((x + y) * 23) % 256, 255))
    return image


class CoreEngineTests(unittest.TestCase):
    def test_public_and_specialized_sorting_keys_cover_channel_extremes(self):
        pixels = [
            (0, 0, 0, 0),
            (255, 255, 255, 255),
            (255, 0, 0, 32),
            (0, 255, 0, 64),
            (0, 0, 255, 128),
            (255, 127, 0, 192),
            (17, 17, 17, 255),
            (17, 17, 17, 0),
        ]
        for function in SortingFunction:
            key = sorting_key_function(function)
            with self.subTest(function=function):
                self.assertEqual(
                    sorted(pixels, key=key),
                    sorted(pixels, key=lambda pixel: sorting_key(pixel, function)),
                )

    def test_specialized_sorting_keys_preserve_ties_and_alpha_order(self):
        pixels = [
            (10, 20, 30, 200),
            (30, 20, 10, 100),
            (10, 20, 30, 50),
        ]
        for function in (SortingFunction.LIGHTNESS, SortingFunction.INTENSITY):
            with self.subTest(function=function):
                self.assertEqual(sorted(pixels, key=sorting_key_function(function)), pixels)

    def test_public_sorting_key_values_remain_normalized(self):
        self.assertEqual(sorting_key((0, 0, 0, 123), "lightness"), 0.0)
        self.assertEqual(sorting_key((255, 255, 255, 123), "lightness"), 1.0)
        self.assertEqual(sorting_key((255, 0, 0, 123), "hue"), 0.0)
        self.assertEqual(sorting_key((255, 0, 0, 123), "saturation"), 1.0)
        self.assertEqual(sorting_key((255, 0, 0, 123), "intensity"), 1.0 / 3.0)
        self.assertEqual(sorting_key((255, 127, 63, 123), "minimum"), 63 / 255.0)

    def test_all_sorting_modes_render(self):
        source = make_image()
        try:
            for function in SortingFunction:
                with self.subTest(function=function):
                    rendered = process_image(
                        source,
                        PixelSortSettings(
                            interval_function=IntervalFunction.NONE,
                            sorting_function=function,
                            seed=42,
                        ),
                    )
                    self.assertEqual(rendered.size, source.size)
                    self.assertEqual(rendered.mode, "RGBA")
                    rendered.close()
        finally:
            source.close()

    def test_all_interval_modes_render(self):
        source = make_image()
        interval = Image.new("L", source.size, 0)
        for y in range(source.height):
            for x in range(2, 12):
                interval.putpixel((x, y), 255)
        try:
            for function in IntervalFunction:
                with self.subTest(function=function):
                    settings = PixelSortSettings(
                        interval_function=function,
                        characteristic_length=4,
                        seed=42,
                    )
                    rendered = process_image(
                        source,
                        settings,
                        interval_image=interval
                        if function in {IntervalFunction.FILE, IntervalFunction.FILE_EDGES}
                        else None,
                    )
                    self.assertEqual(rendered.size, source.size)
                    rendered.close()
        finally:
            source.close()
            interval.close()

    def test_seed_is_deterministic_and_changes_random_intervals(self):
        source = make_image(48, 4)
        try:
            first = process_image(
                source,
                PixelSortSettings(interval_function="random", characteristic_length=5, seed=10),
            )
            second = process_image(
                source,
                PixelSortSettings(interval_function="random", characteristic_length=5, seed=10),
            )
            different = process_image(
                source,
                PixelSortSettings(interval_function="random", characteristic_length=5, seed=11),
            )
            self.assertEqual(first.tobytes(), second.tobytes())
            self.assertNotEqual(first.tobytes(), different.tobytes())
            first.close()
            second.close()
            different.close()
        finally:
            source.close()

    def test_random_and_wave_intervals_use_seeded_inherited_widths(self):
        row = [(0, 0, 0, 255)] * 30
        random_intervals = detect_intervals(row, "random", 0.0, 1.0, 10, random.Random(1))
        wave_intervals = detect_intervals(row, "waves", 0.0, 1.0, 5, random.Random(1))
        self.assertEqual(random_intervals[:3], [(1, 9), (9, 16), (16, 18)])
        self.assertEqual(wave_intervals[:3], [(0, 7), (7, 21), (21, 27)])

    def test_file_edges_delimit_all_regions(self):
        row = [(0, 0, 0, 255)] * 8
        intervals = detect_intervals(
            row,
            "file-edges",
            0.5,
            1.0,
            10,
            random.Random(1),
            [0, 0, 255, 255, 255, 0, 0, 0],
        )
        self.assertEqual(intervals, [(0, 2), (2, 5), (5, 8)])

    def test_dedicated_rng_is_used_without_global_random_state(self):
        source = make_image(32, 2)
        random.seed(123)
        before = random.getstate()
        rendered = process_image(source, PixelSortSettings(interval_function="random", seed=3))
        after = random.getstate()
        self.assertEqual(before, after)
        rendered.close()
        source.close()

    def test_threshold_mode_honors_both_bounds(self):
        source = Image.new("RGBA", (4, 1))
        for x, value in enumerate((0.1, 0.3, 0.6, 0.9)):
            channel = int(value * 255)
            source.putpixel((x, 0), (channel, channel, channel, 255))
        rendered = process_image(
            source,
            PixelSortSettings(
                interval_function="threshold",
                lower_threshold=0.25,
                upper_threshold=0.7,
                seed=1,
            ),
        )
        self.assertEqual(rendered.size, source.size)
        rendered.close()
        source.close()

    def test_mask_black_preserves_pixels(self):
        source = Image.new("RGBA", (4, 1))
        values = [(255, 0, 0, 255), (0, 0, 0, 255), (0, 0, 255, 255), (255, 255, 255, 255)]
        for x, value in enumerate(values):
            source.putpixel((x, 0), value)
        mask = Image.new("L", (4, 1), 0)
        mask.putpixel((2, 0), 255)
        mask.putpixel((3, 0), 255)
        rendered = process_image(
            source, PixelSortSettings(interval_function="none", seed=1), mask=mask
        )
        self.assertEqual(rendered.getpixel((0, 0)), values[0])
        self.assertEqual(rendered.getpixel((1, 0)), values[1])
        self.assertEqual(
            sorted(rendered.getpixel((x, 0))[:3] for x in (2, 3)),
            sorted(values[x][:3] for x in (2, 3)),
        )
        source.close()
        mask.close()
        rendered.close()

    def test_angle_returns_original_dimensions(self):
        source = make_image(20, 12)
        rendered = process_image(
            source, PixelSortSettings(interval_function="none", angle=45, seed=1)
        )
        self.assertEqual(rendered.size, source.size)
        rendered.close()
        source.close()

    def test_angle_matches_visible_wave_sorting_direction(self):
        source = Image.new("RGBA", (41, 41), (0, 0, 0, 255))
        source.putpixel((20, 20), (255, 255, 255, 255))
        try:
            for angle, expected_vertical_direction in ((45, -1), (315, 1)):
                with self.subTest(angle=angle):
                    rendered = process_image(
                        source,
                        PixelSortSettings(
                            interval_function="waves",
                            characteristic_length=1000,
                            angle=angle,
                            seed=1,
                        ),
                    )
                    try:
                        _, brightest_x, brightest_y = max(
                            (rendered.getpixel((x, y))[0], x, y)
                            for y in range(rendered.height)
                            for x in range(rendered.width)
                        )
                        self.assertGreater(brightest_x, source.width // 2)
                        self.assertEqual(
                            -1 if brightest_y < source.height // 2 else 1,
                            expected_vertical_direction,
                        )
                    finally:
                        rendered.close()
        finally:
            source.close()


class ImagingAndExportTests(unittest.TestCase):
    def test_normalization_applies_orientation_and_rejects_animation(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            animation_path = __import__("pathlib").Path(directory) / "animation.gif"
            first = Image.new("RGBA", (2, 2), (0, 0, 0, 255))
            second = Image.new("RGBA", (2, 2), (255, 255, 255, 255))
            first.save(animation_path, save_all=True, append_images=[second], duration=100, loop=0)
            first.close()
            second.close()
            with self.assertRaises(ValidationError) as context:
                normalize_image(animation_path)
        self.assertEqual(context.exception.category, "animated-or-multipage")

    def test_binary_image_requires_exact_dimensions(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory) / "mask.png"
            Image.new("L", (2, 2), 255).save(path)
            with self.assertRaises(ValidationError):
                normalize_binary_image(path, (3, 3))

    def test_binary_image_is_normalized_to_one_bit(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory) / "mask.png"
            Image.new("L", (2, 1), 127).save(path)
            binary = normalize_binary_image(path, (2, 1))
            self.assertEqual(binary.mode, "1")
            self.assertEqual(binary.getpixel((0, 0)), 0)
            binary.close()

    def test_atomic_png_and_jpeg_exports(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            source = make_image(6, 4)
            png = Path(directory) / "out.png"
            jpg = Path(directory) / "out.jpg"
            save_png(source, png)
            save_jpeg(source, jpg)
            with Image.open(png) as saved_png:
                self.assertEqual(saved_png.mode, "RGBA")
                self.assertFalse(saved_png.getexif())
            with Image.open(jpg) as saved_jpg:
                self.assertEqual(saved_jpg.mode, "RGB")
            source.close()


if __name__ == "__main__":
    unittest.main()
