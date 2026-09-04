#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from chromasunder_reference import PixelSortSettings, render_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Render an image with frozen V1 semantics.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--settings-json", type=Path, required=True)
    parser.add_argument("--mask", type=Path)
    parser.add_argument("--interval-image", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-rgba", type=Path)
    parser.add_argument("--print-sha256", action="store_true")
    args = parser.parse_args()
    if args.output is None and args.output_rgba is None and not args.print_sha256:
        parser.error("request --output, --output-rgba, or --print-sha256")

    document = json.loads(args.settings_json.read_text(encoding="utf-8"))
    settings = PixelSortSettings.from_dict(document.get("settings", document))
    rendered = render_file(
        args.source,
        settings,
        mask_path=args.mask,
        interval_path=args.interval_image,
    )
    try:
        rgba = rendered.tobytes()
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            rendered.save(args.output, format="PNG", compress_level=9)
        if args.output_rgba:
            args.output_rgba.parent.mkdir(parents=True, exist_ok=True)
            args.output_rgba.write_bytes(rgba)
        if args.print_sha256:
            print(hashlib.sha256(rgba).hexdigest())
    finally:
        rendered.close()


if __name__ == "__main__":
    main()
