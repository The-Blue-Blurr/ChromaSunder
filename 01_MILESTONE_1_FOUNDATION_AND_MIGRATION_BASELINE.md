# Milestone 1 — V2 Foundation and Migration Baseline

## Objective

Create a safe, reproducible V2 development foundation without porting the renderer yet. At the end of this milestone, the project must have:

- a preserved V1 behavior baseline
- a minimal standalone Python reference renderer
- a clean V2 repository skeleton
- a standalone C++20/CMake engine smoke test
- Flutter desktop/mobile scaffolding
- working Dart FFI -> C++ smoke integration on Fedora
- Windows CI build coverage
- Android native/Flutter build proof for API 33, ARM64/x86_64

Do **not** begin porting pixel-sorting behavior until every hard gate at the end of this file passes.

## Preflight — protect the current repository

1. From the uploaded/current repository root, record:

   ```bash
   git status --short
   git branch --show-current
   git rev-parse HEAD
   git log -1 --oneline
   ```

2. Do not assume the working tree is clean. The inspected archive contained uncommitted/untracked V1.3 files. Preserve them.

3. If branch creation would leave user changes at risk, create a safe patch/backup or commit only when explicitly appropriate. Never discard those changes.

4. Run the current V1 test suite before restructuring:

   ```bash
   python -m pytest -q
   ```

   Expected baseline from the supplied archive: `1356 passed, 25 subtests passed`. If the live checkout differs, record the actual result and investigate before proceeding.

5. Run current benchmark commands supported by `benchmarks/rendering.py`. At minimum capture the quick suite; if the machine can reasonably run it, capture the 6000x4000 suite as well. Preserve machine-readable output where available.

6. Write `docs/v2/V1_MIGRATION_BASELINE.md` containing:
   - baseline commit SHA
   - current branch
   - Python version
   - Pillow version
   - pytest result/count
   - benchmark command(s) and result(s)
   - date/environment notes
   - any dirty-tree files intentionally preserved

## Create the V2 branch safely

Preferred branch name:

```text
dev/v2-rewrite
```

If a branch with that name already exists, inspect it rather than overwriting it.

The branch should originate from the chosen V1 migration baseline. Preserve V1 history in Git.

Do not merge V2 into `main` during this milestone.

## Replace obsolete agent guidance

The existing V1 `AGENTS.md` contains scope constraints that contradict approved V2 requirements such as Live Preview and drag-and-drop.

On the V2 branch:

1. Replace or rewrite root `AGENTS.md` so it points agents to the V2 instruction pack/project docs.
2. Explicitly state that V1 feature prohibitions are not authoritative for V2.
3. Include the essential invariants from `00_README_AND_AGENT_OPERATING_RULES.md`.
4. Keep the guidance concise enough that future coding agents actually read it.

Do not remove attribution/license instructions.

## Extract the temporary Python reference renderer

### Goal

Retain only enough Python to answer this question during migration:

> Given a known source, settings, optional mask, and optional interval image, what does the V1-compatible renderer produce?

Do not carry the GTK application or worker process into the reference package.

### Create

```text
reference/python/
```

Recommended structure:

```text
reference/python/
├── README.md
├── requirements.txt or documented dependency note
├── chromasunder_reference/
│   ├── __init__.py
│   ├── enums.py
│   ├── models.py
│   ├── validation.py
│   ├── sorting.py
│   ├── intervals.py
│   ├── imaging.py
│   └── renderer.py
└── render_reference.py
```

Copy/extract only the semantic code required to render fixtures. Remove imports of:

- GTK / PyGObject
- GUI modules
- worker/controller modules
- GSettings
- application startup code

It is acceptable for the reference renderer to depend on Pillow and the Python standard library.

### CLI contract

Provide a deterministic CLI similar to:

```bash
python reference/python/render_reference.py \
  --source testdata/sources/example.png \
  --settings-json testdata/settings/example.json \
  --output /tmp/reference.png
```

Optional inputs:

```bash
--mask path
--interval-image path
```

Also support a raw/hash-oriented mode suitable for tests, for example:

```bash
--output-rgba /tmp/output.rgba
--print-sha256
```

The exact CLI can vary, but it must make automated C++ parity tests easy and must not require launching the V1 app.

### Preserve reference semantics

Extract the current behavior from:

- `src/chromasunder/core/enums.py`
- `models.py`
- `validation.py`
- `sorting.py`
- `intervals.py`
- `processing.py`
- relevant image-loading behavior from `imaging.py`
- `tests/reference_renderer.py`

Do not "clean up" semantics during extraction. The reference package exists to preserve historical behavior, including odd edge cases.

### Golden test data

Create/organize:

```text
testdata/
├── sources/
├── masks/
├── interval-images/
├── settings/
└── golden-v1/
```

Prefer small synthetic fixtures whose expected behavior is understandable and whose repository size remains small.

Include cases for:

- every sorting mode
- deterministic interval modes
- Random and Waves reference outputs for historical inspection, even though V2 RNG need not match them
- transparency
- tied sort keys
- all-on/all-off/sparse/gapped masks
- File/File Edges interval images
- cardinal angles
- at least two non-cardinal historical-angle examples
- tiny images and asymmetric dimensions

Create a manifest containing for each golden case:

- source/aux/settings file
- reference output dimensions
- RGBA SHA-256
- encoded output SHA-256 if stored encoded
- baseline engine/version identifier

### Reference validation gate

Run the extracted renderer against preserved fixtures and verify its outputs match the original V1 production/reference behavior for the same cases.

Only after this succeeds may the old GUI/worker code start becoming irrelevant to the V2 branch.

## Establish V2 repository layout

Create the following high-level structure without prematurely deleting V1 reference material:

```text
app/
engine/
packages/chromasunder_native/
reference/python/
testdata/
benchmarks/
docs/v2/
scripts/v2/
.github/workflows/
```

Keep V1 source temporarily until extraction and baseline gates are proven. Do not perform the final V1 deletion in Milestone 1.

## Scaffold the standalone C++ engine

### CMake

Create a root/native CMake project under `engine/`.

Minimum requirements:

- `cmake_minimum_required` appropriate for supported toolchains
- C++20 required, extensions off unless specifically justified
- library target for the future engine
- separate test target
- warnings enabled in development
- Windows/MSVC compatibility
- install/export layout suitable for native packaging

Recommended initial structure:

```text
engine/
├── CMakeLists.txt
├── include/chromasunder/
│   ├── version.hpp
│   └── smoke.hpp
├── src/
│   └── smoke.cpp
└── tests/
    └── smoke_test.cpp
```

Do not add image-processing dependencies yet merely to prove the toolchain.

### C ABI smoke layer

Create the smallest possible exported C interface, for example:

```c
uint32_t cs_abi_version(void);
int32_t cs_smoke_add(int32_t a, int32_t b);
```

Use explicit export visibility macros for Windows/Linux.

The purpose is to prove packaging/bindings, not define the final API yet.

### Standalone commands

The following should work independently of Flutter:

```bash
cmake -S engine -B build/engine -DCMAKE_BUILD_TYPE=Debug
cmake --build build/engine
ctest --test-dir build/engine --output-on-failure
```

Also establish release and sanitizer presets where practical, but do not block the initial smoke proof on sanitizer portability.

## Scaffold Flutter application

Use current Flutter tooling rather than hand-creating platform projects.

Suggested command:

```bash
flutter create \
  --project-name chromasunder \
  --org io.github.the_blue_blurr \
  --platforms=linux,windows,android \
  app
```

Preserve the existing application identity/branding namespace where appropriate. Verify actual package/application IDs before finalizing platform metadata.

Do not create macOS/iOS platforms for MVP unless Flutter scaffolding requires harmless placeholders; they are not build gates.

## Scaffold native FFI package

Preferred current Flutter-native approach:

```bash
flutter create \
  --template=package_ffi \
  --project-name chromasunder_native \
  packages/chromasunder_native
```

Integrate `ffigen` so Dart bindings are generated from the C ABI header.

### Single source of native truth

Do not duplicate the engine implementation in the package.

Preferred relationship:

```text
packages/chromasunder_native build hook
            ↓
       invokes/reuses
            ↓
       engine/CMake
            ↓
   packages native asset
```

If the current native-assets hook APIs require a different practical arrangement, keep `engine/` authoritative and document the adaptation.

Do not switch to a larger plugin wrapper unless the package_ffi/native-assets path is proven inadequate; ask if uncertain.

## Prove Dart -> FFI -> C++ on Fedora

Create a tiny handwritten Dart service above generated bindings, for example:

```text
NativeSmokeService
```

The Flutter UI should invoke the smoke function and display/assert the result.

Run:

```bash
flutter doctor -v
flutter pub get
flutter run -d linux
flutter test
flutter build linux
```

Record Fedora version, Flutter version, Dart version, Clang/CMake/Ninja versions, and any extra Fedora packages required in `docs/v2/DEVELOPMENT_ENVIRONMENT.md`.

Do not hide Fedora-specific setup behind undocumented shell state.

## Windows CI proof

Add a GitHub Actions Windows job using a supported Windows/MSVC Flutter environment.

At minimum:

1. checkout
2. install/configure Flutter
3. print Flutter version
4. configure/build C++ engine with MSVC
5. run native tests
6. `flutter pub get`
7. regenerate/verify FFI bindings as appropriate
8. `flutter analyze`
9. `flutter test`
10. `flutter build windows --release` or equivalent release smoke build

A CI build is not a substitute for later real Windows validation, but it is a hard anti-drift gate from this milestone onward.

## Android build proof

Configure Android minimum SDK to **33**.

Supported ABIs for V2 MVP:

- `arm64-v8a`
- `x86_64`

Do not intentionally include `armeabi-v7a`.

Build a smoke APK containing the native library and exercise the smoke FFI method in at least an Android test/emulator path where feasible.

At minimum prove:

```bash
flutter build apk
```

and inspect the APK to confirm the intended native architectures are present.

Do not add Play Store/App Bundle/release-store workflows.

## Dependency/license audit scaffold

Create:

```text
docs/v2/DEPENDENCIES.md
```

with a table for:

- package/library
- version
- purpose
- license
- source URL
- static/dynamic packaging notes
- platforms

Do not add all candidate codec libraries yet unless needed by the smoke build. This milestone establishes the audit process.

## CI quality baseline

Add/retain formatting/static-analysis jobs appropriate to the new stack:

C++:

- build warnings treated seriously; decide whether CI uses `-Werror` only after avoiding third-party warning contamination

Dart/Flutter:

```bash
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
```

Python reference:

- keep a small test that proves its CLI/goldens remain reproducible while it exists

## Required documentation produced by this milestone

- `docs/v2/V1_MIGRATION_BASELINE.md`
- `docs/v2/DEVELOPMENT_ENVIRONMENT.md`
- `docs/v2/DEPENDENCIES.md`
- `docs/v2/ARCHITECTURE.md` with the initial Flutter -> Dart service -> C ABI -> C++ boundary
- updated root `AGENTS.md`

## Hard completion gates

Mark Milestone 1 complete only when all are PASS:

- [ ] Pre-migration V1 test suite result recorded and understood.
- [ ] V1 benchmark baseline recorded.
- [ ] User's dirty/uncommitted work preserved.
- [ ] V2 rewrite branch created safely.
- [ ] V1-only `AGENTS.md` restrictions replaced with V2 guidance.
- [ ] Standalone Python reference renderer runs without GTK/worker/application imports.
- [ ] Reference renderer reproduces preserved V1 golden outputs.
- [ ] Golden manifest with raw RGBA hashes exists.
- [ ] Standalone C++20/CMake library builds and tests on Linux.
- [ ] Dart FFI generated bindings call C++ successfully on Fedora.
- [ ] Flutter Linux app runs locally on Fedora.
- [ ] Flutter Linux release build succeeds.
- [ ] Windows CI builds/tests the C++ engine.
- [ ] Windows CI runs Flutter analyze/tests and builds Windows.
- [ ] Android minSdk is 33.
- [ ] Android APK containing native C++ code builds for intended 64-bit ABIs.
- [ ] Native dependency/license audit process exists.
- [ ] No pixel-sorting renderer has been prematurely ported.

## End-of-milestone handoff

Include exact commands/results for:

- V1 pytest baseline
- reference golden validation
- Linux CMake/CTest
- Fedora Flutter analyze/test/build
- Windows CI run URL/result
- Android APK build and ABI inspection

State explicitly that Milestone 2 may begin only if every hard gate above is green or the user explicitly accepts a documented exception.
