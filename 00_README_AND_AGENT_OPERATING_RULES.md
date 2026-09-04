# Chroma Sunder V2 — Coding Agent Operating Guide

## Purpose

This instruction pack is the authoritative implementation plan for replacing the current Python/GTK Chroma Sunder application with Chroma Sunder V2: a Flutter application backed by a portable C++20 image-processing engine.

Execute the milestone files in numerical order. Do not skip a completion gate because a later milestone appears easier or more interesting.

## Required reading before making changes

Before implementing a milestone, read:

1. This file.
2. `90_ARCHITECTURE_AND_PRODUCT_DECISIONS.md`.
3. `91_TEST_GATE_MATRIX.md`.
4. `92_DEPENDENCY_AND_LICENSE_POLICY.md`.
5. `93_CURRENT_V1_REPO_MAP.md`.
6. The milestone file being executed.
7. Any source/test files explicitly named by that milestone.

If an existing repository instruction conflicts with this V2 pack, stop and determine whether it is V1-only guidance. The current V1 `AGENTS.md` contains scope restrictions that conflict with approved V2 requirements such as Live Preview and desktop drag-and-drop. Milestone 1 explicitly replaces that obsolete V1 guidance on the V2 branch.

## Hard product invariants

Do not change these without explicit user approval:

- Flutter owns the UI/application shell; C++ owns full-resolution image processing.
- Full-resolution working/render buffers must not be moved through Dart merely to display them.
- Processing is local-only. No telemetry, analytics, cloud rendering, accounts, image upload, crash-reporting service, or other network functionality.
- The only possible future network feature is an explicit update check; it is not part of the MVP.
- The source image is immutable for the lifetime of the open document.
- Native processing preserves source precision: 8-bit sources process as 8-bit; 16-bit sources process as 16-bit.
- PNG and JPEG are MVP codecs. The codec layer must be extensible to TIFF/WebP later.
- The internal working color space is sRGB with ICC-aware import conversion.
- EXIF orientation is applied at import; general EXIF/GPS preservation is not an MVP requirement.
- RGBA moves as one pixel. Alpha moves with RGB.
- Masks and interval images must exactly match the canonical source dimensions.
- MVP masks are binary; architecture must permit weighted masks later.
- Arbitrary-angle sorting uses direct directional paths, not rotate/sort/rotate-back.
- The MVP exposes one processing stage, but the engine must be pipeline-ready.
- CPU rendering is the MVP implementation; keep a small backend seam for future GPU work.
- Linux x86-64 is the primary local desktop target.
- Windows x86-64 stays build/test-clean through CI; real Windows validation occurs later.
- Android follows the Linux MVP immediately and must have full core-MVP feature parity.
- Android minimum is API 33 / Android 13+, 64-bit only (`arm64-v8a`, `x86_64`).
- iOS and macOS are eventual targets only.
- Linux distribution: AppImage.
- Windows initial distribution: portable ZIP; installer later.
- Android distribution: directly downloaded universal APK; no Play Store work.
- Versions use ordinary `2.0.x` numbers; do not introduce alpha/beta/rc suffixes.
- MIT licensing and existing attribution remain intact.

## Git and repository safety

- Never discard uncommitted user changes.
- Never use destructive commands such as `git reset --hard`, `git clean -fd`, force-push, or rewriting published history unless explicitly instructed.
- Before branch or migration work, record `git status`, current branch, and current HEAD SHA.
- Keep changes scoped to the current milestone.
- Prefer focused commits that correspond to coherent tasks/gates.
- Do not merge V2 to `main` until Milestone 6 says to do so.
- The current Python/GTK implementation is temporary migration reference material, not a permanent legacy app inside V2.

## Build-system rule

The standalone C++ engine must have a normal CMake build and test path independent of Flutter.

Flutter native integration should use the current `package_ffi`/native-assets approach where practical. The native package may invoke/reuse the CMake build, but there must not be two divergent definitions of the engine or dependency graph.

If `package_ffi` cannot cleanly package the required CMake/dependency output on a target platform, document the exact blocker and ask before changing the architecture to a larger plugin/native-wrapper approach.

## Dependency rule

Mature libraries are allowed when they materially reduce risk or implementation time. Do not add a large dependency merely for a tiny utility.

Before adding a substantial library:

1. State what problem it solves.
2. State why existing dependencies or a small local implementation are insufficient.
3. Check license compatibility with MIT redistribution.
4. Record it in `THIRD_PARTY_NOTICES.md` or the V2 dependency audit.
5. If the tradeoff is uncertain, ask the user.

Do not add OpenCV by default. It may be reconsidered later if measured needs justify it.

## C++ implementation standards

- C++20.
- RAII ownership; no raw owning pointers.
- Prefer value types, `std::span`, `std::vector`, `std::unique_ptr`, and explicit handles.
- No exceptions may cross the C ABI.
- Do not use undefined-behavior-dependent tricks.
- Do not use `-ffast-math` or platform-specific `-march=native` in portable release builds.
- Treat deterministic output as a feature. Avoid implementation-defined numeric behavior in sorting/RNG semantics.
- Keep hot loops allocation-light; reuse scratch buffers where practical.
- Keep engine headers independent of Flutter/Dart/platform UI headers.

## Dart / Flutter implementation standards

- Keep generated FFI bindings behind a handwritten Dart abstraction.
- UI widgets must not directly call generated C functions.
- Model render jobs, documents, preferences, and stale-state semantics explicitly.
- Keep platform-specific Android/Linux/Windows code behind narrow adapters.
- Theme values must come from design/theme tokens rather than scattered literals.
- No custom frameless desktop title bar for the MVP; the desktop environment/window manager owns close/maximize/minimize.

## Correctness before optimization

Do not optimize the new engine before the relevant behavior is tested.

Required sequence for a new processing feature:

1. Implement a simple correct version.
2. Add/port tests.
3. Establish reference/invariant behavior.
4. Benchmark.
5. Optimize measured bottlenecks.
6. Re-run correctness and determinism tests.

Do not change algorithm semantics merely to gain speed unless the roadmap explicitly permits it.

## Compatibility policy

Preserve V1 behavior for the MVP wherever the architecture has not deliberately changed it.

Expected V1-compatible areas include:

- Threshold and interval semantics.
- Sorting key semantics.
- Stable tie behavior.
- Mask semantics.
- Interval-image semantics.
- Alpha movement.
- Cardinal direction behavior where the direct path model can represent it exactly.

Intentional differences:

- A V2 seed does not have to reproduce V1/Python RNG output.
- Non-cardinal angles use a new direct directional path algorithm and do not need byte-for-byte V1 parity.

All other behavior changes must be explicit and tested.

## Test discipline

At each meaningful task boundary:

- Run the smallest relevant test subset while iterating.
- Before declaring a gate complete, run the complete test set required by that gate.
- Do not delete a failing test to make a gate pass unless the test describes an explicitly superseded V1 behavior; if so, replace it with the correct V2 test and document why.
- Record benchmark changes rather than relying on subjective impressions.

Use `91_TEST_GATE_MATRIX.md` as the minimum required coverage, not an exhaustive maximum.

## Progress and cancellation semantics

Render progress must report real work, not elapsed-time simulation.

The logical stages are approximately:

- Preparing image
- Generating paths
- Sorting
- Building preview
- Encoding/exporting

Cancelled full-resolution work is transactional: discard the candidate and keep the last successfully completed full-resolution render valid.

## Required end-of-milestone handoff

At the end of every milestone, provide a concise handoff containing:

### Implemented
- What changed.

### Tests run
- Exact commands.
- Pass/fail counts.

### Artifacts/builds produced
- Paths/names.

### Known limitations
- Only real unresolved limitations; do not hide them.

### Gate checklist
- Each gate marked PASS/FAIL with evidence.

### Next milestone readiness
- State whether the next milestone may begin.

If any hard completion gate is FAIL, do not describe the milestone as complete.
