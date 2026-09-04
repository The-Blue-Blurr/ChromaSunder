# V1 Migration Baseline

## Repository

- Baseline commit: `a5475cb3ad8558705d6a67dd4a3438392db0301d`
- Baseline commit summary: `a5475cb refactor: isolate source and output row access`
- Source branch: `dev/v1.3-rendering-performance`
- V2 branch: `dev/v2-rewrite`
- Date: 2026-09-04

The V2 branch was created directly from the baseline commit. Existing tracked and untracked work
was carried across the branch operation without being discarded.

## Environment

- Fedora Linux 44 Workstation, Linux `7.1.10-200.fc44.x86_64`
- CPU architecture: x86-64, 16 logical CPUs reported by Python
- Python: 3.13.5
- Pillow: 11.1.0

## Tests

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
```

Result: **PASS**, 1356 tests passed in 1.76 seconds. This matches the expected supplied-archive
count of 1356 tests; pytest does not print the unittest subtest count in quiet mode.

## Benchmarks

The first quick-suite invocation omitted `PYTHONPATH=src` and failed before running a case because
the V1 package was not installed in the active shell. The corrected commands were:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m benchmarks.rendering \
  --suite quick --output benchmarks/baselines/v1/fedora44-a5475cb-quick.json
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m benchmarks.rendering \
  --suite large --repetitions 1 \
  --output benchmarks/baselines/v1/fedora44-a5475cb-large.json
```

Both commands passed. The quick suite used one warmup and three measured repetitions. The large
6000x4000 suite used one warmup and one measured repetition to keep baseline runtime reasonable.
The JSON artifacts contain per-stage nanosecond timings and peak RSS measurements.

| Case | Median total | Median peak RSS |
|---|---:|---:|
| 1080p-none | 0.569 s | 58,892 KiB |
| 1080p-threshold-dense | 2.918 s | 58,956 KiB |
| 1080p-file-alternating | 0.482 s | 59,436 KiB |
| 1080p-waves-90 | 0.709 s | 67,636 KiB |
| 1080p-edges-45 | 7.152 s | 141,984 KiB |
| 24mp-none | 7.354 s | 401,848 KiB |
| 24mp-threshold-dense | 34.699 s | 401,728 KiB |
| 24mp-random-sparse | 4.750 s | 401,848 KiB |
| 24mp-file-edges | 8.259 s | 401,368 KiB |
| 24mp-waves-90 | 7.503 s | 496,420 KiB |
| 24mp-none-45 | 29.748 s | 1,306,828 KiB |

## Preserved Dirty Tree

The following pre-existing user work was intentionally preserved:

- modified `TODO.md`
- untracked `00_README_AND_AGENT_OPERATING_RULES.md`
- untracked milestone files `01_...md` through `06_...md`
- untracked `90_ARCHITECTURE_AND_PRODUCT_DECISIONS.md`
- untracked `91_TEST_GATE_MATRIX.md`
- untracked `92_DEPENDENCY_AND_LICENSE_POLICY.md`
- untracked `93_CURRENT_V1_REPO_MAP.md`
- untracked `TODO_(V1.3).md`
- untracked `V1.3_Instructions.md`

No backup patch was required because branch creation retained the complete worktree and was
immediately verified with `git status --short --branch`.
