# Native Engine Architecture

The Milestone 2 engine is a standalone C++20 CMake project. Flutter is not required to configure,
build, test, or benchmark it. The existing shared library still exports only the Milestone 1 smoke
C ABI; the full C ABI remains Milestone 3 work.

## Modules

- `image/` owns typed `RGBA8` and `RGBA16` buffers, views, formats, and the heap-storage seam.
- `processing/` owns settings, keys, intervals, masks, directional paths, stages, and backends.
- `codec/` owns PNG/JPEG decoding, encoding, EXIF orientation, auxiliary loading, and atomic I/O.
- `color/` owns Little CMS conversion into the sRGB working space.
- `jobs/` owns cancellation, real work progress, and the persistent worker pool.
- `memory/` owns checked render estimates and budget rejection.

`chromasunder_core` is a private static implementation target. Tests and benchmarks link to it
directly without exporting an unstable C++ ABI. `chromasunder_engine` is the shared native asset and
links the same core, so there is only one engine definition.

## Render Flow

`CpuRenderBackend` dispatches an `AnyImage` once to `uint8_t` or `uint16_t`. It checks the memory
budget before candidate allocation, copies the immutable source into the candidate, generates path
metadata, and gives independent paths to the fixed worker pool. `PixelSortStage<T>` then operates on
typed pixels without a per-pixel variant, virtual call, or lock.

`FullRenderStore` promotes a candidate only after complete success. Cancellation, validation,
allocation, and processing errors leave the prior completed render untouched.

`ProcessingStage<T>` is the orchestration-level pipeline seam. `RenderBackend` separates callers
from CPU internals. Neither seam introduces virtual dispatch in pixel loops.

## Path Storage

`StraightDirectionalPathProvider` stores one compact descriptor per path: major axis, fixed-point
slope, stable path ID, and primary index range. Coordinates are computed by indexed traversal. No
full-image coordinate map or rotated image exists. The abstract `PathProvider` can later supply
curves or flow-field paths without changing interval and sorting code.
