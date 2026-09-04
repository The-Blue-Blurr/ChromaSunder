# Milestone 6 — V2 Replacement, Windows Validation, and Release Hardening

## Objective

Finish the V2 migration by validating the existing shared implementation on real Windows, hardening cross-platform determinism/release packaging, removing the temporary V1 implementation/reference runtime, rewriting repository documentation around V2, and making the repository exclusively the Flutter/C++ Chroma Sunder application.

Do not add unrelated post-MVP features during this milestone.

## 1. Pre-hardening freeze

Before cleanup/deletion:

1. Confirm Linux Milestone 4 gates remain green.
2. Confirm Android Milestone 5 gates remain green.
3. Confirm Windows CI remains green.
4. Record current V2 branch HEAD.
5. Run the complete cross-platform-compatible automated test suite.
6. Produce a backup/tag/reference for the final V1 baseline if it has not already been formally tagged.

Do not delete V1/reference files until permanent V2 tests/goldens are proven sufficient.

## 2. Real Windows environment

Obtain a real Windows 10 or Windows 11 x86-64 environment.

Windows hands-on validation is mandatory because CI compilation alone does not prove:

- native dialogs
- drag/drop
- HiDPI behavior
- window chrome
- file paths
- packaging/runtime dependencies

Record:

- Windows edition/version/build
- architecture
- display scale(s) tested
- Flutter build/toolchain version used

## 3. Windows build from V2 source

On Windows:

- checkout clean V2 branch
- install documented Flutter/Visual Studio C++ prerequisites
- configure/build native engine
- run native tests
- run `flutter doctor -v`
- run `flutter pub get`
- run `flutter analyze`
- run `flutter test`
- build release Windows app

Do not patch shared code with Windows-only hacks if a proper platform adapter or portable fix is possible.

## 4. Windows UI/manual validation

Test:

### Window/layout

- native Windows title bar owns minimize/maximize/close
- no custom frameless controls overlap native chrome
- toolbar layout remains recognizable
- preview/settings divider works
- window resize works
- window maximize/restore works
- saved geometry does not produce unusable off-screen window state

### HiDPI

At minimum test 100% and one high-DPI scale such as 150%/200% if hardware/environment permits.

Verify:

- Flutter visual UI remains sharp
- low-resolution preview target uses actual Flutter DPR
- text/controls do not clip
- drag/drop target remains correct

### File integration

- Open PNG/JPEG
- drag/drop source
- mask select/remove
- interval-image select/remove
- default export directory
- Export Beside Source
- log folder action

### Processing

- representative every interval mode
- representative every sort mode
- arbitrary angle
- U8
- U16 PNG
- Live Preview
- Full Resolution Preview
- explicit Render
- cancel
- stale export choices

### Presets/history

- Load/Save preset
- Recent Presets
- Undo/Redo
- preset portability fixture created on Linux/Android

## 5. Cross-platform deterministic hash gate

Create a permanent `testdata/v2-cross-platform/` or equivalent set of small fixtures and expected raw-render hashes.

Generate/verify on:

- Linux x86-64
- Windows x86-64
- Android ARM64
- Android x86_64 where practical

Include at least:

- deterministic U8 None/Lightness/cardinal
- deterministic U16 Threshold/Saturation/cardinal
- mask case
- File or File Edges interval case
- V2 RNG Random/Waves case
- nonzero randomness-skip case
- non-cardinal 45° direct-angle case
- another asymmetric arbitrary angle
- transparency

All V2 expected outputs must match across supported targets for the same engine semantics version.

If platform differences exist, fix the underlying semantics before release; do not simply record per-platform goldens unless the user explicitly accepts nondeterminism.

## 6. Benchmark and optimize only measured bottlenecks

Run the benchmark suite on the latest correct engine.

Required workload categories:

- 1920x1080 U8
- 6000x4000 U8
- 6000x4000 U16
- mask-heavy
- interval-image-heavy
- Lightness
- Hue
- Saturation
- Random
- Waves
- 0°
- 45°
- 90°

Measure:

- decode
- ICC conversion
- proxy resize
- path generation
- interval/sorting
- display conversion
- encode
- total
- peak memory

### Optimization rules

Optimize only where data shows meaningful cost.

Likely candidates:

- sort-key computation
- worker-local scratch reuse
- avoiding allocations in per-path processing
- path scheduling/granularity
- hue/saturation fixed-point calculation
- cache locality
- codec configuration
- runtime-dispatched SIMD where safe

Do not:

- enable `-ffast-math`
- use `-march=native` in portable release artifacts
- change visible algorithm semantics without a deliberate versioned decision
- add GPU work in MVP hardening
- add a large dependency solely to claim performance

After every optimization, rerun determinism/equivalence/sanitizer tests.

No hard render-time target is required to complete V2 unless the product owner later sets one.

## 7. Windows portable ZIP packaging

Initial Windows distribution is a portable ZIP, not an installer.

Create versioned artifact such as:

```text
ChromaSunder-2.0.x-Windows-x86_64.zip
```

Include everything needed from a clean extraction directory:

- executable
- Flutter runtime/data assets
- C++ engine native library
- required codec/color native libraries
- licenses/notices as required
- concise README if runtime prerequisites remain

Do not include:

- source build tree
- debug symbols unless deliberate separate artifact
- Python
- Pillow
- PyGObject
- V1 GTK resources
- developer absolute paths

### Clean-machine test

On a clean or representative non-development Windows environment:

1. extract ZIP to arbitrary user directory
2. launch without installation
3. perform Open -> Live Preview -> Render -> Export
4. test PNG16
5. verify logs/preferences use user-writable app locations
6. verify native DLL resolution does not depend on developer PATH

Generate SHA-256.

Proper Windows installer is post-MVP.

## 8. Revalidate Linux AppImage

Rebuild final Linux artifact from the release candidate commit.

Test the actual artifact on Fedora again.

Verify:

- C++ native dependencies packaged correctly
- no accidental Python/V1 runtime dependency
- no Flatpak assumptions
- PNG16/JPEG/ICC paths work from packaged app
- default export/log/preferences work outside source tree

Produce versioned filename and SHA-256.

## 9. Revalidate Android universal APK

Rebuild from the same release candidate source/engine semantics.

Verify:

- minSdk 33
- `arm64-v8a` + `x86_64` only
- direct install works
- merged manifest privacy audit passes
- no Play Store dependency
- signing process documented/secrets external
- versioned APK filename
- SHA-256

Run final ARM64 smoke test.

## 10. Preserve V1 history before deletion

Before removing V1 implementation:

- identify/tag final historical V1 commit/state
- ensure any uncommitted migration-origin files that mattered were preserved in history/docs if appropriate
- confirm Git history can retrieve V1 source
- preserve existing release tags

If creating a new historical tag would be public/persistent and naming is uncertain, ask the user rather than inventing a surprising release tag. An internal/documented baseline SHA is sufficient until approved.

V1 does not remain as a subfolder/legacy package after this milestone.

## 11. Migrate permanent tests before deleting Python reference

Review every important semantic test in the temporary `reference/python` package and V1 suite.

For each useful behavior, ensure one of these exists in permanent V2 tests:

- exact native unit test
- cross-platform golden/hash test
- property test
- codec fixture test
- Dart application-state test

Preserve useful small source/mask/interval/golden fixtures if licensing permits.

Do not delete the Python reference until this mapping is documented, for example in:

```text
docs/v2/V1_TEST_MIGRATION.md
```

with categories:

- migrated
- intentionally obsolete (reason)
- V2 replacement test path

## 12. Remove temporary Python reference

After the permanent-test gate passes, delete:

```text
reference/python/
```

Remove Python/Pillow dependencies that existed only for migration/reference testing.

Run repository search to prove release/build paths no longer invoke Python for product rendering.

Development scripts may use Python only if independently justified as build tooling, but the product/runtime must not require it. Prefer removing obsolete Python tooling if no longer needed.

## 13. Remove V1 application implementation

Delete obsolete V1-only runtime source, including as applicable:

```text
src/chromasunder/
```

once all V2 replacements/gates pass.

This includes:

- GTK/libadwaita UI
- Python core renderer
- spawned worker/process protocol
- GSettings integration
- V1 application startup
- V1 batch implementation if not reused (batch is post-MVP and must not leave a ghost V1 runtime)

Do not leave a functional `legacy/` application.

Git history is the legacy archive.

## 14. Remove obsolete V1 packaging/build infrastructure

After confirming V2 release artifacts are independent, remove obsolete items such as:

- Python `pyproject.toml` configuration that only builds V1
- Flatpak manifests/repository/bundles/build scripts if no longer relevant
- old generated Flatpak build directories/artifacts
- GSettings schemas used only by V1
- V1-specific redeploy scripts
- old cached build artifacts committed/present in tree

Be careful not to delete generic icons/metadata/assets that should be migrated to Flutter packaging.

Before deletion, migrate:

- application icon(s)
- desktop metadata wording worth preserving
- license/attribution
- changelog/history if appropriate

## 15. Root repository cleanup

Final high-level repo should look conceptually like:

```text
ChromaSunder/
├── app/
├── engine/
├── packages/
├── testdata/
├── benchmarks/
├── docs/
├── scripts/
├── .github/
├── LICENSE
├── ATTRIBUTION.md
├── THIRD_PARTY_NOTICES.md
├── README.md
├── CONTRIBUTING.md
└── AGENTS.md
```

Exact structure may include additional V2 files, but there must be no parallel V1 app.

## 16. Rewrite documentation for V2 only

### README

Must describe:

- what Chroma Sunder does
- current V2 screenshots/feature summary
- Linux/Windows/Android supported release status
- Android 13+ requirement
- PNG/JPEG and U8/U16 behavior
- direct directional pixel sorting
- Live Preview / Full Resolution Preview / Render distinction
- offline/privacy stance
- build/development links
- MIT license/attribution

Do not tell new users to install Python/GTK/Flatpak V1 tooling.

### Architecture docs

Consolidate current V2 docs so they accurately describe:

- Flutter app
- C ABI/package_ffi
- C++ engine
- path architecture
- color/bit-depth pipeline
- jobs/cancellation
- preview/full render
- platform adapters

### Contributing

Update commands for:

- CMake tests
- Flutter tests
- FFI regeneration
- Linux development
- Windows CI expectations
- Android development

### Changelog

Document V2 as a major rewrite and explicitly call out intended behavior differences:

- arbitrary angles now direct directional sort, not rotate/resample
- seed output not compatible with V1 RNG
- 16-bit native processing
- Flutter/C++ architecture

## 17. License and third-party notice audit

Project remains MIT.

Verify root `LICENSE` is correct.

Preserve/update `ATTRIBUTION.md`, including existing Pixelsort attribution.

Audit every direct/transitive native/runtime dependency used in distributed artifacts.

Update `THIRD_PARTY_NOTICES.md` with required notices/license text/references.

Check AppImage/ZIP/APK packaging includes notices in an appropriate accessible form.

Do not assume "MIT compatible" means notice can be omitted.

## 18. Privacy/network audit

Perform source/dependency/config searches for suspicious integrations/keywords such as:

```text
http://
https://
analytics
telemetry
crashlytics
sentry
firebase
segment
amplitude
remote config
login
oauth
cloud
upload
```

Not every URL string is prohibited (licenses/help metadata may contain URLs), but every runtime network-capable dependency/call must be reviewed.

Verify:

- no product network service initialized
- no telemetry SDK
- no account code
- no update checker
- Android merged manifest no unintended Internet permission
- Linux/Windows app works offline

Document audit result in `docs/v2/PRIVACY_ARCHITECTURE.md`.

## 19. Final complete test sweep

Run all relevant suites from a clean checkout/release candidate:

### Linux

- CMake native debug/release tests
- sanitizer jobs
- reference-independent V2 cross-platform hashes
- Flutter analyze/tests/widget/integration
- AppImage smoke

### Windows

- native tests
- Flutter tests
- release build
- portable ZIP clean-machine smoke

### Android

- native/hash tests
- Dart/widget tests
- x86_64 emulator integrations
- ARM64 real-device manual/integration gate
- final APK smoke

No Python reference renderer should be required for these final tests.

## 20. Merge/repository replacement

Only after all gates pass:

1. ensure V2 branch is current and reviewed
2. ensure final V1 state is recoverable in Git history/tags
3. ensure V1 implementation/reference has been removed from V2 tree
4. merge/replace `main` according to repository policy without destroying history
5. verify `main` builds/tests after merge

Do not force-push/rewrite main history just to make the repo look like V2 started from scratch.

The intended result is evolutionary Git history with a V2-only current tree.

## 21. Release versioning

Use normal `2.0.x` version numbers.

No alpha/beta/rc suffixes.

Synchronize version across:

- Flutter pub/app version
- native engine/application version metadata
- About screen
- artifact filenames
- preset application metadata where used
- release notes

Do not invent a release sequence beyond the repository/product owner's current decision. If an actual public release number is not specified, use the current V2 `2.0.x` development version already established in the branch rather than arbitrarily incrementing.

## 22. Final release artifacts

Expected direct-download artifacts:

### Linux

```text
ChromaSunder-2.0.x-Linux-x86_64.AppImage
```

### Windows

```text
ChromaSunder-2.0.x-Windows-x86_64.zip
```

### Android

```text
ChromaSunder-2.0.x-Android.apk
```

Produce SHA-256 checksum(s), ideally a companion `SHA256SUMS.txt`.

Do not add store distribution.

Do not add automatic updater.

## 23. Post-MVP features explicitly not to sneak into hardening

Do not implement during this milestone unless separately instructed:

- batch processing
- Recent Source Files
- zoom/pan
- split preview
- TIFF
- WebP
- weighted masks
- project/session files
- multiple documents/tabs
- multi-stage UI
- bent paths
- curved paths
- flow fields
- extra sorting algorithms
- GPU backend
- mapped/disk-backed out-of-core renderer
- light/alternate themes
- JPEG background picker
- filename templates
- Windows installer
- ARM desktop
- update checker/updater
- iOS
- macOS
- app stores

Hardening is not a license for scope creep.

## Hard completion gates

### Windows

- [ ] Real Windows 10/11 x86-64 environment tested.
- [ ] Native engine builds/tests with MSVC.
- [ ] Flutter Windows release build succeeds.
- [ ] Native window chrome/layout/HiDPI manually validated.
- [ ] Open/drag/drop/mask/interval/presets/render/cancel/export work.
- [ ] PNG16 works on Windows.
- [ ] portable ZIP runs from clean extraction without developer PATH/build tree.
- [ ] Windows ZIP SHA-256 generated.

### Cross-platform semantics

- [ ] Permanent V2 cross-platform hash fixture set exists.
- [ ] Linux x86-64 hashes pass.
- [ ] Windows x86-64 hashes pass.
- [ ] Android ARM64 hashes pass.
- [ ] Android x86_64 path passes where required.
- [ ] V2 RNG and arbitrary-angle cases are cross-platform deterministic.

### Cleanup/migration

- [ ] final V1 state recoverable through Git history/tag/reference SHA.
- [ ] every useful V1/reference behavior has a permanent V2 test or documented obsolete reason.
- [ ] temporary `reference/python` removed.
- [ ] Python V1 renderer removed.
- [ ] GTK/libadwaita V1 application removed.
- [ ] V1 worker/process/cache architecture removed.
- [ ] obsolete V1 Python packaging removed.
- [ ] obsolete Flatpak-specific infrastructure removed if no longer used.
- [ ] no maintained legacy app remains in-tree.

### Documentation/licenses/privacy

- [ ] README/CONTRIBUTING/architecture docs describe V2 only.
- [ ] `AGENTS.md` describes V2 workflow.
- [ ] MIT license preserved.
- [ ] existing attribution preserved.
- [ ] third-party notices audited/updated.
- [ ] privacy/network audit passes.
- [ ] Android final manifest has no unintended Internet permission.

### Final artifacts

- [ ] final Linux AppImage rebuilt and Fedora-tested.
- [ ] final Windows portable ZIP clean-tested.
- [ ] final Android universal APK ARM64-tested.
- [ ] all three artifacts built from the intended release candidate source.
- [ ] SHA-256 checksums produced.
- [ ] version metadata consistently uses current `2.0.x`.

### Repository replacement

- [ ] `main` current tree is Flutter/C++ V2 only.
- [ ] full test suite passes after final merge/replacement.
- [ ] no destructive history rewrite was required.

## End-of-milestone handoff

Provide a final engineering release report containing:

- release commit SHA
- `2.0.x` version
- Linux/Windows/Android test environments
- full automated test counts/results
- cross-platform hash matrix
- benchmark summary (measured, not marketing claims)
- AppImage/ZIP/APK filenames, sizes, SHA-256
- final dependency/license audit result
- final privacy audit result
- list of intentionally deferred post-MVP features
- confirmation that V1 code remains accessible only through Git history/tags and is no longer in the current tree
