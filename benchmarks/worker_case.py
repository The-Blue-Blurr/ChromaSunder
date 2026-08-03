"""One fresh-process benchmark measurement."""

from __future__ import annotations

import argparse
import cProfile
import json
from pathlib import Path
from time import perf_counter_ns

from chromasunder.core.exporting import save_png
from chromasunder.core.imaging import normalize_binary_image, normalize_image
from chromasunder.core.models import PixelSortSettings
from chromasunder.core.processing import process_image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mask", type=Path)
    parser.add_argument("--interval-image", type=Path)
    parser.add_argument("--interval", required=True)
    parser.add_argument("--sorting", required=True)
    parser.add_argument("--angle", type=float, required=True)
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()

    total_started = perf_counter_ns()
    normalize_started = perf_counter_ns()
    source = normalize_image(args.source)
    normalized_ns = perf_counter_ns() - normalize_started
    mask = normalize_binary_image(args.mask, source.dimensions) if args.mask else None
    interval_image = (
        normalize_binary_image(args.interval_image, source.dimensions)
        if args.interval_image
        else None
    )
    settings = PixelSortSettings(
        interval_function=args.interval,
        sorting_function=args.sorting,
        angle=args.angle,
        lower_threshold=0.25,
        upper_threshold=0.75,
        characteristic_length=64,
        randomness=7.5,
        seed=8675309,
    )
    profiler = cProfile.Profile() if args.profile else None
    try:
        render_started = perf_counter_ns()
        if profiler:
            profiler.enable()
        rendered = process_image(
            source.image,
            settings,
            mask=mask,
            interval_image=interval_image,
        )
        if profiler:
            profiler.disable()
            profiler.dump_stats(args.profile)
        render_ns = perf_counter_ns() - render_started
        try:
            encode_started = perf_counter_ns()
            save_png(rendered, args.output)
            encode_ns = perf_counter_ns() - encode_started
            result = {
                "normalize_ns": normalized_ns,
                "render_ns": render_ns,
                "encode_ns": encode_ns,
                "total_ns": perf_counter_ns() - total_started,
                "dimensions": list(rendered.size),
                "mode": rendered.mode,
            }
        finally:
            rendered.close()
    finally:
        source.image.close()
        if mask is not None:
            mask.close()
        if interval_image is not None:
            interval_image.close()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
