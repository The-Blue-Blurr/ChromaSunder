# V2 Development Environment

## Validated Fedora Host

- Fedora Linux 44 Workstation, kernel `7.1.10-200.fc44.x86_64`
- Flutter 3.44.9 stable, framework revision `6b182d2c75`
- Dart 3.12.2, DevTools 2.57.0
- Clang 22.1.8
- GCC/G++ 16.2.1
- CMake 4.3.0
- Ninja 1.13.2
- pkg-config 2.5.1
- Android SDK 36.0.0, platform android-37, build-tools 36.0.0
- Android NDK 28.2.13676358 selected by Flutter
- Android Studio JDK 25.0.2
- Python 3.13.5 and Pillow 11.1.0 for the temporary V1 reference

`flutter doctor -v` reported no issues. The attached physical Android device was unauthorized, so
the APK was built and inspected locally but not launched on that device during this milestone.

## Fedora Native Packages

Standalone Milestone 2 codec builds additionally require libpng, libjpeg-turbo, and Little CMS 2
development headers. The validated versions are libpng 1.6.58, libjpeg-turbo 3.1.3, and Little CMS
2.16. On Fedora install the corresponding `libpng-devel`, `libjpeg-turbo-devel`, and `lcms2-devel`
packages. The validated host contained the runtime libraries and libpng/LCMS headers; the JPEG
header used for local verification was extracted from Fedora's matching development RPM without a
system installation.

Core tools include:

```text
clang-22.1.8-4.fc44.x86_64
cmake-4.3.0-1.fc44.x86_64
ninja-build-1.13.2-2.fc44.x86_64
pkgconf-pkg-config-2.5.1-1.fc44.x86_64
gtk3-devel-3.24.52-2.fc44.x86_64
gcc-c++-16.2.1-2.fc44.x86_64
```

## Build Commands

```bash
cmake -S engine -B build/engine -DCMAKE_BUILD_TYPE=Debug
cmake --build build/engine
ctest --test-dir build/engine --output-on-failure

cd packages/chromasunder_native
dart pub get
dart run ffigen --config ffigen.yaml
dart analyze
dart test

cd app
flutter pub get
flutter analyze
flutter test
flutter run -d linux --release
flutter build linux --release
flutter build apk --release
```

Flutter asks native-assets hooks to compile its default Android target set before Gradle packaging.
The application-level `abiFilters` and JNI packaging exclusions form the distribution boundary
and restrict the resulting universal APK to the two approved 64-bit ABIs. This is verified from the
archive after every release build rather than inferred from Gradle configuration.

The GCC sanitizer runtime is absent on this host, so Milestone 2 sanitizer validation uses Clang
22.1.8. ASan+UBSan passes with codecs enabled. TSan passes in a separate codec-disabled build and
covers the worker pool, parallel renderer, determinism tests, and 400-case parity matrix. CI repeats
both sanitizer configurations on Ubuntu.

## Native-Assets Adaptation

The generated `native_toolchain_c` CBuilder initially misidentified Fedora's ccache compiler
symlink and invoked `/usr/bin/ccache` directly with compiler flags. The handwritten build hook now
invokes the authoritative CMake project instead. This keeps one engine definition and allows CMake
to handle Fedora ccache, MSVC, and Android NDK toolchains normally.
