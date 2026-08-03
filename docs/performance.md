# Performance Measurements

These measurements compare implementations on one development host. They are
useful for detecting regressions and choosing between experiments, not as
universal timing promises.

## Environment

- CPU: AMD Ryzen 7 7840HS, 8 cores / 16 threads
- RAM: 30 GiB
- OS: Fedora Linux, kernel 7.1.5-201.fc44.x86_64
- Python: 3.13.5
- Pillow: 11.1.0 (the project requirement remains `Pillow>=10.0`)
- Baseline commit: `76cf929`

## Methodology

`python -m benchmarks.rendering` generates deterministic RGBA sources, masks,
and interval images before timing. The sources combine gradients, repeated
high-frequency colors, hard transitions, and varied alpha. Mask fixtures cover
sparse, dense, enabled, disabled, and alternating patterns; interval fixtures
cover black, white, alternating, striped, and gradient patterns.

Each important case receives one warm-up and three measured iterations. Every
iteration runs in a fresh process under `/usr/bin/time -v`; elapsed figures are
from `time.perf_counter_ns()` and RSS is GNU time's maximum resident set.
Fixtures are decoded and normalized before the render timer. PNG encoding is
timed separately. `--profile` stores cProfile data for call-level analysis.
The small `matrix` suite covers all interval and sorting modes with no, sparse,
and dense masks at 0, 45, and 90 degrees. It is correctness-oriented and is not
used to claim speedups.

## Pre-V1.3 Baseline

All measured outputs were RGBA at source dimensions. Times show total median
with measured min/max; RSS shows the median fresh-process peak.

| Case | Render settings | Total median (min-max) | Peak RSS |
|---|---|---:|---:|
| 1920x1080 | none, lightness, 0 degrees | 1.924 s (1.880-1.951) | 57.5 MiB |
| 1920x1080 | threshold, hue, dense mask | 3.532 s (3.478-3.558) | 57.4 MiB |
| 1920x1080 | file, intensity, sparse mask | 0.512 s (0.510-0.515) | 58.1 MiB |
| 1920x1080 | waves, minimum, 90 degrees | 2.294 s (2.268-2.349) | 65.7 MiB |
| 1920x1080 | edges, saturation, 45 degrees | 8.450 s (8.412-8.694) | 138.7 MiB |

For the unrotated `none` case, median source decode/normalization was 30 ms and
median PNG encoding was 61 ms; most elapsed time was therefore in row reading,
key calculation, sorting, and per-pixel output assignment. Expanded arbitrary
angle images substantially increase both render work and peak memory.

A cProfile run of that case recorded 1,923,840 sortable pixels. The profiler's
instrumentation increases wall time, so these values are used only to locate
work: `sorting_key()` consumed 3.629 s cumulative, including 1.024 s in
`colorsys.rgb_to_hls()`, while enum resolution accounted for 0.533 s. The
remaining row read/write and interval overhead was represented by 0.307 s of
self time in `process_image()` and `_sort_row()`; Pillow forward/inverse
rotation was absent in this 0-degree case.

Large-image results and each isolated V1.3 experiment are recorded below as
the stages are completed.
