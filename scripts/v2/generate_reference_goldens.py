#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "reference" / "python"))

from chromasunder_reference import PixelSortSettings, render_file  # noqa: E402

from chromasunder.core.models import PixelSortSettings as ProductionSettings  # noqa: E402
from chromasunder.core.processing import render_file as production_render_file  # noqa: E402

BASELINE = "v1-a5475cb-pillow-11.1.0"
DEFAULTS = {
    "interval_function": "none",
    "sorting_function": "lightness",
    "lower_threshold": 0.2,
    "upper_threshold": 0.8,
    "characteristic_length": 3,
    "angle": 0.0,
    "randomness": 0.0,
    "seed": 8675309,
}


def save_sources() -> None:
    sources = ROOT / "testdata" / "sources"
    masks = ROOT / "testdata" / "masks"
    intervals = ROOT / "testdata" / "interval-images"
    for directory in (sources, masks, intervals):
        directory.mkdir(parents=True, exist_ok=True)

    matrix = Image.new("RGBA", (7, 5))
    matrix.putdata(
        [
            (
                (x * 73 + y * 19) % 256,
                (x * 29 + y * 101) % 256,
                ((x // 2) * 53 + y * 41) % 256,
                (x * 47 + y * 67) % 256,
            )
            for y in range(5)
            for x in range(7)
        ]
    )
    special = [
        (0, 0, 0, 0),
        (255, 255, 255, 255),
        (255, 0, 0, 64),
        (0, 255, 0, 128),
        (0, 0, 255, 192),
        (20, 40, 60, 32),
        (60, 40, 20, 224),
    ]
    for x, pixel in enumerate(special):
        matrix.putpixel((x, 0), pixel)
    matrix.save(sources / "matrix.png")
    matrix.close()

    ties = Image.new("RGBA", (6, 2))
    ties.putdata(
        [
            (10, 20, 30, 255),
            (30, 20, 10, 32),
            (10, 20, 30, 64),
            (200, 10, 10, 96),
            (10, 200, 10, 128),
            (10, 10, 200, 160),
        ]
        * 2
    )
    ties.save(sources / "ties-alpha.png")
    ties.close()

    Image.new("RGBA", (1, 1), (17, 33, 65, 127)).save(sources / "tiny.png")
    asymmetric = Image.new("RGBA", (3, 2))
    asymmetric.putdata(
        [
            (10, 20, 30, 0),
            (200, 50, 20, 51),
            (70, 80, 90, 102),
            (100, 110, 120, 153),
            (5, 240, 100, 204),
            (160, 170, 180, 255),
        ]
    )
    asymmetric.save(sources / "asymmetric.png")
    asymmetric.close()

    for name, predicate in {
        "all-on": lambda x, y: True,
        "all-off": lambda x, y: False,
        "sparse": lambda x, y: (x + y * 7) % 7 == 0,
        "gapped": lambda x, y: (x + y) % 2 == 0,
    }.items():
        image = Image.new("L", (7, 5))
        image.putdata([255 if predicate(x, y) else 0 for y in range(5) for x in range(7)])
        image.save(masks / f"{name}.png")
        image.close()

    for name, predicate in {
        "runs": lambda x, y: x in (1, 2, 5, 6),
        "edges": lambda x, y: x >= 3,
    }.items():
        image = Image.new("L", (7, 5))
        image.putdata([255 if predicate(x, y) else 0 for y in range(5) for x in range(7)])
        image.save(intervals / f"{name}.png")
        image.close()


def cases() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for mode in ("lightness", "hue", "saturation", "intensity", "minimum"):
        result.append({"name": f"sort-{mode}", "sorting_function": mode})
    for mode in ("none", "threshold", "edges", "random", "waves"):
        result.append({"name": f"interval-{mode}", "interval_function": mode})
    result.extend(
        [
            {
                "name": "interval-file",
                "interval_function": "file",
                "interval_image": "runs.png",
            },
            {
                "name": "interval-file-edges",
                "interval_function": "file-edges",
                "interval_image": "edges.png",
                "lower_threshold": 0.5,
            },
        ]
    )
    for mask in ("all-on", "all-off", "sparse", "gapped"):
        result.append({"name": f"mask-{mask}", "mask": f"{mask}.png"})
    for angle in (0, 90, 180, 270, 45, 315):
        result.append({"name": f"angle-{angle}", "angle": angle})
    result.extend(
        [
            {"name": "transparency-ties", "source": "ties-alpha.png"},
            {"name": "tiny", "source": "tiny.png"},
            {"name": "asymmetric", "source": "asymmetric.png", "angle": 90},
        ]
    )
    return result


def main() -> None:
    save_sources()
    settings_directory = ROOT / "testdata" / "settings"
    golden_directory = ROOT / "testdata" / "golden-v1"
    settings_directory.mkdir(parents=True, exist_ok=True)
    golden_directory.mkdir(parents=True, exist_ok=True)
    manifest_cases = []

    for case in cases():
        name = str(case["name"])
        source_name = str(case.get("source", "matrix.png"))
        mask_name = case.get("mask")
        interval_name = case.get("interval_image")
        settings_values = DEFAULTS | {key: value for key, value in case.items() if key in DEFAULTS}
        settings_path = settings_directory / f"{name}.json"
        settings_path.write_text(json.dumps(settings_values, indent=2) + "\n", encoding="utf-8")
        source_path = ROOT / "testdata" / "sources" / source_name
        mask_path = ROOT / "testdata" / "masks" / str(mask_name) if mask_name else None
        interval_path = (
            ROOT / "testdata" / "interval-images" / str(interval_name) if interval_name else None
        )

        reference = render_file(
            source_path,
            PixelSortSettings.from_dict(settings_values),
            mask_path=mask_path,
            interval_path=interval_path,
        )
        production = production_render_file(
            str(source_path),
            ProductionSettings.from_dict(settings_values),
            mask_path=str(mask_path) if mask_path else None,
            interval_path=str(interval_path) if interval_path else None,
        )
        try:
            raw = reference.tobytes()
            if raw != production.tobytes():
                raise RuntimeError(f"reference output differs from V1 production for {name}")
            output_name = f"{name}.rgba"
            (golden_directory / output_name).write_bytes(raw)
            manifest_cases.append(
                {
                    "name": name,
                    "source": f"sources/{source_name}",
                    "mask": f"masks/{mask_name}" if mask_name else None,
                    "interval_image": (
                        f"interval-images/{interval_name}" if interval_name else None
                    ),
                    "settings": f"settings/{name}.json",
                    "output": f"golden-v1/{output_name}",
                    "dimensions": list(reference.size),
                    "rgba_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
        finally:
            reference.close()
            production.close()

    manifest = {"baseline": BASELINE, "pixel_format": "RGBA8", "cases": manifest_cases}
    (ROOT / "testdata" / "golden-v1" / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Generated and validated {len(manifest_cases)} V1 golden cases")


if __name__ == "__main__":
    main()
