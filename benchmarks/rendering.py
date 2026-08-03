"""Deterministic V1.3 rendering benchmark orchestrator.

Run ``python -m benchmarks.rendering --suite quick`` for representative cases or
``--suite large`` for the required 6000x4000 validation sweep. GNU ``time`` runs
every measurement in a fresh process so peak RSS values are independent.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median

from PIL import Image, ImageOps
from PIL import __version__ as pillow_version

from chromasunder.core.enums import IntervalFunction, SortingFunction


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    size: tuple[int, int]
    interval: str = "none"
    sorting: str = "lightness"
    mask: str = "none"
    interval_image: str = "alternating"
    angle: float = 0.0


QUICK_CASES = (
    BenchmarkCase("1080p-none", (1920, 1080)),
    BenchmarkCase("1080p-threshold-dense", (1920, 1080), "threshold", "hue", "dense"),
    BenchmarkCase("1080p-file-alternating", (1920, 1080), "file", "intensity", "sparse"),
    BenchmarkCase("1080p-waves-90", (1920, 1080), "waves", "minimum", "none", angle=90),
    BenchmarkCase("1080p-edges-45", (1920, 1080), "edges", "saturation", "none", angle=45),
)

LARGE_CASES = (
    BenchmarkCase("24mp-none", (6000, 4000)),
    BenchmarkCase("24mp-threshold-dense", (6000, 4000), "threshold", "hue", "dense"),
    BenchmarkCase("24mp-random-sparse", (6000, 4000), "random", "intensity", "sparse"),
    BenchmarkCase("24mp-file-edges", (6000, 4000), "file-edges", "minimum", "none"),
    BenchmarkCase("24mp-waves-90", (6000, 4000), "waves", "lightness", "none", angle=90),
    BenchmarkCase("24mp-none-45", (6000, 4000), "none", "lightness", "none", angle=45),
)


def correctness_cases() -> tuple[BenchmarkCase, ...]:
    return tuple(
        BenchmarkCase(
            f"matrix-{interval.value}-{sorting.value}-{mask}-{angle:g}",
            (16, 9),
            interval.value,
            sorting.value,
            mask,
            angle=angle,
        )
        for interval in IntervalFunction
        for sorting in SortingFunction
        for mask in ("none", "sparse", "dense")
        for angle in (0.0, 90.0, 45.0)
    )


def _channel_gradient(size: tuple[int, int], *, horizontal: bool, invert: bool) -> Image.Image:
    gradient = Image.linear_gradient("L")
    if horizontal:
        gradient = gradient.rotate(90, expand=True)
    if invert:
        gradient = ImageOps.invert(gradient)
    resized = gradient.resize(size, Image.Resampling.BILINEAR)
    gradient.close()
    return resized


def create_source(path: Path, size: tuple[int, int]) -> None:
    red = _channel_gradient(size, horizontal=True, invert=False)
    green = _channel_gradient(size, horizontal=False, invert=True)
    tile = Image.new("L", (8, 8))
    tile.putdata([64 if (x + y) % 3 else 224 for y in range(8) for x in range(8)])
    blue = tile.resize(size, Image.Resampling.NEAREST)
    alpha = _channel_gradient(size, horizontal=True, invert=True)
    source = Image.merge("RGBA", (red, green, blue, alpha))
    source.save(path, compress_level=1)
    source.close()
    red.close()
    green.close()
    blue.close()
    alpha.close()
    tile.close()


def _striped_binary(size: tuple[int, int], values: list[int]) -> Image.Image:
    pattern = Image.new("L", (len(values), 1))
    pattern.putdata(values)
    image = pattern.resize(size, Image.Resampling.NEAREST)
    pattern.close()
    return image


def create_mask(path: Path, size: tuple[int, int], kind: str) -> None:
    if kind == "sparse":
        image = _striped_binary(size, [255] + [0] * 15)
    elif kind == "dense":
        image = _striped_binary(size, [0] + [255] * 15)
    elif kind == "all-enabled":
        image = Image.new("L", size, 255)
    elif kind == "all-disabled":
        image = Image.new("L", size, 0)
    else:
        image = _striped_binary(size, [0, 255])
    image.save(path, compress_level=1)
    image.close()


def create_interval_image(path: Path, size: tuple[int, int], kind: str) -> None:
    if kind == "black":
        image = Image.new("L", size, 0)
    elif kind == "white":
        image = Image.new("L", size, 255)
    elif kind == "stripes":
        image = _striped_binary(size, [0] * 8 + [255] * 8)
    elif kind == "gradient":
        gradient = _channel_gradient(size, horizontal=True, invert=False)
        image = gradient.point(lambda value: 255 if value >= 128 else 0)
        gradient.close()
    else:
        image = _striped_binary(size, [0, 255])
    image.save(path, compress_level=1)
    image.close()


def _environment() -> dict[str, str | int]:
    return {
        "cpu": platform.processor() or platform.machine(),
        "logical_cpus": os.cpu_count() or 0,
        "os": platform.platform(),
        "python": platform.python_version(),
        "pillow": pillow_version,
        "commit": subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
    }


def _peak_rss_kib(time_report: str) -> int:
    match = re.search(r"Maximum resident set size \(kbytes\): (\d+)", time_report)
    if match is None:
        raise RuntimeError("GNU time report did not include peak RSS")
    return int(match.group(1))


def run_case(case: BenchmarkCase, repetitions: int, profile: bool) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="chromasunder-benchmark-") as directory:
        root = Path(directory)
        source = root / "source.png"
        mask = root / "mask.png"
        interval = root / "interval.png"
        create_source(source, case.size)
        if case.mask != "none":
            create_mask(mask, case.size, case.mask)
        if case.interval in {"file", "file-edges"}:
            create_interval_image(interval, case.size, case.interval_image)

        runs: list[dict[str, object]] = []
        total_runs = repetitions + 1
        for iteration in range(total_runs):
            report = root / f"time-{iteration}.txt"
            output = root / f"output-{iteration}.png"
            profile_path = root / "render.prof" if profile and iteration == total_runs - 1 else None
            command = [
                "/usr/bin/time",
                "-v",
                "-o",
                str(report),
                sys.executable,
                "-m",
                "benchmarks.worker_case",
                "--source",
                str(source),
                "--output",
                str(output),
                "--interval",
                case.interval,
                "--sorting",
                case.sorting,
                "--angle",
                str(case.angle),
            ]
            if case.mask != "none":
                command.extend(("--mask", str(mask)))
            if case.interval in {"file", "file-edges"}:
                command.extend(("--interval-image", str(interval)))
            if profile_path is not None:
                command.extend(("--profile", str(profile_path)))
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
            result = json.loads(completed.stdout)
            result["peak_rss_kib"] = _peak_rss_kib(report.read_text())
            if iteration:
                runs.append(result)

        elapsed = [int(run["total_ns"]) for run in runs]
        rss = [int(run["peak_rss_kib"]) for run in runs]
        summary: dict[str, object] = {
            "case": asdict(case),
            "runs": runs,
            "total_ns": {"median": median(elapsed), "min": min(elapsed), "max": max(elapsed)},
            "peak_rss_kib": {"median": median(rss), "min": min(rss), "max": max(rss)},
        }
        if profile_path is not None:
            summary["profile"] = str(Path.cwd() / f"{case.name}.prof")
            Path(summary["profile"]).write_bytes(profile_path.read_bytes())
        return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("quick", "large", "matrix"), default="quick")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--case", help="Run one named case from the selected suite")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

    cases = {
        "quick": QUICK_CASES,
        "large": LARGE_CASES,
        "matrix": correctness_cases(),
    }[args.suite]
    if args.case:
        cases = tuple(case for case in cases if case.name == args.case)
        if not cases:
            parser.error(f"unknown case for {args.suite} suite: {args.case}")
    result = {
        "environment": _environment(),
        "procedure": {"warmups": 1, "measured_repetitions": args.repetitions},
        "results": [run_case(case, args.repetitions, args.profile) for case in cases],
    }
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
