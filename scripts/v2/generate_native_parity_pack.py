from __future__ import annotations

import struct
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "reference" / "python"))

from chromasunder_reference.enums import IntervalFunction, SortingFunction  # noqa: E402
from chromasunder_reference.models import PixelSortSettings  # noqa: E402
from chromasunder_reference.renderer import process_image  # noqa: E402

SORTING_MODES = (
    SortingFunction.LIGHTNESS,
    SortingFunction.HUE,
    SortingFunction.SATURATION,
    SortingFunction.INTENSITY,
    SortingFunction.MINIMUM,
)
INTERVAL_MODES = (
    IntervalFunction.NONE,
    IntervalFunction.THRESHOLD,
    IntervalFunction.EDGES,
    IntervalFunction.FILE,
    IntervalFunction.FILE_EDGES,
)
ANGLES = (0.0, 90.0, 180.0, 270.0)
MASKS = (None, "all-on.png", "all-off.png", "gapped.png")


def _binary(path: Path) -> tuple[Image.Image, bytes]:
    with Image.open(path) as opened:
        grayscale = opened.convert("L")
        values = bytes(1 if value >= 128 else 0 for value in grayscale.getdata())
        return grayscale.point(lambda value: 255 if value >= 128 else 0, mode="1"), values


def main() -> None:
    destination = ROOT / "testdata" / "golden-v1" / "native-cardinal-parity.bin"
    with Image.open(ROOT / "testdata" / "sources" / "matrix.png") as opened:
        source = opened.convert("RGBA")
    masks = [_binary(ROOT / "testdata" / "masks" / name) for name in MASKS[1:]]
    interval_images = [
        _binary(ROOT / "testdata" / "interval-images" / "runs.png"),
        _binary(ROOT / "testdata" / "interval-images" / "edges.png"),
    ]
    expected: list[tuple[int, int, int, int, bytes]] = []
    for sorting_index, sorting_mode in enumerate(SORTING_MODES):
        for interval_index, interval_mode in enumerate(INTERVAL_MODES):
            interval_image = None
            if interval_mode is IntervalFunction.FILE:
                interval_image = interval_images[0][0]
            elif interval_mode is IntervalFunction.FILE_EDGES:
                interval_image = interval_images[1][0]
            for angle_index, angle in enumerate(ANGLES):
                for mask_index in range(len(MASKS)):
                    settings = PixelSortSettings(
                        interval_function=interval_mode,
                        sorting_function=sorting_mode,
                        lower_threshold=0.21,
                        upper_threshold=0.8,
                        characteristic_length=3,
                        angle=angle,
                        randomness=0.0,
                        seed=8675309,
                    )
                    rendered = process_image(
                        source,
                        settings,
                        mask=None if mask_index == 0 else masks[mask_index - 1][0],
                        interval_image=interval_image,
                    )
                    expected.append(
                        (
                            sorting_index,
                            interval_index,
                            angle_index,
                            mask_index,
                            rendered.tobytes(),
                        )
                    )
                    rendered.close()

    with destination.open("wb") as output:
        output.write(b"CSPAR2\0\0")
        output.write(struct.pack("<III", source.width, source.height, len(expected)))
        output.write(source.tobytes())
        for _, values in masks:
            output.write(values)
        for _, values in interval_images:
            output.write(values)
        for sorting, interval, angle, mask, rgba in expected:
            output.write(bytes((sorting, interval, angle, mask)))
            output.write(rgba)
    source.close()
    for image, _ in masks + interval_images:
        image.close()
    print(f"wrote {len(expected)} cases to {destination}")


if __name__ == "__main__":
    main()
