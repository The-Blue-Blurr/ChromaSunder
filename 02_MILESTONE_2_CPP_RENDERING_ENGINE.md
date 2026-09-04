# Milestone 2 — Complete Native C++ Rendering Engine

## Objective

Build and validate the standalone C++20 engine that replaces the Python/Pillow render hot path. By the end of this milestone the engine must:

- represent and process RGBA8 and RGBA16 natively
- implement all existing sorting/interval/mask semantics required for MVP
- implement deterministic V2 RNG behavior
- replace rotation-based angle rendering with direct directional pixel paths
- import/export PNG and JPEG with color management and EXIF orientation
- process independent paths in parallel deterministically
- support typed jobs, cancellation, progress primitives, and transactional full renders at the engine layer
- estimate memory before large operations
- remain completely usable/testable without Flutter

Do not build the polished C ABI or Flutter state layer in this milestone; that is Milestone 3. It is acceptable to expose a temporary C++ testing API internally.

## 1. Establish engine module boundaries

Refine `engine/` into small explicit modules. A recommended structure is:

```text
engine/
├── include/chromasunder/
│   ├── image/
│   │   ├── pixel_format.hpp
│   │   ├── image_buffer.hpp
│   │   └── image_view.hpp
│   ├── processing/
│   │   ├── settings.hpp
│   │   ├── sorting.hpp
│   │   ├── intervals.hpp
│   │   ├── mask.hpp
│   │   ├── path.hpp
│   │   ├── pixel_sort_stage.hpp
│   │   └── render_backend.hpp
│   ├── codec/
│   │   ├── image_codec.hpp
│   │   └── image_io.hpp
│   ├── color/
│   │   └── color_management.hpp
│   ├── jobs/
│   │   ├── cancellation.hpp
│   │   ├── progress.hpp
│   │   └── thread_pool.hpp
│   ├── memory/
│   │   └── render_budget.hpp
│   └── error.hpp
├── src/
├── tests/
└── benchmarks/
```

The exact file names may differ, but preserve these conceptual boundaries.

## 2. Implement native image types

### Pixel format

Represent at minimum:

```text
RGBA8
RGBA16
```

Do not make the hot processing loop interpret a runtime union on every pixel. Prefer compile-time channel specialization once a job is dispatched.

Recommended pattern:

```cpp
template <typename Channel>
struct RgbaPixel;

template <typename Channel>
class ImageBuffer;
```

Where supported channel types are:

```cpp
std::uint8_t
std::uint16_t
```

Use wider intermediate integer types for sums and ratios so U16 operations cannot overflow.

### Image buffer

Requirements:

- contiguous row-major storage for MVP
- explicit width/height/stride
- checked size calculations before allocation
- overflow-safe `width * height * bytes_per_pixel`
- read-only `ImageView` support
- mutable output view support
- no raw owning pointers
- no implicit U16 -> U8 conversion

### Future storage seam

Do not implement tiling or disk backing now, but isolate backing storage enough that heap storage can later be replaced.

A simple design is sufficient:

```text
ImageBuffer<T>
   owns
BufferStorage
   current implementation: HeapStorage
```

Do not add virtual dispatch inside per-pixel access. The hot path must still get contiguous pointers/spans.

## 3. Port settings and validation

Create a C++ `PixelSortSettings` model matching current semantic fields:

- interval mode
- sorting mode
- lower threshold
- upper threshold
- characteristic length
- angle degrees
- randomness percentage
- seed

Validation must cover the rules documented in `93_CURRENT_V1_REPO_MAP.md`.

Recommended types:

- normalized thresholds: `double` at API/state boundary
- randomness: `double` or fixed normalized representation, explicit valid `[0,100]`
- characteristic length: unsigned integer with validated >=1
- seed: unsigned 64-bit for V2
- angle: finite double, normalized explicitly for path generation

Return typed validation errors rather than assertions for user-controlled inputs.

## 4. Define deterministic color/sorting semantics

The C++ engine must not depend on unspecified floating-point comparator behavior across platforms.

### Lightness sort key

Preserve V1 ordering:

```text
max(R,G,B) + min(R,G,B)
```

Use an intermediate wide enough for U16 (`uint32_t` or larger).

### Intensity sort key

Preserve:

```text
R + G + B
```

Use a wide enough integer.

### Minimum sort key

Preserve:

```text
min(R,G,B)
```

### Hue and saturation

V1 uses Python `colorsys.rgb_to_hls` ordering. Reproduce its HLS ordering semantics without relying on low-precision float differences to break comparisons.

Preferred approach:

- implement HLS key calculation directly in C++
- represent hue/saturation ordering as deterministic fixed-point integers, e.g. Q40 or another documented precision that gives stable ordering for all U8/U16 channel values
- define exact tie behavior
- add exhaustive U8 color tests where practical and broad U16 property tests

Hue algorithm must preserve the conventional HLS sector behavior:

- achromatic pixels hue = 0
- red/green/blue sector arithmetic equivalent to Python colorsys ordering
- hue normalized to `[0,1)` before conversion to fixed point

Saturation must use HLS saturation, not HSV saturation.

Document the chosen fixed-point representation in `docs/v2/ENGINE_SEMANTICS.md` so it becomes part of the V2 deterministic contract.

### Interval lightness

Threshold/Edges logic should use HLS lightness:

```text
(max + min) / (2 * channel_max)
```

Avoid unnecessary floating point by comparing rational/integer forms when possible. This makes inclusive threshold behavior easier to make deterministic.

### Precompute keys

For a sortable position set, compute each sort key once and stable-sort entries by the key.

Do not write a comparator that recalculates HLS repeatedly.

### Stable ties

Use `std::stable_sort` or an equivalent explicitly stable strategy.

Add tests where visually different pixels have identical keys and verify incoming order remains unchanged.

## 5. Port interval semantics exactly where required

General rules:

- intervals are half-open `[start,end)` within an ordered path
- do not emit intervals with length <2

Implement all seven modes.

### None

Whole path if length >=2.

### Threshold

For each path position, determine whether normalized HLS lightness is inclusively:

```text
lower <= L <= upper
```

Emit connected true runs of length >=2.

Test exact inclusive boundaries.

### Edges

Use adjacent HLS-lightness difference.

A boundary occurs when:

```text
abs(L[i] - L[i-1]) >= lower_threshold
```

Port V1 interval-boundary behavior exactly, including first/last boundaries and minimum-length handling.

### Random

Do not match Python's random stream.

Preserve the conceptual V1 interval-size rule but use the V2 RNG specified later in this file. For each generated size, retain the V1-compatible characteristic-length semantics and drop sub-2 intervals.

### Waves

Preserve V1 conceptual behavior:

```text
characteristic_length + bounded random variation
```

The existing variation is `randint(0,10)`; keep that semantic for MVP unless a test proves another current branch behavior.

### File

Treat the binary interval-image samples along the current path as on/off. Emit connected true runs of length >=2.

### File Edges

Port current transition/boundary behavior, including the current leading `previous=false/0` concept and boundary deduplication. Do not substitute generic edge detection.

## 6. Port exact mask semantics

This is easy to accidentally change.

For every interval:

1. Determine the interval **without** using the mask to split it.
2. Collect only positions inside that interval whose mask bit is enabled.
3. If fewer than 2 enabled positions remain, do nothing.
4. Stable-sort the pixels occupying those enabled positions.
5. Write sorted pixels back only to those enabled positions in their existing path order.
6. Disabled positions remain untouched.

Therefore, enabled pixels may move across disabled gaps within one interval.

Mask gaps must **not** become interval boundaries.

Alpha remains attached to its RGB pixel.

Add targeted tests that would fail if the implementation mistakenly splits intervals at mask gaps.

## 7. Define the V2 RNG contract

V2 does not need Python RNG compatibility, but must be deterministic across supported platforms and worker counts.

### Recommended generator

Use a small, fully specified generator whose exact arithmetic can be documented and reproduced, such as SplitMix64 for sequence generation/seed derivation. Do not use implementation-defined `std::uniform_*_distribution` results as part of the persistent V2 output contract because distribution mappings are not guaranteed identical across standard-library implementations.

Document exact functions for:

- next 64-bit value
- uniform `[0,1)` conversion
- bounded integer generation
- probability/percentage test

Suggested deterministic uniform double conversion:

- take a defined 53-bit portion of the generated integer
- multiply by exactly `1 / 2^53`

For bounded integers, use rejection sampling rather than modulo bias if the range matters to semantics.

### Per-path independent seed

No shared global RNG state may be consumed in scheduler order.

Derive a path-local seed from at minimum:

```text
global_seed
path_stable_id
rng_semantics_version
```

Use an explicitly documented mixing function.

Within a path, preserve deterministic consumption order. If both interval generation and interval-skipping randomness consume randomness, define and test the sequence in which they do so.

### Stable path ID

Path ID must be derived from geometry/order, not worker index or task-submission order.

### Required invariant

Rendering the same source/settings/seed with 1, 2, or N workers must produce identical bytes.

## 8. Build the path-processing abstraction

Separate path generation from interval detection and sorting.

Recommended interface concept:

```cpp
class PathProvider {
public:
    virtual PathDescriptor path(std::size_t index) const = 0;
    virtual std::size_t path_count() const = 0;
};
```

Do not require every future path to allocate a vector of every coordinate. A `PathDescriptor` can expose lazy/indexed traversal.

For MVP implement:

```text
StraightDirectionalPathProvider
```

The pixel-sort stage should receive ordered path positions and remain ignorant of whether those paths are straight, bent, curved, or flow-field-derived.

## 9. Replace rotate/sort/rotate with direct directional paths

### User-facing angle convention

Preserve current UI convention:

- 0° = left -> right
- 90° = bottom -> top
- 180° = right -> left
- 270° = top -> bottom

Image coordinates conventionally have +x right and +y down, therefore the mathematical direction vector can be defined as:

```text
dx = cos(theta)
dy = -sin(theta)
```

### Cardinal special cases

Implement explicit exact paths for 0/90/180/270. These should be simple row/column traversal and should permit V1 parity tests.

### Non-cardinal discrete path strategy

Use a deterministic grid partition, not geometric resampling.

One recommended strategy:

#### X-major directions

When `abs(dx) >= abs(dy)`:

- traversal variable advances along x in the direction of `dx`
- define a fixed-point secondary offset based on slope `dy / abs(dx)`
- for each primary step `u`, compute one deterministic rounded integer `offset(u)`
- assign each pixel to a path using:

```text
path_id = y - offset(u)
```

where actual x is mapped from `u` according to direction.

#### Y-major directions

When `abs(dy) > abs(dx)`:

- traversal variable advances along y in the direction of `dy`
- use fixed-point slope `dx / abs(dy)`
- define:

```text
path_id = x - offset(u)
```

with actual y mapped according to direction.

### Deterministic fixed point

Do not rely on repeated floating rounding in the per-pixel path loop if it can cause cross-platform boundary drift.

Convert slope once to a documented fixed-point representation (for example Q24/Q32), and use one explicitly defined round-to-nearest rule.

Angles themselves may enter via `sin/cos`, but path partitioning should quantize them once into the fixed-point slope. Normalize near-cardinal values to the exact cardinal implementation with a documented epsilon/snap rule if necessary.

### Coverage invariants

The algorithm is only acceptable if property tests prove for every tested image/angle:

- every pixel belongs to exactly one path
- no duplicate coordinates
- no omissions
- all coordinates are in bounds
- traversal direction matches the requested angle convention

### Memory

Do not create a full-image coordinate map.

Prefer lazy path iteration or compact path ranges. Because offset is monotonic for a straight line, derive valid primary-index ranges for each path rather than materializing every coordinate where practical.

The total auxiliary path metadata should remain far smaller than the image buffer.

## 10. U8/U16 semantic implementation

Dispatch once per job:

```text
RGBA8 -> render<uint8_t>()
RGBA16 -> render<uint16_t>()
```

Keep one templated/common algorithm rather than two independently drifting renderers.

### Normalized threshold behavior

The main settings remain normalized independent of bit depth.

Use exact/wide integer comparisons where possible so, for example, a 25% threshold has corresponding meaning across 255 and 65535 channel ranges.

### U16 preservation

Tests must include values that cannot be represented as 8-bit * 257. Verify they survive no-op and sorting moves exactly.

## 11. Add codec abstraction

Define a small codec layer such as:

```cpp
struct DecodedImage {
    PixelFormat format;
    ImageBuffer...;
    ColorProfile profile;
    OrientationMetadata orientation;
};

class ImageCodec { ... };
```

Do not make the sorting engine know about PNG/JPEG.

Choose mature dependencies according to `92_DEPENDENCY_AND_LICENSE_POLICY.md`.

### PNG

Implement decode/encode for at least:

- RGB8
- RGBA8
- grayscale8
- RGB16
- RGBA16
- grayscale16

Convert into canonical RGBA at the **same bit depth**.

PNG16 channel byte order must be handled correctly on all supported hosts.

### JPEG

Implement decode to RGBA8.

JPEG export:

- quality 1–100
- alpha flattened onto black
- result encoded as 8-bit JPEG

For a U16 render exported to JPEG:

1. keep native full result U16
2. flatten/convert into an export scratch buffer using high-precision arithmetic
3. quantize to U8 deliberately
4. encode JPEG

Do not mutate/replace the native U16 render with its JPEG conversion.

### Atomic output

Preserve V1's safety principle:

- write to a temporary file in/near the destination
- flush/close successfully
- atomically replace/move into final destination where platform semantics permit
- clean temporary file on failure

The later application layer will handle user overwrite confirmation/naming.

## 12. EXIF orientation

Apply EXIF orientation before the image becomes the canonical source.

For JPEG, implement a focused safe parser or use an already-approved lightweight dependency. Do not add a large metadata framework just for orientation unless justified.

Support/test EXIF orientation values 1–8.

After application:

- canonical pixels are upright
- canonical dimensions reflect the orientation
- masks/interval images must match those canonical dimensions
- orientation metadata need not be carried into later processing/export

## 13. ICC color management

Integrate a mature ICC engine such as Little CMS 2.

Import pipeline:

```text
Decode native depth
    -> apply EXIF orientation
    -> inspect source ICC
    -> convert source pixels to defined sRGB working space
    -> canonical RGBA8 or RGBA16
```

Requirements:

- preserve bit depth during transform
- tagged sRGB should not be double-transformed incorrectly
- define behavior for untagged source (treat as sRGB for MVP unless evidence/product decision says otherwise)
- exported PNG/JPEG should carry appropriate sRGB/profile information so output is interpreted correctly
- do not reattach the original non-sRGB profile to pixels already converted to sRGB

Document color assumptions.

## 14. Auxiliary image loading

Masks and interval images are image-specific.

Requirements:

- decode auxiliary file
- apply orientation rules consistently if the auxiliary format carries orientation; document the behavior
- validate exact dimensions against canonical source
- reject mismatches with typed error
- convert to grayscale/binary semantic data
- threshold at 50% of the current auxiliary sample range

For U8, 50% corresponds to the V1 `>=128` rule.

Prefer compact binary/byte storage rather than full RGBA once the auxiliary image has been interpreted.

## 15. Pipeline-ready processing stage

Even though the MVP UI exposes only one sort operation, avoid a monolithic function that assumes source->sort->export forever.

Define a stage seam conceptually like:

```cpp
class ProcessingStage {
public:
    virtual Result process(const ImageView&, MutableImageView&, ...)=0;
};

class PixelSortStage : public ProcessingStage { ... };
```

Avoid excessive abstraction/virtual calls in the pixel loop. The seam is orchestration-level.

Future stages may include additional sort passes, curved paths, etc.

## 16. Render backend seam

Create one minimal backend abstraction:

```text
RenderBackend
└── CpuRenderBackend
```

Do not implement GPU support.

Do not design Vulkan/Metal/OpenGL abstractions now. The only goal is to keep the application/FFI orchestration from depending on CPU implementation internals.

## 17. Implement native worker pool

Only begin after single-thread engine tests are green.

Requirements:

- fixed worker pool per engine/context, not one new thread per path
- path-level work units
- source buffer read-only during stage
- output writes limited to coordinates belonging to the assigned path
- no per-pixel mutex
- scratch memory preferably worker-local and reused
- deterministic path-local RNG independent of task execution order

Avoid oversubscription if multiple jobs can exist. Milestone 3 will define application job priorities; the engine pool should expose enough scheduling control to support it.

### Worker count

Provide an automatic count and an explicit cap.

A reasonable initial desktop policy can be based on `hardware_concurrency` while reserving enough capacity for the UI/OS; exact tuning comes from benchmarks.

Do not hard-code one universal count for Android; expose policy inputs for Milestone 5.

## 18. Cancellation primitive

Implement a lightweight cancellation token, likely atomic.

Check cancellation at safe, reasonably frequent boundaries:

- before a path
- between substantial interval operations
- within exceptionally long sort/preparation loops if needed

Do not add an atomic check for every single trivial pixel if it materially harms throughput; benchmark granularity.

A cancelled operation returns a typed cancelled state rather than partial success.

## 19. Transactional render result model

At engine/orchestrator level distinguish:

```text
last_completed_full_render
candidate_full_render
```

Candidate is promoted only after the full job succeeds.

On cancellation/failure:

- destroy/discard candidate
- keep previous completed result unchanged

This must be testable before Flutter exists.

## 20. Progress primitives

Expose an engine-level stage enum and normalized progress fraction/units.

Suggested stages:

- PreparingImage
- GeneratingPaths
- Sorting
- BuildingPreview (placeholder/use later)
- Encoding

For sorting, progress should be tied to completed path/work units, preferably weighted by path lengths if simple path counts are misleading.

Do not create fake time-based percentages.

## 21. Memory estimator and safety gate

Before allocating a candidate full render, estimate at minimum:

- canonical source bytes
- previous completed full-render bytes if retained
- candidate output bytes
- mask bytes
- interval-image bytes
- worker scratch worst-case
- codec/decode/encode allowance relevant to operation
- safety margin

Use overflow-safe arithmetic.

Expose a configurable memory-budget input/policy so:

- desktop app can choose a reasonable fraction/limit
- Android can be more conservative later
- tests can inject tiny budgets

If estimate exceeds budget:

- reject before large allocation
- return a typed `InsufficientMemoryBudget`-style error with estimated/allowed bytes
- do not silently downsample a full render
- do not silently convert U16 to U8

No tiled/out-of-core implementation in MVP.

## 22. Native benchmark harness

Create a standalone benchmark executable/script that can output machine-readable JSON.

Benchmark cases should include at least:

- 1920x1080 U8 representative case
- 6000x4000 U8 representative case
- 6000x4000 U16 representative case
- lightness
- hue
- saturation
- Random/Waves
- mask-heavy
- interval-image-heavy
- 0°
- 45°
- 90°

Measure separately where practical:

- decode
- color transform
- path generation
- interval/sorting core
- encode
- total
- peak resident memory

Do not set a pass/fail seconds target yet. Preserve data for later optimization.

## 23. Sanitizers/static quality

Linux debug CI/local where practical:

- AddressSanitizer
- UndefinedBehaviorSanitizer

Add ThreadSanitizer coverage once multithreading is stable if compatible with dependencies/toolchain.

Windows:

- MSVC warnings and native unit tests

Do not compile third-party libraries with project warnings-as-errors unless configured cleanly.

## 24. Documentation produced

Create/update:

- `docs/v2/ENGINE_ARCHITECTURE.md`
- `docs/v2/ENGINE_SEMANTICS.md`
- `docs/v2/RNG_SEMANTICS.md`
- `docs/v2/COLOR_PIPELINE.md`
- `docs/v2/MEMORY_MODEL.md`
- `docs/v2/BENCHMARKING.md`

The RNG/path/fixed-point semantics documentation is especially important because it becomes the cross-platform reproducibility contract.

## Hard completion gates

Milestone 2 is complete only when all are PASS:

### Core

- [ ] U8 and U16 native buffers implemented without silent conversion.
- [ ] Validation rules ported and tested.
- [ ] All five sorting modes implemented and tested.
- [ ] Stable ties preserve input order.
- [ ] All seven interval modes implemented.
- [ ] V1 mask semantics reproduced exactly.
- [ ] RGBA including alpha moves as one pixel.

### Compatibility/determinism

- [ ] Exact V1 byte-parity matrix passes for intentionally compatible cases.
- [ ] Random/Waves/nonzero-randomness cases are deterministic within V2.
- [ ] V2 RNG semantics documented.
- [ ] 1 worker == 2 workers == N workers for deterministic hashes.

### Directional paths

- [ ] 0/90/180/270 cardinal paths behave correctly.
- [ ] Non-cardinal direct paths implemented without image rotation/resampling.
- [ ] Every tested pixel belongs to exactly one path for all property-test angles/dimensions.
- [ ] Output pixel multiset invariants pass.
- [ ] Path interface is extensible to future non-straight providers.

### Image I/O/color

- [ ] PNG8 decode/encode tests pass.
- [ ] PNG16 decode/encode tests pass with exact preservation fixtures.
- [ ] JPEG decode/encode tests pass.
- [ ] JPEG alpha flattens to black.
- [ ] U16->JPEG conversion does not mutate U16 render.
- [ ] EXIF orientations 1–8 are tested.
- [ ] ICC -> sRGB conversion is implemented/tested at U8 and U16.
- [ ] Auxiliary exact-dimension validation passes.

### Runtime

- [ ] Worker pool implemented without per-pixel locks.
- [ ] Cancellation works safely.
- [ ] Cancelled/failed candidate cannot replace last completed render.
- [ ] Real stage/progress primitives exist.
- [ ] Memory budget can reject unsafe jobs before major allocation.
- [ ] Benchmark harness reports reproducible JSON/data.
- [ ] Sanitizer/unit CI is green where configured.

## End-of-milestone handoff

Report:

- exact V1 parity matrix count/result
- RNG determinism test hashes for 1/N workers
- path coverage property-test scope/result
- PNG8/PNG16/JPEG/ICC/EXIF test counts
- sanitizer results
- benchmark JSON/artifact locations
- current dependency/license changes
- any intentional behavior difference from V1 beyond the two pre-approved areas

Do not begin polished Flutter/FFI application work if the native engine has unresolved correctness/determinism failures.
