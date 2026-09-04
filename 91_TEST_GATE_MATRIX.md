# Chroma Sunder V2 — Test and Gate Matrix

This file defines minimum automated/manual coverage. Add more tests whenever implementation risk warrants it.

## 1. V1 migration/reference tests

### Baseline

- Current V1 suite passes before migration extraction.
- Standalone Python reference renderer produces stable golden hashes for preserved fixtures.
- Record reference renderer version/baseline commit.

### Exact V1 byte-parity matrix

Require exact RGBA output for cases whose semantics remain intentionally compatible:

- sorting modes:
  - Lightness
  - Hue
  - Saturation
  - Intensity
  - Minimum
- deterministic interval modes:
  - None
  - Threshold
  - Edges
  - File
  - File Edges
- masks:
  - none
  - all off
  - all on
  - sparse
  - alternating/gapped
  - edge-position masks
- cardinal directions where direct paths map exactly:
  - 0°
  - 90°
  - 180°
  - 270°
- randomness percentage = 0
- transparency fixtures
- repeated/tied sorting-key fixtures

Do not require V1 byte parity for Random/Waves RNG sequences, nonzero interval-skip randomness, or non-cardinal angles.

## 2. Core settings/validation tests

Cover:

- lower threshold minimum/maximum/out-of-range
- upper threshold minimum/maximum/out-of-range
- lower > upper rejection
- Characteristic Length 1 and invalid 0/negative
- randomness 0, 100, out-of-range
- seed 0, max supported value, invalid negative at application boundary
- finite angle accepted
- NaN/infinity rejected
- File/File Edges require interval image
- auxiliary exact-dimension enforcement

## 3. Sorting-key tests

For both U8 and U16:

- Lightness ordering follows max+min semantics.
- Hue ordering matches the defined V2/V1-compatible HLS hue ordering.
- Saturation ordering matches HLS saturation semantics.
- Intensity uses R+G+B without overflow.
- Minimum uses min(R,G,B).
- Alpha does not affect sort key unless a future algorithm explicitly says so.
- Stable ties preserve incoming path order.

Include:

- black
- white
- primary colors
- secondary colors
- grayscale
- equal-key distinct pixels
- channel extremes
- U16 values that are not multiples of 257

## 4. Interval-mode tests

### None

- whole path emitted when length >=2
- no interval for path shorter than 2

### Threshold

- inclusive lower boundary
- inclusive upper boundary
- values immediately outside boundaries
- multiple separated runs
- one-pixel runs excluded

### Edges

- boundary when adjacent lightness delta == threshold
- no boundary immediately below threshold
- multiple boundaries
- minimum interval length behavior

### Random

- deterministic for same V2 seed/path/engine semantics
- different seed changes output for a suitable fixture
- intervals respect characteristic length rule
- no interval shorter than 2 emitted

### Waves

- deterministic for same V2 seed/path/engine semantics
- variation bounded as specified
- no interval shorter than 2 emitted

### File

- connected true runs
- leading/trailing runs
- one-pixel true runs excluded if V1 semantics exclude them

### File Edges

- transitions generate expected boundaries
- leading previous=false behavior
- deduplicated boundaries

## 5. Mask semantics

Test the exact V1 rule:

- interval is determined first
- mask then selects sortable positions inside that interval
- mask gaps do not create new interval boundaries
- masked-off pixels remain in place
- enabled pixels can move across disabled gaps when they belong to the same interval
- RGBA moves as one unit

## 6. U8/U16 equivalence/integrity

For algorithmically equivalent values, create paired fixtures where U16 = U8 * 257 and verify normalized decisions/order are equivalent.

Also test native U16-only precision values:

- 0
- 1
- 255
- 256
- 257
- 32767
- 32768
- 65534
- 65535

Verify:

- no silent U16->U8 conversion in working/render buffers
- sums/intermediates cannot overflow chosen types
- PNG16 export preserves values exactly for no-op/compatible operations

## 7. RNG determinism tests

Define a stable V2 RNG semantics version and test:

- same source/settings/seed/path ID => same result across repeated runs
- 1 worker == 2 workers == N workers
- Linux == Windows == Android reference hashes for selected fixtures
- path scheduling order changes do not change output
- changing seed changes output on a suitable fixture

Do not compare exact V2 RNG stream to Python `random.Random`.

## 8. Directional path property tests

For many dimensions and angles, including tiny/asymmetric images:

- every pixel index appears exactly once
- no duplicate coordinates
- no omitted coordinates
- all coordinates are in bounds
- path order follows the user-facing direction convention

Mandatory angles:

- 0°
- 1°
- 15°
- 44°
- 45°
- 46°
- 89°
- 90°
- 91°
- 135°
- 179°
- 180°
- 181°
- 225°
- 269°
- 270°
- 271°
- 315°
- 359°
- negative equivalents
- angles beyond 360 normalized as specified

Dimensions:

- 1x1
- 1xN
- Nx1
- 2x2
- asymmetric odd/even sizes
- representative larger image

Rendering invariant for full-mask/None intervals:

- output pixel multiset equals input pixel multiset exactly
- no interpolation-generated colors appear

## 9. Codec tests

### PNG

- RGB8 import
- RGBA8 import
- grayscale8 import
- RGB16 import
- RGBA16 import
- grayscale16 import
- alpha handling
- PNG8 export/reimport
- PNG16 export/reimport
- atomic destination replacement
- invalid/truncated file fails cleanly

### JPEG

- RGB JPEG import
- EXIF-oriented JPEG import
- ICC-profiled JPEG import
- JPEG quality lower/upper valid values
- alpha-containing render exports with black flattening
- U16 working result explicitly converts to 8-bit export path without altering native working buffer
- invalid/truncated file fails cleanly

## 10. EXIF orientation tests

Use fixtures for orientation values 1 through 8.

Verify canonical working dimensions/pixel orientation after import.

Masks/interval images are validated against the post-orientation canonical dimensions.

## 11. ICC/color tests

Use known profile fixtures where practical.

Verify:

- untagged/default behavior is defined
- tagged sRGB does not undergo harmful double conversion
- non-sRGB profile converts into sRGB
- U8 conversion remains U8
- U16 conversion remains U16
- exported PNG contains appropriate sRGB/profile information
- color conversion does not mutate source file

## 12. Concurrency tests

- single-thread vs multi-thread output hashes identical
- intentionally shuffled task scheduling output identical
- concurrent preview/full jobs obey scheduler priorities
- cancellation from another thread is safe
- no path writes overlap
- ThreadSanitizer run where toolchain/platform permits

## 13. Cancellation/transaction tests

Full render:

1. complete render A
2. start render B
3. cancel B mid-work
4. verify A is still current/exportable
5. verify B cannot be promoted/exported as complete

Also test failure path equivalent to cancellation preservation.

## 14. Memory-budget tests

- estimator accounts for source, candidate, existing full render, aux buffers, scratch, codec allowance, safety margin
- render rejected before major allocations when estimate exceeds configured budget
- rejection returns typed actionable error
- U16 estimate is larger than U8 as expected
- preview proxy can still work when full render is rejected, if its own budget is safe

## 15. C ABI / FFI tests

- ABI version mismatch rejected clearly
- struct size validation
- engine/document/job create/destroy
- double-release protected or documented-safe
- invalid handle returns typed error, not crash
- no exception crosses C boundary
- async start returns promptly
- status/progress polling
- cancellation
- collect preview metadata
- preview buffer size query + bounded copy
- insufficient destination preview buffer reports required size
- full-resolution buffer is never required by public Dart API
- export job through native API

## 16. Preview sizing tests

Use logical viewport + DPR combinations:

- 700x400 @ 1.0
- 700x400 @ 2.0
- 700x400 @ 2.5
- portrait viewport
- extremely small viewport
- viewport larger than source

Verify:

- target uses physical pixels
- aspect ratio preserved
- processing proxy never exceeds source dimensions
- minimum proxy clamp is simple and deterministic
- source-smaller-than-viewport does not upscale processing

## 17. Preview precision/scaling tests

- U16 source creates U16 proxy
- U16 preview render remains U16 until display conversion
- display conversion produces expected RGBA8 values
- Characteristic Length scales with proxy scale and remains >=1
- angle unchanged
- thresholds unchanged
- randomness percentage unchanged
- binary mask proxy remains binary
- interval-image proxy remains semantically binary

## 18. Live Preview tests

Using a fake native engine and selected integration tests:

- Live Preview defaults ON
- Full Resolution Preview defaults OFF
- rapid slider changes collapse/cancel obsolete jobs
- slider release schedules final value immediately
- viewport resizing is debounced
- stale job completion cannot replace a newer preview
- Render button has higher priority than obsolete preview work
- successful full-resolution preview becomes current valid full render

## 19. Stale-render/export tests

Create completed full render, then independently change:

- setting
- mask
- interval image

Verify stale state.

Dialog choices:

- Render Current Settings & Export => renders newest state then exports that result
- Export Previous Full-Resolution Render => exports previous completed result unchanged
- Cancel => no render/export

A successful full-resolution preview of current state clears stale status.

## 20. Undo/Redo tests

Undoable:

- thresholds/settings
- mode selection
- angle
- randomness/seed
- Characteristic Length
- preset application as one logical action
- mask add/remove/change
- interval image add/remove/change

Verify:

- no pixel buffers stored in history
- slider drag is coalesced into sensible logical history, not hundreds of steps
- new source clears document history
- redo invalidates correctly after divergent edit
- default history capacity approximately 100 unless deliberately revised

## 21. Preset tests

- V2 save/load round trip
- Linux-created fixture loads identically in Android/Dart logic
- Android-created fixture loads identically on desktop
- preset contains processing settings only
- no source/mask/interval/export path serialization
- V1 schema-1 import for mappable fields
- malformed/unsupported preset produces clear error
- Recent Presets ordering/deduplication/clear behavior

## 22. Export filename tests

Source `example.png`:

- no collision => `example_sorted.png`
- collision => `example_sorted_2.png`
- then `_3`, etc.

Source `example_sorted.png`:

- avoid `example_sorted_sorted.png`
- if output collision, use `example_sorted_2.png`

Also test:

- uppercase/mixed extensions
- JPEG output extension
- Preserve Source format
- names containing dots
- Unicode names
- destination race handled without destructive overwrite unless explicit overwrite flow permits it

## 23. Linux integration flows

At minimum automate or manually gate:

1. launch empty editor
2. Open PNG8
3. drag/drop source
4. low-res Live Preview setting change
5. Full Resolution Preview
6. explicit Render
7. cancel render and retain prior full result
8. add/remove mask
9. add/remove interval image
10. save/load preset + Recent Presets
11. Undo/Redo
12. stale Export Previous path
13. stale Render Current & Export path
14. export PNG/JPEG/default-directory/beside-source as applicable

## 24. Android integration flows

Test on Android 13+ ARM64 real device and x86_64 emulator/development path:

- portrait and landscape
- system document open
- Photo Picker
- ACTION_VIEW/Open With
- ACTION_SEND/Share To
- mask/interval selection
- all core processing controls available
- Live Preview
- Full Resolution Preview
- Render/cancel
- Save As
- Save to Gallery
- Share Export
- persistent default directory after restart
- 16-bit PNG workflow
- memory-budget rejection
- no unintended INTERNET permission in final manifest

## 25. Windows validation matrix

CI continuously:

- C++ MSVC build/tests
- Dart/Flutter tests
- Flutter Windows release build

Hands-on before final V2 hardening:

- launch
- native window chrome
- HiDPI
- Open dialog
- drag/drop
- presets
- Live Preview
- Full Render
- cancellation
- masks/interval images
- PNG8/PNG16/JPEG
- default export directory
- logs
- portable ZIP on clean Windows 10/11 environment

## 26. Packaging gates

### AppImage

- launches on Fedora test environment
- native libraries resolve without developer system paths
- no Python/GTK V1 runtime dependency
- license/notices present as required
- SHA-256 generated

### Android APK

- universal APK includes only intended 64-bit ABIs
- ARM64 launch/test
- x86_64 emulator path
- no Play-specific dependency/configuration required
- release/signing process does not commit secrets
- SHA-256 generated

### Windows ZIP

- contains Flutter/runtime/native dependencies needed to run
- tested from clean extracted directory
- no developer absolute paths
- license/notices included
- SHA-256 generated

## 27. Final privacy audit

Search source, manifests, dependencies, and built artifacts/config for unintended:

- analytics
- telemetry
- crash upload
- HTTP clients used by product functionality
- remote config
- accounts/auth
- cloud storage
- image upload

Android final merged manifest must not request Internet permission unless a future explicit user-approved update-check feature is actually implemented.
