# Milestone 3 — FFI, Preview System, and Application State

## Objective

Connect the validated C++ engine to Flutter through a small stable C ABI and build the nonvisual application architecture needed for the Linux and Android UIs.

At the end of this milestone:

- Dart can create/use native engines/documents/jobs without knowing C++ details
- heavy work is asynchronous and cancellable
- full-resolution buffers stay native-side
- preview buffers cross the boundary in display-ready form only
- low/full-resolution preview behavior is implemented
- render identity/stale-state semantics are explicit
- general undo/redo, presets, Recent Presets, and persistence models exist
- a minimal end-to-end Flutter vertical slice can open/process/preview/render/export using the real engine

Do not spend this milestone polishing the desktop visual design. Build state, behavior, and testability first.

## 1. Freeze a C ABI v1

Create a public C header under the native package/engine boundary, for example:

```text
packages/chromasunder_native/src/chromasunder_c_api.h
```

or an installed header generated/exported by the engine.

### ABI design rules

- C-compatible types only.
- Opaque handles for engine/document/job/render objects.
- No `std::string`, STL containers, C++ references, or C++ classes in public ABI.
- No exception can cross the ABI.
- Every operation returns a typed status/result.
- Define ownership/release responsibilities explicitly.
- Use fixed-width integer types.
- Every extensible input/output struct begins with:

  ```c
  uint32_t abi_version;
  uint32_t struct_size;
  ```

- Validate both before reading optional/new fields.

### Recommended handles

Conceptually:

```c
typedef struct cs_engine_t cs_engine_t;
typedef struct cs_document_t cs_document_t;
typedef struct cs_job_t cs_job_t;
typedef struct cs_render_t cs_render_t;
```

Do not expose their layouts.

### Error model

Define stable error categories such as:

- OK
- invalid argument
- invalid handle
- unsupported format
- decode failure
- validation failure
- auxiliary dimension mismatch
- insufficient memory budget
- cancelled
- I/O failure
- internal failure
- ABI mismatch

Provide a safe way to obtain human-readable detail for the last/result-specific error without requiring Dart to own native memory indefinitely.

## 2. Define settings structs/enums

Mirror V2 engine settings through explicit C enums/structs.

Do not pass JSON for the hot/common settings path.

Fields include:

- interval mode
- sorting mode
- lower threshold
- upper threshold
- characteristic length
- angle degrees
- randomness percent
- seed

Use generated Dart enum/value mapping tests so adding/reordering a Dart enum cannot silently change the native numeric mapping.

## 3. Native object lifecycle

Recommended relationship:

```text
Engine
  └── Document
       ├── canonical source
       ├── optional mask
       ├── optional interval image
       ├── last completed full render
       └── jobs
```

Define clearly whether jobs retain document/engine references internally so Dart cannot accidentally destroy required resources while a job is active.

Preferred behavior:

- engine/document release returns a defined busy/error state or safely waits/cancels according to documented contract
- job handles can be released after completion/collection
- double release is protected in Dart and does not become a use-after-free in C++

Add lifecycle stress tests.

## 4. Heavy work must be asynchronous

The following must not run synchronously on Flutter's UI isolate through a long FFI call:

- source import/decode/color conversion
- mask/interval image import if nontrivial
- preview render
- full-resolution render
- export/encoding

Use native asynchronous jobs.

### Job API concept

A start function should return quickly:

```text
start job -> job handle
```

Then Dart can:

```text
poll status/progress
cancel
collect result
release
```

A dedicated native coordinator thread plus the engine worker pool is acceptable. Do not spawn a new OS process.

Avoid callbacks from arbitrary native worker threads into Dart for the MVP unless a strong reason emerges. Polling lightweight job state on a UI timer is simpler and safer.

## 5. Job status and progress ABI

Expose:

- job state: queued/running/completed/cancelled/failed
- current stage enum
- normalized progress or completed/total work units
- typed error code if failed

Suggested stages:

- Preparing Image
- Generating Paths
- Sorting
- Building Preview
- Encoding

Progress must be monotonic within a job and based on actual work.

Flutter may localize/friendly-format labels; engine sends semantic stage identifiers, not hardcoded UI strings.

## 6. Preview transfer contract

Full-resolution working pixels must never be a routine Dart-return value.

For preview results, return metadata:

- width
- height
- display pixel format (RGBA8888 for MVP)
- byte count
- render/document revision identity

Use a two-step bounded copy pattern:

1. query required preview byte size/metadata
2. Dart allocates appropriately sized native/Dart buffer
3. native copies at most the provided capacity

If capacity is too small, return required size rather than writing out of bounds.

Alternative zero-copy/native-texture optimization is post-MVP unless measurements prove this copy is a bottleneck.

## 7. Handwritten Dart native service

Generated `ffigen` bindings must remain low-level.

Create a handwritten layer such as:

```text
lib/native/
├── native_engine.dart
├── native_document.dart
├── native_job.dart
├── native_models.dart
└── native_errors.dart
```

UI/application state code calls this layer, never raw generated binding functions.

Responsibilities:

- handle ownership
- enum mapping
- typed exceptions/results
- polling job lifecycle
- cancellation
- preview byte collection
- native error translation
- test seam/injection

Define an interface such as `EngineApi` so tests can use a fake implementation without loading the native library.

## 8. Application state architecture

Create explicit app/document models before polished widgets.

Recommended structure:

```text
ApplicationState
├── AppPreferences
├── PresetRepository
├── RecentPresetRepository
└── DocumentManager
     └── currentDocument (0 or 1 in MVP)
```

### Document model

Track logical state separately from native handles:

- source display name/identity
- canonical source metadata
- width/height
- bit depth
- source format
- mask identity/metadata
- interval-image identity/metadata
- current `PixelSortSettings`
- editor revision
- undo/redo history
- latest preview identity/state
- last completed full-render identity/state
- active job(s)

`DocumentManager` must be written so it can later hold multiple documents, but do not implement tabs/multiple open documents now.

## 9. Render identity and stale-state semantics

Do not infer staleness from one boolean that widgets manually toggle.

Define a value identity/signature generated from semantic revisions, for example:

```text
RenderInputIdentity
- sourceRevision
- maskRevision
- intervalImageRevision
- settingsRevision or stable settings value hash
- engineSemanticsVersion
```

A completed full render stores the identity it rendered.

Current full render is fresh iff:

```text
completed.identity == currentDocument.renderInputIdentity
```

Changing only UI layout/preferences must not stale a render.

Changing any render-affecting setting/aux input must stale it.

A successful Full Resolution Preview stores a full result with current identity and therefore makes it fresh.

## 10. Canonical source/snapshot behavior

When an image is opened:

- native document imports/decodes it into the canonical source
- source is then treated as fixed for the current document
- do not watch source file for external edits
- do not repeatedly decode source for each render

For Android later, platform URI input will first be snapshotted to app-private storage before native import. Keep Dart/native document APIs compatible with both local paths and future safe byte/file adapter input.

## 11. Preview resolution algorithm

Implement one central function, independently unit-tested.

Inputs:

- canonical source width/height
- logical preview viewport width/height
- device pixel ratio
- minimum proxy constant

### Physical target

Compute:

```text
physicalWidth  = logicalWidth  * DPR
physicalHeight = logicalHeight * DPR
```

Use an explicitly documented integer rounding method.

Fit source aspect ratio inside this physical target.

### Never upscale processing

Final proxy dimensions must not exceed source dimensions.

If source is smaller than viewport, process at native source dimensions and let Flutter scale display pixels visually.

### Tiny viewport clamp

Use one simple minimum proxy rule to prevent absurdly tiny processing.

Initial policy:

- approximately 256 pixels on the longest proxy side
- never exceed source dimensions
- preserve aspect ratio

Do not build complex adaptive quality heuristics in MVP.

## 12. Proxy generation/cache

Cache low-resolution source proxy keyed by:

- source revision
- target proxy dimensions
- bit depth/color-space semantics version if needed

Generate mask/interval proxies to exactly the same target dimensions.

### Source proxy

- RGBA8 source -> RGBA8 proxy
- RGBA16 source -> RGBA16 proxy
- use approved high-quality resize filter

### Binary mask / interval proxy

Do not blur into weighted semantics.

Use nearest-neighbor or another explicitly binary-preserving rule so result remains on/off.

### Cache invalidation

- viewport target changes materially -> rebuild target proxy
- mask change -> rebuild mask proxy only as needed
- settings change alone -> reuse source/aux proxies

Do not resize source for every slider event.

## 13. Spatial-setting preview scaling

The UI stores full-resolution settings.

For a low-resolution preview job compute a derived native preview settings value.

For Characteristic Length:

```text
previewLength = max(1, round(sourceLength * spatialScale))
```

Derive `spatialScale` consistently from the actual source/proxy mapping. If aspect-ratio fit produces a single uniform scale, use that value.

Do not mutate the user's stored setting.

Do **not** scale:

- angle
- normalized lower threshold
- normalized upper threshold
- randomness percentage
- seed

Document any future spatial settings so they cannot accidentally skip this translation.

## 14. 16-bit preview path

For a U16 canonical source:

```text
U16 canonical source
  -> U16 proxy
  -> U16 sorting
  -> U16 preview result
  -> display conversion only
  -> RGBA8888 preview bytes
```

Do not make U16 low-res preview use an 8-bit proxy simply because Flutter displays RGBA8.

Define deterministic display conversion. A simple expected mapping is conceptually:

```text
round(channel16 * 255 / 65535)
```

Use integer math with defined rounding and preserve alpha similarly.

This display conversion must never replace the U16 native render.

## 15. Live Preview controller

Create one centralized controller/state machine; do not scatter timers through slider widgets.

Defaults:

- Live Preview: ON
- Full Resolution Preview: OFF

### Debounce

Use a small configurable constant, initially around 100–150 ms; 120 ms is a reasonable starting value.

While a continuous control changes:

1. update editor state immediately
2. mark stale state immediately
3. cancel/supersede older low-priority preview request
4. restart debounce
5. after quiet period, render newest state only

When the gesture/control is finalized/released:

- schedule newest preview immediately without waiting for the remaining debounce

### Viewport resize debounce

Use a separate small debounce around ~150 ms so dragging desktop panes/window size does not continuously rebuild proxies.

These timings are implementation constants, not user-facing promises; tune only if measured UX warrants it.

## 16. Job generation and stale completion protection

Every scheduled preview gets a monotonically increasing request/generation ID.

When a job completes:

- verify it belongs to the current document
- verify generation/identity is still expected
- discard result if a newer preview request superseded it

A cancelled or late obsolete native job must never overwrite a newer preview.

## 17. Job priorities

Establish at least conceptual priority ordering:

1. export-required current full render
2. explicit Render button full render
3. Full Resolution Live Preview
4. final low-resolution preview after user input release
5. debounced intermediate low-resolution preview

It is acceptable if the first engine scheduler implementation cannot preempt a currently running expensive full render, but queued obsolete previews must be removable/cancellable and must not delay explicit Render/Export work unnecessarily.

Document scheduler semantics.

## 18. Full Resolution Preview behavior

When enabled:

- automatic Live Preview jobs use canonical source resolution, not proxy
- spatial settings remain unscaled
- successful completed result is retained as the document's current full-resolution result
- the UI preview displays a display-scaled representation generated from that full result
- Export can use it without pressing Render again if identity still matches

Changing a setting immediately stales that previous full result even if it remains available as "previous full render" for the stale-export dialog.

## 19. Render button behavior

Explicit Render:

- always uses canonical full resolution
- always uses current settings/aux inputs
- returns transactional result
- on success becomes current completed full render
- on cancel/failure leaves prior completed full result unchanged

Render remains useful even with Live Preview enabled because normal default preview is low resolution.

## 20. Original / Rendered preview state

Model preview selection as application/UI preference:

```text
Original
Rendered
```

Do not add split view.

When Original selected:

- display original preview proxy/display representation
- do not schedule an unnecessary sorting job just to show original

When Rendered selected:

- show newest successful preview appropriate to current state
- define clear empty/loading/stale UI state without conflating it with last completed full export result

## 21. Stale export decision workflow

Centralize it in application state/service rather than the final dialog widget.

If current full result is fresh:

- export it directly

If a previous completed full result exists but is stale:

return/drive three explicit choices:

1. Render Current Settings & Export
2. Export Previous Full-Resolution Render
3. Cancel

Choice 1:

- start full render of current identity
- export only if render succeeds

Choice 2:

- export the previous completed render bytes represented by its own stored native render handle/identity
- do not relabel it as current

Choice 3:

- no native work/output

If no completed full render exists at all, Export should require rendering current settings rather than offering a nonexistent previous export.

## 22. General Undo/Redo history

Replace V1 settings-only history with lightweight render-affecting editor snapshots/actions.

History content includes:

- PixelSortSettings
- mask selection identity/reference
- interval-image selection identity/reference

Preset application is one logical history action.

Do not include:

- source pixel buffer
- full render pixel buffer
- preview bytes
- active job state
- progress
- window/layout preferences
- Original/Rendered toggle

### Slider coalescing

A drag from 20% -> 70% must not generate dozens/hundreds of undo states.

Preferred behavior:

- capture pre-gesture state once
- live-update current state during drag
- commit one history transition when gesture completes

Keyboard/text-step edits may remain individual logical actions.

Default history capacity can remain around 100 unless there is a measured reason to change it.

Opening a new source begins a new document history.

## 23. Preset model and V1 importer

### V2 schema

Keep:

```text
.csunder
```

Use a versioned JSON document, likely schema 2.

Required contents:

- format identifier
- schema version
- application/engine version metadata as useful
- processing settings only

Never serialize:

- source path
- mask reference/path
- interval-image reference/path
- default export path
- document history

### V1 schema-1 importer

Implement best-effort mapping from current preset schema.

Map all compatible fields.

Accept that:

- same V1 seed may create a different V2 random arrangement
- arbitrary non-cardinal angle output differs due to new path engine

Do not preserve Python-only legacy implementation details in the V2 model.

### Cross-platform portability

Preset JSON must contain no platform-specific path separators/path fields.

Use UTF-8.

## 24. Recent Presets repository

Recent Presets is MVP.

Track a bounded recent list with:

- most recent first
- canonical deduplication where platform permits
- missing preset handled gracefully
- clear-recent action

Do not add Recent Source Files in MVP.

On Android, persisted content URI handling for presets can be adapted in Milestone 5; keep repository abstraction path/URI-neutral enough to support it.

## 25. Preferences model

Create typed `AppPreferences` for eventual persisted values:

- Live Preview (default true)
- Full Resolution Preview (default false)
- default export format (PNG)
- preserve-source-format preference if modeled as a selected export mode
- default export directory reference
- CPU cap/automatic mode
- desktop window geometry
- desktop divider positions
- Original/Rendered selection
- other non-document UI preferences

Do not persist/reopen the previous active source document.

Platform-specific persistence implementation can be completed in Milestones 4/5; define/test the serialization model now.

## 26. Minimal vertical-slice Flutter screen

Before polished Linux UI, build a deliberately plain screen that proves:

1. open/select a local test image
2. native import completes
3. show source metadata
4. change a few settings
5. schedule low-resolution preview
6. display RGBA8 preview bytes
7. explicit full Render
8. cancel a render
9. export current full result
10. verify stale identity logic

Use the real engine through `EngineApi`.

Do not spend time on cyberpunk styling here.

## 27. Fake native engine for Dart/widget tests

Implement `FakeEngineApi` capable of:

- controlled job delays
- controlled progress sequence
- cancellation
- failure injection
- out-of-order preview completion
- deterministic preview bytes
- full-render identity

Use it to test Live Preview, staleness, Undo/Redo, and UI controllers without needing native rendering in every Flutter test.

## 28. Required tests

Follow `91_TEST_GATE_MATRIX.md` sections for:

- C ABI lifecycle/error/size checks
- Dart enum/settings mapping
- async start/poll/cancel/collect
- bounded preview copy
- physical-DPR preview sizing
- minimum proxy clamp/no upscale
- spatial scaling
- U16 proxy/display conversion
- Live Preview debounce/supersession
- Full Resolution Preview freshness
- stale export three-way behavior
- Undo/Redo coalescing
- preset schema 2 + V1 import
- Recent Presets
- preference serialization

## 29. Documentation produced

Create/update:

- `docs/v2/C_ABI.md`
- `docs/v2/FFI_LIFECYCLE.md`
- `docs/v2/PREVIEW_ARCHITECTURE.md`
- `docs/v2/APP_STATE.md`
- `docs/v2/PRESET_SCHEMA.md`
- `docs/v2/RENDER_IDENTITY.md`

## Hard completion gates

### C ABI / FFI

- [ ] Versioned C ABI exists with opaque handles and typed errors.
- [ ] No exception crosses ABI.
- [ ] Heavy work starts asynchronously and returns a job handle promptly.
- [ ] Poll/progress/cancel/collect lifecycle is tested.
- [ ] Full-resolution pixels are not part of normal Dart transfer API.
- [ ] Preview bounded-copy API is tested for correct and undersized buffers.
- [ ] Generated bindings are hidden behind handwritten Dart service.
- [ ] Fake `EngineApi` exists for tests.

### Preview

- [ ] Physical viewport = logical × DPR sizing is implemented/tested.
- [ ] Proxy preserves aspect ratio.
- [ ] Proxy never upscales beyond source.
- [ ] Simple tiny-window minimum clamp works.
- [ ] U8 source uses U8 proxy.
- [ ] U16 source uses U16 proxy through sorting.
- [ ] Display conversion occurs only after U16 preview rendering.
- [ ] Characteristic Length scales correctly for low-res proxy.
- [ ] Mask/interval proxies remain binary.

### Live/full render

- [ ] Live Preview defaults ON.
- [ ] Full Resolution Preview defaults OFF.
- [ ] Debounce/cancel/supersession is tested.
- [ ] Final control release triggers newest preview immediately.
- [ ] Late obsolete job cannot replace latest preview.
- [ ] Full Resolution Preview completion becomes valid current full result.
- [ ] Explicit Render always uses canonical full resolution.
- [ ] Cancelled explicit render preserves previous full result.
- [ ] Stage + real percentage reach Dart state.

### App state

- [ ] One-document `DocumentManager` implemented with future multi-document seam.
- [ ] Render identity/stale logic is value-driven, not widget booleans.
- [ ] Stale export supports all three required decisions.
- [ ] General render-affecting Undo/Redo works without pixel buffers.
- [ ] Slider history is coalesced.
- [ ] V2 portable settings-only presets round trip.
- [ ] V1 preset importer works for mappable fields.
- [ ] Recent Presets works; Recent Source Files not added.
- [ ] Preferences model serializes without active source restoration.

### Vertical slice

- [ ] Minimal Flutter screen can import -> preview -> full render -> export using real native engine on Linux.
- [ ] Flutter/Dart tests and C ABI tests are green.
- [ ] Windows CI remains green.
- [ ] Android build remains green.

## End-of-milestone handoff

Report:

- C ABI version/header location
- generated binding regeneration command
- native job lifecycle description
- preview sizing/scaling test matrix result
- Live Preview debounce value currently used
- stale export tests
- Undo/Redo/preset tests
- a successful real-engine vertical-slice run on Fedora
- Windows/Android CI status
