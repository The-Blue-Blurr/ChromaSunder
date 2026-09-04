# Chroma Sunder V2 — Dependency and License Policy

## Goal

Use mature libraries where they reduce risk, but keep the dependency graph comprehensible, portable, offline-capable, and legally compatible with an MIT-licensed direct-download application.

## Mandatory review before adding a dependency

For every new runtime/native dependency, record:

- name
- exact version or version policy
- upstream URL
- purpose
- license
- whether it is linked statically or dynamically on each target
- whether notices/source-offer obligations exist
- supported target architectures/platforms
- package size impact if material
- why a smaller existing/local option is not preferable

Update `THIRD_PARTY_NOTICES.md` as required.

## Preferred native candidates

These are starting candidates, not permission to add unused libraries.

### libpng

Purpose:

- PNG decode/encode
- 8-bit and 16-bit PNG paths

Use it directly or through a very thin wrapper. Do not reduce 16-bit PNG input to 8-bit.

### libjpeg-turbo

Purpose:

- JPEG decode/encode
- fast SIMD paths on x86-64 and ARM64

MVP JPEG output is 8-bit. Preserve ICC payload/convert correctly through the color pipeline as designed.

### Little CMS 2 (lcms2)

Purpose:

- ICC color-profile transforms
- 8-bit and 16-bit conversion to the defined sRGB working space

Do not write a homegrown ICC engine.

### `stb_image_resize2.h` or equivalent focused resizer

Purpose:

- low-resolution proxy generation
- 8-bit and 16-bit resizing

Keep resizing outside the sorting semantics. For binary mask/interval proxies, use nearest/explicit binary-safe sampling rather than a smoothing filter that invents fractional mask meaning.

### nlohmann/json

Purpose:

- small JSON serialization needs in native tooling/settings if native JSON is actually necessary

Do not duplicate application persistence logic in C++ and Dart without need. If presets/preferences can remain wholly Dart-side except for typed settings passed through FFI, avoid unnecessary native JSON parsing.

### spdlog

Purpose:

- native rotating local diagnostics

Configure for local files only. No network sinks.

### C++ test framework

Choose one focused framework (for example Catch2 or GoogleTest) and use it consistently. Do not add multiple competing native test frameworks.

## OpenCV policy

Do **not** add OpenCV by default.

If a future task appears to benefit from it, first document:

- exact APIs required
- binary/package-size impact
- dependency/transitive impact
- why existing codec/resizer/color libraries plus local code are inadequate

Ask the user before making OpenCV foundational if the benefit is uncertain.

## Flutter package policy

Prefer Flutter/Dart standard library and first-party/platform APIs where they are adequate.

For third-party packages:

- prefer actively maintained packages with clear desktop + Android support
- avoid packages that silently add analytics/network SDKs
- avoid a stack of tiny packages for trivial helpers
- pin/lock dependencies through normal Flutter tooling
- audit transitive native dependencies

For Android platform capabilities, prefer a narrow typed platform adapter (Kotlin + Pigeon or similarly typed bridge) when that avoids accumulating many overlapping plugins.

## FFI/build strategy

Preferred:

- standalone CMake C++ engine
- Flutter `package_ffi` native-assets integration
- generated Dart bindings via `ffigen`
- handwritten Dart service wrapper above generated bindings

The standalone engine build remains authoritative. Do not create separate platform forks of the renderer.

If package_ffi/native-assets cannot package a required CMake dependency layout cleanly on a platform, document the blocker and ask before switching to a larger plugin architecture.

## Licensing

Project remains MIT licensed.

Preserve:

- root `LICENSE`
- existing `ATTRIBUTION.md`
- Pixelsort attribution/notice
- required dependency notices

Before final release, verify the distributed AppImage/ZIP/APK contains or references all required third-party notices.

## Security/privacy constraints

Reject dependencies whose normal operation requires:

- telemetry
- cloud API access
- remote feature flags
- online accounts
- analytics SDK initialization

An otherwise-useful dependency with optional networking must have that functionality disabled/unlinked for MVP unless explicitly approved.

## Release portability constraints

Do not use release compiler options that bind the binary to the developer's CPU, such as broad `-march=native` assumptions.

Do not use `-ffast-math` in deterministic rendering code.

SIMD optimizations are welcome when:

- runtime-dispatched or target-appropriate
- tested on supported architectures
- behavior remains deterministic within the defined engine semantics
- benchmark data shows benefit
