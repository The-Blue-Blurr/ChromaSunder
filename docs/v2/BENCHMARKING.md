# Native Benchmarking

Build the release harness and capture JSON with:

```sh
cmake --preset release
cmake --build --preset release
../build/engine-release/chromasunder_engine_benchmark \
  --output ../benchmarks/baselines/v2/fedora44-m2-full.json
```

Use `--quick` for reduced dimensions during CI. The full suite includes 1920x1080 RGBA8 workloads
for lightness, hue, saturation, Random, Waves, mask-heavy, interval-heavy, and 0/45/90-degree paths,
plus 6000x4000 RGBA8 and RGBA16 workloads.

Each case records preparation, path generation, sorting/render core, total duration, estimator bytes,
process peak resident memory where supported, and an FNV-1a output hash. Synthetic cases report
decode, color-transform, and encode as JSON `null`; codec costs are intentionally not conflated with
the sorting benchmark. Codec microbenchmarks can populate those fields later.

Committed observations live under `benchmarks/baselines/v2/`. They are reproducibility artifacts,
not pass/fail time targets. Compare results only on similarly configured machines, worker counts,
build types, and dependency versions.
