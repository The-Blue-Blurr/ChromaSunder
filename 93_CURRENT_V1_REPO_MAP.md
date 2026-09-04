# Chroma Sunder V1 — Migration Reference Map

Use this file to orient work against the uploaded V1.3-era repository. Confirm paths still exist before editing because the V2 branch will gradually replace them.

## Current baseline health

At inspection time, the uploaded repository passed:

```text
1356 tests passed
25 subtests passed
```

The uploaded Git working tree was on:

```text
dev/v1.3-rendering-performance
```

and contained user/uncommitted work. Milestone 1 must preserve it rather than assuming a clean checkout.

## Core processing files

### `src/chromasunder/core/enums.py`

Defines current public processing modes.

Interval modes:

- `threshold`
- `edges`
- `random`
- `waves`
- `file`
- `file-edges`
- `none`

Sorting modes:

- `lightness`
- `hue`
- `saturation`
- `intensity`
- `minimum`

These names are compatibility-sensitive because they appear in presets/settings.

### `src/chromasunder/core/models.py`

Contains current settings/snapshot models.

Important current defaults/semantics:

- Interval: threshold
- Sorting: lightness
- Lower threshold: `0.25`
- Upper threshold: `0.80`
- Characteristic Length: `50`
- Angle: `0`
- Randomness: `0`
- Seed: nonnegative integer

`RenderSnapshot` already captures the important stale-render idea: render identity is tied to settings and source/auxiliary inputs. Preserve the concept, not the Python implementation.

### `src/chromasunder/core/validation.py`

Current validation rules include:

- thresholds within `[0, 1]`
- lower threshold <= upper threshold
- randomness within `[0, 100]`
- Characteristic Length >= 1
- seed nonnegative
- angle finite
- File / File Edges require interval image
- mask/interval image must exactly match source dimensions

Port these rules unless a V2 milestone explicitly supersedes them.

### `src/chromasunder/core/imaging.py`

Important V1 behavior:

- PNG/JPEG are the official image formats.
- EXIF orientation is applied with Pillow `ImageOps.exif_transpose`.
- V1 canonical processing is RGBA8; V2 deliberately changes this to native 8/16-bit processing.
- Auxiliary images must exactly match source dimensions.
- Binary mask/interval threshold is `>=128` in 8-bit grayscale.
- Current display copy is capped around `1200x900`; V2 replaces this with viewport/DPR-driven preview proxies.

### `src/chromasunder/core/sorting.py`

Current production sorting keys:

- Lightness: `max(R,G,B) + min(R,G,B)`
- Hue: Python `colorsys.rgb_to_hls(...)[0]`
- Saturation: Python `colorsys.rgb_to_hls(...)[2]`
- Intensity: `R + G + B`
- Minimum: `min(R,G,B)`

Current interval brightness/lightness uses normalized HLS lightness.

V2 must preserve ordering semantics for compatible cases. Avoid replacing these with superficially similar HSV metrics.

### `src/chromasunder/core/intervals.py`

Important semantics to port:

- Intervals are half-open `[start, end)`.
- Intervals shorter than 2 pixels are not emitted.
- Threshold mode includes pixels whose HLS lightness is inclusively between lower and upper thresholds.
- Edges mode creates boundaries where adjacent normalized HLS lightness delta is >= lower threshold.
- Random mode uses a characteristic-length-derived random size and emits intervals of length >=2.
- Waves mode uses characteristic length plus a small random variation.
- None mode yields the whole path/row.
- File mode uses connected true runs from the interval image.
- File Edges uses transitions in the binary interval image and deduplicated boundaries.

The exact V1 Python RNG sequence does not need to be preserved in V2; interval concepts do.

### `src/chromasunder/core/processing.py`

This is the V1 hot path and primary semantic reference.

Important behavior:

- Python `sorted(...)` is stable; V2 must preserve stable ties.
- Randomness percentage can skip entire intervals.
- A mask selects sortable positions inside an interval; mask gaps do **not** split the interval into new intervals.
- RGBA tuples move together, including alpha.
- V1 arbitrary angle processing rotates the source, mask, and interval data, sorts horizontal rows, rotates back, and crops.
- V2 deliberately removes that rotation architecture and uses direct directional pixel paths.

### `src/chromasunder/core/exporting.py`

Current useful behavior:

- Atomic save pattern via temporary output then replace.
- JPEG quality range 1–100.
- Alpha is flattened to a background color; current/default background is black.
- V1 automatic suffix is `_pxsorted`; V2 deliberately changes this to `_sorted`.

### `src/chromasunder/core/presets.py`

Current preset document is JSON and approximately:

```json
{
  "format": "chromasunder-preset",
  "schema_version": 1,
  "application_version": "...",
  "settings": {}
}
```

V2 presets remain settings-only and should use the same `.csunder` extension. Implement a best-effort schema-1 importer.

## Worker architecture — reference only, do not port

### `src/chromasunder/worker/controller.py`
### `src/chromasunder/worker/protocol.py`
### `src/chromasunder/worker/render_worker.py`

V1 uses a spawned Python worker process and communicates via files/protocol state. Full-resolution output and preview are cached/encoded as PNG artifacts.

V2 must **not** reproduce this architecture. The C++ engine is an in-process native library with native jobs, worker threads, cancellation, and C ABI handles.

## UI files

### `src/chromasunder/gui/main_window.py`

Current layout/reference behavior:

- default window roughly `1280x860`
- toolbar order/concepts: Open, Recents, Presets, Undo, Redo, Help, About, with Render and Export at the opposite end
- horizontal split: preview and controls
- bottom status/progress/cancel area
- Processing / Export controls organization
- Original / Rendered preview toggles
- empty preview message: open or drop an image

V2 keeps this general layout, modernizes the visuals, omits Recent Source Files from the MVP, and keeps Recent Presets.

Current shortcuts worth preserving:

- Ctrl+O: Open
- Ctrl+R: Render
- Ctrl+E: Export
- Ctrl+Z: Undo
- Ctrl+Shift+Z: Redo
- Escape: Cancel active job

### `src/chromasunder/gui/settings_controller.py`

Current interval-mode control sensitivity:

| Interval mode | Lower | Upper | Characteristic Length | Interval Image |
|---|---:|---:|---:|---:|
| Threshold | yes | yes | no | no |
| Edges | yes | no | no | no |
| Random | no | no | yes | no |
| Waves | no | no | yes | no |
| File | no | no | no | yes |
| File Edges | yes | no | no | yes |
| None | no | no | no | no |

Preserve this behavior unless later product changes explicitly supersede it.

### `src/chromasunder/gui/angle_dial.py`

Current angle convention:

- 0° points right
- 90° points up
- keyboard step 1°
- Shift-step 15°

The V2 direct path generator must preserve the user-facing angle convention.

### `src/chromasunder/gui/history.py`

V1 has settings-only undo/redo with a history limit of 100. V2 expands this to general render-affecting editor state while retaining lightweight snapshots rather than pixel buffers.

## Tests

### `tests/reference_renderer.py`

Contains the existing independent/reference renderer logic used to verify the production engine. Milestone 1 should extract a minimal standalone reference version from the current Python implementation.

### `tests/unit/test_render_equivalence.py`

Contains broad equivalence coverage across interval/sorting modes, angles, masks, and seeded behavior.

For V2:

Exact V1 byte parity is appropriate for deterministic compatible cases such as:

- Interval modes: None, Threshold, Edges, File, File Edges
- All five sorting modes
- Randomness = 0
- Cardinal directions where V2 direct paths map exactly
- Masks/interval images

Do **not** require V1 byte parity for:

- Random or Waves RNG sequences
- nonzero randomness skipping
- non-cardinal angles

Instead, test deterministic V2 behavior and structural invariants there.

## Benchmarks

### `benchmarks/rendering.py`
### `benchmarks/worker_case.py`

Current benchmark infrastructure includes quick and large-image workloads and machine-readable measurements. Preserve benchmark concepts and build a native V2 benchmark harness that reports stage timings and peak memory.

## Repository-level files

### `AGENTS.md`

Current guidance is V1-scoped and explicitly forbids some features now approved for V2, including Live Preview and drag-and-drop. Replace it on the V2 rewrite branch with V2-compatible agent guidance early in Milestone 1.

### `LICENSE`

MIT. Preserve.

### `ATTRIBUTION.md`

Preserve attribution, including Pixelsort-derived inspiration/source licensing notices.

### `THIRD_PARTY_NOTICES.md`

Update as native/Flutter dependencies are introduced.

### Flatpak/build artifacts

The current repo contains Flatpak manifests/build outputs and Python packaging. They remain during migration only as needed to preserve V1 reference behavior. Milestone 6 removes obsolete V1/Flatpak/Python infrastructure once V2 gates pass.
