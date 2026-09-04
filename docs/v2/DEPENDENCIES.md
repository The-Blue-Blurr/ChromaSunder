# V2 Dependency Audit

Versions are locked by `app/pubspec.lock` and `packages/chromasunder_native/pubspec.lock`. No codec,
color-management, logging, telemetry, analytics, or network dependency has been added.

| Package/library | Version | Purpose | License | Source | Packaging | Platforms |
|---|---:|---|---|---|---|---|
| Flutter SDK | 3.44.9 | Application shell and platform runners | BSD-3-Clause | <https://github.com/flutter/flutter> | Flutter runtime bundled per target | Linux, Windows, Android |
| Dart SDK | 3.12.2 | Application language and FFI runtime | BSD-3-Clause | <https://github.com/dart-lang/sdk> | Supplied through Flutter toolchain/runtime | Linux, Windows, Android |
| `code_assets` | 1.0.0 | Declare bundled native code assets | BSD-3-Clause | <https://pub.dev/packages/code_assets> | Build-time package; generated asset metadata | Linux, Windows, Android |
| `hooks` | 1.0.3 | Execute the native CMake build hook | BSD-3-Clause | <https://pub.dev/packages/hooks> | Build-time only | Linux, Windows, Android |
| `ffi` | 2.2.0 | FFI types used while generating/testing bindings | BSD-3-Clause | <https://pub.dev/packages/ffi> | Development dependency | Development hosts |
| `ffigen` | 20.1.1 | Generate Dart declarations from `c_api.h` | BSD-3-Clause | <https://pub.dev/packages/ffigen> | Development/CI dependency | Development hosts |
| `flutter_lints` | 6.0.0 | Dart and Flutter static-analysis rules | BSD-3-Clause | <https://pub.dev/packages/flutter_lints> | Development only | Development hosts |
| `test` | 1.32.0 | Native package smoke tests | BSD-3-Clause | <https://pub.dev/packages/test> | Development only | Development hosts |
| Pillow | 11.1.0 baseline (`>=10.0`) | Temporary V1 reference image loading/rendering | HPND | <https://python-pillow.github.io/> | Migration tooling only; not V2 runtime | Development hosts |
| pytest | 8.x environment (`>=8`) | V1 and reference validation | MIT | <https://pytest.org/> | Development only | Development hosts |
| Ruff | 0.6+ policy | Python lint/format checks | MIT | <https://github.com/astral-sh/ruff> | Development/CI only | Development hosts |

The C++ smoke engine uses only the C++ standard library. It is dynamically bundled as
`chromasunder_engine` on each application target. Android links the C++ runtime statically into
that library for the current smoke build. There are no third-party native runtime libraries.

Before adding PNG, JPEG, ICC, resize, or logging libraries in later milestones, record exact
versions, licenses, linkage, supported architectures, size impact, and notice obligations here and
update `THIRD_PARTY_NOTICES.md` where required.
