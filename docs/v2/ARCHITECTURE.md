# V2 Architecture

## Milestone 1 Boundary

```text
Flutter widgets
    -> handwritten NativeSmokeService
    -> generated ffigen declarations
    -> stable exported C ABI
    -> portable C++20 engine
```

Flutter owns the application shell. The C++ engine will own full-resolution image processing and
buffers; future Dart APIs may retrieve bounded display previews and metadata but will not move
full-resolution working buffers through Dart for display.

## Native Build

`engine/CMakeLists.txt` is the authoritative standalone definition and provides an installable
shared library plus CTest target. The native-assets hook invokes this same CMake project for the
target selected by Flutter and registers its shared-library output as a bundled code asset.

The package contains generated declarations only, not a second native implementation. The
handwritten `NativeSmokeService` prevents widgets and application state from importing generated
bindings directly.

The current C ABI is intentionally limited to version and addition smoke functions. It is not the
final document/job API. C ABI exceptions are impossible in the current implementation, and future
entry points must catch all C++ exceptions before returning typed errors.

## Target Builds

- Linux and Windows use the platform CMake generator/toolchain.
- Android uses Flutter's selected NDK, API level, and architecture in the CMake toolchain file.
- Android packaging is restricted to `arm64-v8a` and `x86_64`.
- No macOS or iOS application was scaffolded.

## Migration Boundary

The temporary `reference/python` package is an isolated historical oracle. It deliberately retains
V1's RGBA8 and rotate/sort/rotate-back behavior and is not part of the V2 runtime architecture.
No pixel-sorting behavior exists in the C++ engine during Milestone 1.
