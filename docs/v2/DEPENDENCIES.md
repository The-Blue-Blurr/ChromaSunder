# V2 Dependency Audit

Flutter versions are locked by `app/pubspec.lock` and `packages/chromasunder_native/pubspec.lock`.
Windows native versions are locked by `engine/vcpkg.json` at vcpkg baseline
`04a9d8e5212d01ee1dd9478eadd9caade4f8b0d4`. Linux uses compatible distribution packages.

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
| libpng | 1.6.58 Windows/Fedora; compatible 1.6.x Linux | Lossless PNG8/PNG16 I/O | libpng-2.0 | <https://github.com/pnggroup/libpng> | Dynamic system library on Linux; static private vcpkg linkage on Windows | Linux x86-64, Windows x86-64; upstream supports Android 64-bit |
| zlib | vcpkg-baseline/distribution version | libpng compression dependency | Zlib | <https://zlib.net/> | Same linkage policy as libpng | Linux x86-64, Windows x86-64; upstream supports Android 64-bit |
| libjpeg-turbo | 3.2.0 Windows; 3.1.3 Fedora; compatible distro version | JPEG decode/encode | BSD-3-Clause/IJG/zlib notices | <https://libjpeg-turbo.org/> | Dynamic system library on Linux; static private vcpkg linkage on Windows | Linux/Windows x86-64; upstream supports Android ARM64/x86-64 |
| Little CMS 2 | 2.19.1 Windows; 2.16 Fedora; compatible 2.x Linux | ICC conversion to sRGB at U8/U16 | MIT | <https://github.com/mm2/Little-CMS> | Dynamic system library on Linux; static private vcpkg linkage on Windows; GPL plugins disabled | Linux/Windows x86-64; upstream supports Android 64-bit |

These focused libraries replace unsafe home-grown implementations: libpng is needed for exact PNG16
and metadata handling, libjpeg-turbo for robust JPEG parsing/encoding, and Little CMS because ICC
transforms must not be implemented locally. Their Linux installed footprint is distribution-owned;
the Windows static release contribution is expected to be a few MiB and will be measured during ZIP
packaging. None performs network activity or telemetry.

`chromasunder_engine` remains the only Flutter-bundled shared library. Milestone 2 standalone builds
enable codecs by default. The current Milestone 1 native-assets smoke build disables codecs because
cross-compiled Android dependency packaging belongs to later integration work; this does not create
a second engine definition. The full dependency graph is exercised by Linux and Windows native CI.
