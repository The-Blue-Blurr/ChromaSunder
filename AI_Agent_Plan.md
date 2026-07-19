# ChromaSunder MVP Coding Agent Implementation Plan

## Purpose

This document is the authoritative implementation brief for a coding agent building **ChromaSunder**.

The coding agent must:

1. Implement only the features explicitly included here.
2. Complete phases in order.
3. Stop at each completion gate and verify every requirement.
4. Keep the processing core separate from the GUI.
5. Avoid speculative features, dependencies, platforms, and abstractions.
6. Preserve attribution to the original Pixelsort project and Kim Asendorf.
7. Produce a Fedora-first, GNOME-native Python application distributed through a self-hosted Flatpak repository.

Do not implement anything listed as excluded.

---

# 1. Fixed Decisions

| Item | Required value |
|---|---|
| Application | ChromaSunder |
| Repository | `The-Blue-Blurr/ChromaSunder` |
| Application ID | `io.github.the_blue_blurr.ChromaSunder` |
| Preset extension | `.csunder` |
| License | MIT |
| Primary platform | Fedora Linux with GNOME |
| GUI toolkit | GTK 4 |
| GNOME library | libadwaita |
| Python binding | PyGObject |
| Image library | Pillow |
| Packaging | Self-hosted Flatpak |
| Flathub | Do not submit |
| Theme | Dark mode only |
| Public processing CLI | Do not create |
| Default export | PNG |
| Default suffix | `_pxsorted` |
| Official image formats | PNG and JPEG |
| Batch processing | Required |
| Live preview | Excluded |
| Built-in presets | Excluded |

---

# 2. MVP Product Goal

ChromaSunder is a graphical application for accessing all supported settings of the original Pixelsort tool without repeatedly consulting command-line documentation.

The MVP must support:

- Opening PNG and JPEG images
- Adjusting all inherited Pixelsort parameters
- Loading an external mask
- Loading an external interval image
- Full-resolution, button-triggered rendering
- Cancelling active rendering
- Original/Rendered comparison in one preview
- PNG and JPEG export
- Settings-only `.csunder` presets
- Settings-only undo and redo
- Last-used setting recovery after restart or crash
- Sequential batch processing with one shared settings state
- One shared mask and one shared interval image for a batch
- Output conflict preflight
- Simple batch progress and cancellation
- Installation and updates through a signed, project-controlled Flatpak repository

---

# 3. Strict Scope

## Required single-image features

- Open PNG and JPEG.
- Display a fitted source preview.
- Expose:
  - Interval function
  - Sorting function
  - Lower threshold
  - Upper threshold
  - Characteristic length
  - Angle
  - Randomness
  - Seed
  - Mask image
  - Interval image
- Render at full source resolution when **Render Preview** is pressed.
- Run rendering outside the GTK process.
- Cancel by terminating the worker.
- Display completed rendering.
- Toggle between Original and Rendered.
- Detect stale rendered previews.
- Warn before stale export.
- Export PNG by default.
- Export JPEG when selected.
- Save and load `.csunder` files.
- Undo and redo processing settings.
- Persist last committed settings.

## Required batch features

- Add files through a GTK multiple-file chooser.
- Use a collapsible queue inside the editor window.
- Use one settings snapshot for the queue.
- Use the same seed for every image.
- Allow one shared mask.
- Allow one shared interval image.
- Require identical input dimensions when a shared auxiliary image is active.
- Require the auxiliary image to match those dimensions.
- Use one output folder.
- Convert all outputs to PNG by default.
- Offer preservation of supported source formats.
- Process one image at a time.
- Show current item, total count, progress, completed, skipped, and failed counts.
- Continue after individual failures.
- Cancel immediately.
- Preserve already-completed files.
- Show a final summary.

## Required distribution

- Build an x86_64 Flatpak.
- Host a signed Flatpak repository through GitHub Pages.
- Generate a `.flatpakref`.
- Attach a standalone `.flatpak` bundle to tagged GitHub releases.
- Do not use Flathub.

## Prohibited features

Do not implement:

- Live preview
- Proxy rendering
- Public image-processing CLI
- Drag and drop
- Recent files
- Recent presets
- Built-in presets
- Render history
- Project files
- Mask drawing or editing
- Automatic mask resizing
- Per-image batch settings
- Per-image masks or interval images
- Batch thumbnails
- Queue reordering
- Parallel batch processing
- TIFF
- Animated images
- Multipage images
- Light theme
- Multiple themes
- Heavy cyberpunk restyling
- AppImage
- RPM or COPR
- Flathub submission
- Windows or macOS support
- Telemetry or analytics
- Network services
- Cloud storage
- In-app updating
- Plugin systems
- User accounts
- NumPy without profiling evidence and owner approval

Document out-of-scope ideas separately. Do not implement them.

---

# 4. Architecture

## Dependency direction

```text
GUI
  ↓
Worker controller
  ↓
Core
  ↓
Pillow and Python standard library
```

A worker process imports the core directly.

The core must not import GTK, libadwaita, PyGObject, GUI modules, or Flatpak-specific modules. The GUI must not duplicate processing logic.

## Repository layout

```text
ChromaSunder/
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE
├── ATTRIBUTION.md
├── THIRD_PARTY_NOTICES.md
├── .gitignore
├── .editorconfig
├── src/
│   └── chromasunder/
│       ├── __init__.py
│       ├── __main__.py
│       ├── application.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── enums.py
│       │   ├── models.py
│       │   ├── validation.py
│       │   ├── processing.py
│       │   ├── intervals.py
│       │   ├── sorting.py
│       │   ├── imaging.py
│       │   ├── exporting.py
│       │   └── presets.py
│       ├── worker/
│       │   ├── __init__.py
│       │   ├── protocol.py
│       │   ├── render_worker.py
│       │   └── controller.py
│       ├── gui/
│       │   ├── __init__.py
│       │   ├── main_window.py
│       │   ├── editor_controller.py
│       │   ├── settings_controller.py
│       │   ├── history.py
│       │   ├── preview.py
│       │   ├── dialogs.py
│       │   ├── batch/
│       │   │   ├── __init__.py
│       │   │   ├── model.py
│       │   │   ├── controller.py
│       │   │   └── view.py
│       │   └── widgets/
│       └── resources/
│           ├── ui/
│           └── css/
├── data/
│   ├── io.github.the_blue_blurr.ChromaSunder.desktop
│   ├── io.github.the_blue_blurr.ChromaSunder.metainfo.xml
│   ├── io.github.the_blue_blurr.ChromaSunder.gschema.xml
│   └── icons/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── golden/
│   ├── fixtures/
│   └── performance/
├── flatpak/
│   ├── io.github.the_blue_blurr.ChromaSunder.yml
│   ├── ChromaSunder.flatpakref
│   └── README.md
├── scripts/
└── docs/
```

Use a `src/` layout and `pyproject.toml`.

---

# 5. Core Contracts

## PixelSortSettings

Create one typed, copyable settings model containing only preset-compatible values.

| Field | Type | Default | Validation |
|---|---|---:|---|
| `interval_function` | Enum | `threshold` | Supported value |
| `sorting_function` | Enum | `lightness` | Supported value |
| `lower_threshold` | float | `0.25` | 0.0 through 1.0 |
| `upper_threshold` | float | `0.80` | 0.0 through 1.0 |
| `characteristic_length` | int | `50` | At least 1 |
| `angle` | float | `0.0` | Finite |
| `randomness` | float | `0.0` | 0.0 through 100.0 |
| `seed` | int | Generated | Nonnegative |

Required interval functions:

- `threshold`
- `edges`
- `random`
- `waves`
- `file`
- `file-edges`
- `none`

Required sorting functions:

- `lightness`
- `hue`
- `saturation`
- `intensity`
- `minimum`

Do not put source, mask, interval, export, or batch paths in `PixelSortSettings`.

## RenderSnapshot

Every render request captures:

- Complete settings copy
- Source file identity
- Mask file identity, when present
- Interval-image identity, when present
- Engine version

File identity includes a usable path or selected-file identifier, size, and modification timestamp.

Use snapshot comparison to determine whether a render is current or stale.

---

# 6. Engine Requirements

- Preserve every required interval and sorting function.
- Remove all `PIL.PyAccess` usage.
- Use one dedicated `random.Random(seed)` instance per render.
- Pass that generator through random interval generation and skip decisions.
- Recreate it with the same seed at the start of every batch image.
- Implement mathematically correct sorting calculations.
- Do not copy an incorrect inherited saturation formula.
- Do not use unbounded per-pixel caches.
- Process one row at a time instead of building a full-image Python row list.
- Normalize inputs:
  1. Verify readability.
  2. Apply EXIF orientation.
  3. Reject animated and multipage files.
  4. Convert to RGBA.
  5. Discard metadata.
  6. Record dimensions.
- Officially support PNG and JPEG.
- Treat other readable still formats as experimental and warn.
- Mask semantics:
  - White permits sorting.
  - Black preserves source pixels.
  - Convert to one-bit.
  - Require exact dimensions.
  - Never resize.
- Interval images:
  - Required for `file` and `file-edges`.
  - Convert to one-bit.
  - Require exact dimensions.
  - Do not store in presets.
- Rotation:
  - Accept floating-point degrees.
  - Return original dimensions after inverse rotation and cropping.
  - Estimate expanded size and fail safely when unreasonable.

---

# 7. GUI Requirements

Use:

- `Adw.Application`
- `Adw.ApplicationWindow`
- `Adw.ToolbarView`
- `Adw.HeaderBar`
- `Adw.PreferencesGroup`
- `Adw.ActionRow`
- `Adw.ComboRow`
- `Adw.SpinRow`
- `Adw.Banner`
- `Gtk.ProgressBar`
- `Gtk.Revealer`
- A current GTK 4 image widget
- Current libadwaita alert dialogs

Force dark mode. Avoid extensive custom widget styling.

## Main window

```text
┌────────────────────────────────────────────────────────────┐
│ Open  Presets  Undo  Redo       Render Preview     Export  │
├─────────────────────────────────────┬──────────────────────┤
│                                     │ Processing controls  │
│          Image preview              │ Interval function    │
│                                     │ Sorting function     │
│     Original / Rendered toggle      │ Thresholds           │
│                                     │ Length, angle        │
│                                     │ Randomness, seed     │
│                                     │ Mask, interval image │
├─────────────────────────────────────┴──────────────────────┤
│ ▸ Batch Queue                                      0 files │
├────────────────────────────────────────────────────────────┤
│ Status / progress / cancel                                 │
└────────────────────────────────────────────────────────────┘
```

Actions:

- Open Image
- Load Preset
- Save Preset
- Undo
- Redo
- Render Preview
- Export
- About
- Quit

Shortcuts:

| Action | Shortcut |
|---|---|
| Open | `Ctrl+O` |
| Render | `Ctrl+R` |
| Export | `Ctrl+E` |
| Undo | `Ctrl+Z` |
| Redo | `Ctrl+Shift+Z` |
| Cancel | `Escape` |
| Quit | `Ctrl+Q` |

## Mode-dependent controls

| Mode | Lower | Upper | Length | Interval image |
|---|---:|---:|---:|---:|
| Threshold | Enabled | Enabled | Disabled | Inactive |
| Edges | Enabled | Disabled | Disabled | Inactive |
| Random | Disabled | Disabled | Enabled | Inactive |
| Waves | Disabled | Disabled | Enabled | Inactive |
| File | Disabled | Disabled | Disabled | Required |
| File-edges | Enabled | Disabled | Disabled | Required |
| None | Disabled | Disabled | Disabled | Inactive |

Inactive values remain stored.

Block rendering when validation fails.

---

# 8. Undo and Redo

Undo and redo apply only to `PixelSortSettings`.

Do not include:

- Source image
- Mask selection
- Interval-image selection
- Export choices
- Batch queue
- Saved files

Rules:

- Opening a different source clears both stacks.
- Loading a preset is one action.
- Reset is one action.
- New Variation is one action.
- Use snapshot-based history.
- Limit history to 100 states.
- Coalesce continuous adjustments where practical.
- Update stale-render status after undo and redo.

---

# 9. Worker Process

- Use `multiprocessing` with `spawn`.
- Use a fresh process for each render.
- Pass only serializable paths, settings, IDs, and temporary destinations.
- Do not send Pillow objects through IPC.
- Write:
  - Full-resolution lossless cache render
  - Display-sized preview
  - Small structured metadata result
- Store cache under the XDG cache directory.
- Use PNG for the full-resolution render cache.
- Do not use maximum compression for temporary previews.
- On cancel:
  1. Terminate.
  2. Wait briefly.
  3. Kill if needed.
  4. Dispose of IPC.
  5. Delete partial files.
  6. Return GUI to idle.
- Never reuse IPC after forced termination.
- Clean abandoned cache files on startup without touching another active instance.

---

# 10. Preview and Export State

## Render Preview

1. Validate.
2. Capture immutable snapshot.
3. Disable conflicting actions.
4. Start worker.
5. Show pulsing progress.
6. Show Cancel.
7. Display completed result.
8. Retain full-resolution cache.
9. Mark render current.

Do not show fake single-render percentages.

## Toggle

- One preview area only.
- Original available after source load.
- Rendered disabled until completion.

## Stale render

Keep the older rendering viewable and show a banner.

When Export is selected with stale settings, show:

**The settings have changed since this preview was rendered.**

Choices:

- Render Current Settings and Export
- Export Existing Render
- Cancel

With no render:

- Render and Export
- Cancel

With a current render, proceed directly.

---

# 11. Export

Default output name is source stem plus `_pxsorted`.

## PNG

- Default
- Preserve RGBA
- Maximum lossless compression
- Strip metadata
- Atomic writing

## JPEG

- Quality slider
- Default 95
- Numeric quality display
- Black alpha-compositing background by default
- Custom background color
- Convert composited result to RGB
- Strip metadata
- Atomic writing

When the render is current, re-encode the cached full-resolution image. Do not rerun sorting.

---

# 12. Presets

A `.csunder` file is UTF-8 JSON.

```json
{
  "format": "chromasunder-preset",
  "schema_version": 1,
  "application_version": "1.0.0",
  "settings": {
    "interval_function": "threshold",
    "sorting_function": "lightness",
    "lower_threshold": 0.25,
    "upper_threshold": 0.8,
    "characteristic_length": 50,
    "angle": 0.0,
    "randomness": 0.0,
    "seed": 123456
  }
}
```

Include processing settings only.

Loading must:

- Validate format and schema.
- Validate every required field and enum.
- Reject malformed files without changing current settings.
- Apply a valid preset as one undo action.

Saving must:

- Add `.csunder` if omitted.
- Write atomically.
- Avoid custom MIME registration in MVP.

---

# 13. Persistence

Use `Gio.Settings` with:

`io.github.the_blue_blurr.ChromaSunder`

Persist immediately when committed:

- Last processing settings
- JPEG quality
- JPEG background
- Last output-mode choice
- Window size
- Maximized state
- Batch queue expanded state
- Default output suffix

Do not persist:

- Source path
- Mask path
- Interval-image path
- Output folder
- Queue contents
- Undo or redo history
- Render cache

---

# 14. Batch Processing

## Queue

The queue is collapsible within the editor.

Controls:

- Add Images
- Remove Selected
- Clear Queue
- Choose Output Folder
- Start Batch
- Cancel Batch

No drag and drop, thumbnails, or reordering.

Each item stores or displays:

- Filename
- Width
- Height
- Format
- Proposed output
- Status
- Warning or error

Statuses:

- Pending
- Processing
- Completed
- Skipped
- Failed
- Cancelled

## Fixed snapshot

At start, capture:

- Processing settings
- Seed
- Shared mask
- Shared interval image
- Output folder
- Output mode
- JPEG options
- Suffix
- Conflict policy

Disable editing and queue mutation during processing.

## Dimension rules

Without active auxiliary images, mixed dimensions are allowed.

With shared mask or active interval image:

- Every input must have identical dimensions.
- Auxiliary image must match.
- Validate everything before writing output.
- Never resize.

## Output modes

Default: convert all to PNG.

Optional: preserve supported source format.

- JPEG to JPEG
- PNG to PNG

Experimental inputs cannot be preserved.

## Processing

- Sequential
- Fresh worker per image
- Same seed reinitialized for every image
- Continue after failure
- Keep completed outputs

## Progress

Show:

- Overall bar
- `Processing X of Y`
- Current filename
- Completed, skipped, failed
- Cancel

## Cancellation

- Terminate active worker immediately.
- Mark active and pending items Cancelled.
- Keep completed outputs.
- Delete active partial output.
- Show summary.

---

# 15. Conflict Preflight

Calculate all proposed outputs before starting.

When conflicts exist, show one dialog with:

- Skip Existing
- Overwrite Existing
- Add Numeric Suffix
- Use Different Filename Suffix
- Cancel

Numeric examples:

```text
photo_pxsorted.png
photo_pxsorted_1.png
photo_pxsorted_2.png
```

Custom suffix changes `_pxsorted`, then reruns preflight.

Do not interrupt once per file.

---

# 16. Errors and Logging

Required user-facing error categories:

- Unsupported or corrupt image
- Animated or multipage image
- Mask mismatch
- Interval mismatch
- Missing interval image
- Invalid preset
- Unsupported preset schema
- Invalid destination
- Permission failure
- Worker crash
- Out of memory
- Export failure
- Unexpected internal error

Use expandable technical details where useful.

Logging must include startup, version, render summaries, worker exits, validation failures, export failures, unexpected exceptions, and batch summaries.

Do not log image data. Rotate logs. Store in an XDG-appropriate location. Do not transmit anything.

---

# 17. Attribution and License

Use MIT.

`ATTRIBUTION.md` must state:

- ChromaSunder contains a modernized implementation derived from Satyarth's Pixelsort.
- Pixelsort was MIT licensed.
- ChromaSunder is independently maintained.
- It is not an officially endorsed continuation.
- Kim Asendorf's ASDFPixelSort was foundational inspiration.
- Give prominent thanks to the original author and contributors.

`THIRD_PARTY_NOTICES.md` must include the complete original Pixelsort copyright and MIT notice.

The About dialog must credit:

- ChromaSunder developer
- Satyarth
- Original Pixelsort contributors
- Kim Asendorf

Do not imply endorsement.

---

# 18. Testing

## Core

Test all sorting and interval modes, thresholds, length, randomness, seed, masks, interval images, rotation, cropping, alpha, deterministic output, PNG, JPEG compositing, and metadata stripping.

## Golden images

Use small committed fixtures and fixed seeds. Compare decoded pixels or pixel hashes, not compressed bytes.

## Presets

Test round-trip, missing fields, bad types, invalid enum, future schema, unknown fields, atomic save, failed-load preservation, and one-step undo.

## Workers

Test success, engine exception, crash, cancellation, cleanup, repeated cancellation, startup cleanup, and no IPC reuse.

## Batch

Test PNG, JPEG, mixed queues, both output modes, auxiliary dimensions, conflicts, failure continuation, cancellation, and summary counts.

## GUI state

Test action enablement, control sensitivity, stale state, toggle availability, undo, redo, preset application, batch state, and export warning choices.

## Manual Fedora tests

Verify portals, dark mode, keyboard navigation, scaling, window sizing, 6000×4000 rendering and cancellation, batch processing, crash recovery, Flatpak install, and Flatpak update.

---

# 19. Performance

Requirements:

- GTK never freezes during processing.
- Approximate 6000×4000 images are handled without an uncontrolled crash under reasonable memory.
- Cancellation feels immediate.
- Batch remains sequential.
- Large failures are controlled.
- Peak memory is measured.

Benchmarks:

- 1920×1080
- 3840×2160
- 6000×4000
- 6000×4000 at 45 degrees
- 6000×4000 with mask
- 6000×4000 with file intervals

Optimization order:

1. Profile.
2. Remove allocations.
3. Optimize interval detection.
4. Optimize placement.
5. Consider bounded caches.
6. Request approval before NumPy.

---

# 20. Flatpak and CI

## Flatpak

- Self-hosted
- Signed
- GitHub Pages repository
- `.flatpakref`
- Standalone release bundle
- x86_64 only
- Stable channel only
- Minimal permissions
- No network
- No unrestricted home access
- File portals for selected files and folders

## Pull-request CI

Run:

1. Ruff lint
2. Ruff format check
3. Core tests
4. Golden tests
5. Preset tests
6. Worker tests
7. Batch tests
8. Flatpak smoke build

## Tagged release

1. Verify version consistency.
2. Run all tests.
3. Build and smoke-test Flatpak.
4. Export signed repository.
5. Generate static deltas.
6. Publish GitHub Pages.
7. Build standalone bundle.
8. Generate SHA-256.
9. Create release.
10. Attach bundle, checksum, release notes, and `.flatpakref`.

Do not publish stable releases from untagged commits.

---

# 21. Phase Rules

For every phase:

1. Work only on that phase.
2. Keep the application runnable.
3. Add tests with features.
4. Update documentation.
5. Run relevant tests.
6. Produce a completion report.
7. Do not continue until every gate passes.
8. Fix failed gates immediately.
9. Do not silently defer required work.
10. Obtain owner approval for deviations.

---

# Phase 0: Foundation

## Tasks

- Create repository structure.
- Add `pyproject.toml`, Ruff, Pytest, `.gitignore`, and `.editorconfig`.
- Add MIT license, attribution, third-party notices, README, contributing guide, and changelog.
- Create minimal Adwaita application and window.
- Force dark mode.
- Add desktop entry, AppStream metadata, icon placeholder, and GSettings schema.
- Add basic CI.
- Add About dialog credits.

## Gate 0

- [ ] Development launch works with `python -m chromasunder`.
- [ ] Correct application ID.
- [ ] Dark mode forced.
- [ ] About attribution present.
- [ ] Ruff passes.
- [ ] Pytest passes.
- [ ] CI passes.
- [ ] No processing code added early.
- [ ] No public CLI.

---

# Phase 1: Core Engine

## Tasks

- Models and enums
- Validation
- Image normalization
- Sorting functions
- Interval functions
- Masks and interval images
- Deterministic randomness
- Row-streaming processor
- Rotation and crop
- PNG and JPEG helpers
- Atomic file writing
- Unit, golden, and performance tests

## Gate 1

- [ ] Core has no GTK dependency.
- [ ] Seven interval modes work.
- [ ] Five sorting modes work.
- [ ] Mask and interval semantics work.
- [ ] Same seed is deterministic.
- [ ] Different seeds affect random modes.
- [ ] No obsolete Pillow API.
- [ ] Row-streaming is implemented.
- [ ] PNG and JPEG export helpers work.
- [ ] Animated and multipage files are rejected.
- [ ] Core and golden tests pass.

---

# Phase 2: Single-Image Editor

## Tasks

- Main window
- Open Image
- Original preview
- Processing controls
- Mode sensitivity
- Mask and interval choosers
- Validation feedback
- Editor state
- Render snapshots
- Worker protocol and process
- Cache and cancellation
- Rendered preview
- Original/Rendered toggle
- Stale banner
- Startup cleanup
- Worker and GUI-state tests

## Gate 2

- [ ] PNG and JPEG open.
- [ ] Original preview displays.
- [ ] All controls are available.
- [ ] Sensitivity is correct.
- [ ] Auxiliary dimensions validate.
- [ ] Spawned worker renders.
- [ ] GTK remains responsive.
- [ ] Cancellation cleans partial files.
- [ ] Completed result displays.
- [ ] Toggle works.
- [ ] Stale state works.
- [ ] 6000×4000 manual test completes or fails safely.
- [ ] Tests pass.

---

# Phase 3: Export, Presets, History, Persistence

## Tasks

- Export action and stale dialogs
- PNG default and maximum compression
- JPEG quality and background
- `_pxsorted` naming
- Cache reuse
- `.csunder` schema and I/O
- Undo and redo
- New Variation
- GSettings persistence
- Tests

## Gate 3

- [ ] Current render exports without rerendering.
- [ ] Stale dialog offers all required choices.
- [ ] PNG is default and maximum compression.
- [ ] JPEG defaults to quality 95.
- [ ] JPEG background defaults black and is customizable.
- [ ] Naming is correct.
- [ ] Presets contain settings only.
- [ ] Invalid presets preserve state.
- [ ] Preset load is one undo action.
- [ ] History is settings-only.
- [ ] New source clears history.
- [ ] Settings survive restart.
- [ ] Paths do not survive restart.
- [ ] Tests pass.

---

# Phase 4: Batch Queue

## Tasks

- Collapsible queue
- Multiple-file chooser
- Remove and clear
- Item metadata and status
- Output folder
- Both output modes
- Fixed batch snapshot
- Shared auxiliaries and dimension preflight
- Output paths and conflicts
- Sequential workers
- Progress and cancellation
- Final summary
- Tests

## Gate 4

- [ ] Queue is inside editor.
- [ ] Add Images uses chooser.
- [ ] No drag and drop or thumbnails.
- [ ] One settings snapshot and one seed.
- [ ] Shared mask and interval work when dimensions match.
- [ ] Mismatches block start.
- [ ] Both output modes work.
- [ ] All conflict policies work.
- [ ] Processing is sequential.
- [ ] Failures do not stop later files.
- [ ] Progress and summary are correct.
- [ ] Cancellation is immediate.
- [ ] Completed files remain.
- [ ] Tests pass.

---

# Phase 5: Flatpak Package

## Tasks

- Flatpak manifest and GNOME runtime
- Package app and Pillow dependencies
- Install metadata, icons, and schema
- Minimal permissions
- Portal verification
- Local build docs
- `.flatpakref`
- Standalone bundle workflow
- CI smoke build
- Clean Fedora test

## Gate 5

- [ ] Flatpak builds and launches.
- [ ] Correct application ID.
- [ ] Portal file access works.
- [ ] Selected output folder is writable.
- [ ] No unrestricted home or network permission.
- [ ] GSettings works.
- [ ] Single and batch exports work.
- [ ] CI Flatpak smoke test passes.
- [ ] Standalone bundle installs.

---

# Phase 6: Hosted Repository and Releases

## Tasks

- Dedicated GPG signing key
- Public key committed
- Private key documented and protected
- GitHub secrets
- Signed repository
- Static deltas
- GitHub Pages deployment
- Final `.flatpakref`
- Tagged release workflow
- Bundle and checksum
- Installation test
- Second-version update test

## Gate 6

- [ ] Repository is signed.
- [ ] Private key is not committed.
- [ ] GitHub Pages repository works.
- [ ] `.flatpakref` installs.
- [ ] Bundle installs.
- [ ] Tagged release publishes required artifacts.
- [ ] Checksums publish.
- [ ] Second release updates through `flatpak update`.
- [ ] No Flathub workflow.
- [ ] x86_64 only.

---

# Phase 7: Hardening and 1.0

## Tasks

- Complete automated suite
- Fedora manual matrix
- Performance benchmarks
- Peak-memory measurement
- Error-message review
- Accessibility and keyboard review
- High-DPI check
- Crash-recovery check
- Cache and logging review
- Attribution and license review
- Final documentation and screenshots
- Changelog and release checklist
- Tag and publish 1.0.0

## Gate 7

- [ ] All tests pass.
- [ ] Manual matrix passes.
- [ ] No known data-loss defect.
- [ ] No GUI-blocking render path.
- [ ] Cancellation is reliable.
- [ ] 6000×4000 is acceptably handled.
- [ ] Batch, presets, and exports are stable.
- [ ] Flatpak installation and updating are verified.
- [ ] Attribution and MIT license are complete.
- [ ] No prohibited feature was added.
- [ ] Version 1.0.0 is signed and published.

---

# 22. Final Acceptance Checklist

## Application

- [ ] Launches on Fedora GNOME.
- [ ] GTK 4, libadwaita, dark only.
- [ ] Opens PNG and JPEG.
- [ ] Exposes all processing modes.
- [ ] Supports masks and interval images.
- [ ] Deterministic seed.
- [ ] Worker rendering and cancellation.
- [ ] Original/Rendered toggle.
- [ ] Stale detection and warning.
- [ ] PNG and JPEG export.
- [ ] `.csunder` save and load.
- [ ] Settings-only undo and redo.
- [ ] Last settings restore.

## Batch

- [ ] Collapsible queue.
- [ ] File chooser import.
- [ ] Shared settings and seed.
- [ ] Shared mask and interval.
- [ ] Dimension blocking.
- [ ] PNG default.
- [ ] Preserve-format option.
- [ ] Conflict preflight.
- [ ] Skip, overwrite, numeric suffix, custom suffix.
- [ ] Sequential processing.
- [ ] Failure continuation.
- [ ] Visible progress.
- [ ] Immediate cancellation.
- [ ] Final summary.

## Distribution

- [ ] Self-hosted signed Flatpak.
- [ ] `.flatpakref`.
- [ ] Standalone bundle.
- [ ] GitHub Pages repository.
- [ ] Working updates.
- [ ] No Flathub.

## Scope

- [ ] No CLI.
- [ ] No live preview.
- [ ] No built-in presets.
- [ ] No recent lists.
- [ ] No drag and drop.
- [ ] No mask editor.
- [ ] No thumbnails.
- [ ] No parallel batch.
- [ ] No TIFF.
- [ ] No light mode.
- [ ] No alternate package.
- [ ] No telemetry.

---

# 23. Coding Agent Conduct

1. Do not work beyond the current phase.
2. Do not silently change decisions.
3. Do not add dependencies without documenting necessity.
4. Do not create a public processing CLI.
5. Do not copy obsolete internals without modernization and tests.
6. Do not weaken validation to pass tests.
7. Do not skip cancellation, conflict, or preset tests.
8. Do not claim success without running commands.
9. Do not publish unsigned releases.
10. Do not use Flathub.
11. Do not persist prohibited paths.
12. Do not add network access or analytics.
13. Do not implement excluded features.
14. Keep the main branch buildable.
15. Use small reviewable commits.
16. Document important architecture.
17. Preserve license notices.
18. Stop and report when a gate cannot pass.

---

# 24. Phase Completion Report Template

```markdown
# Phase X Completion Report

## Summary
What was completed.

## Files Created
- path

## Files Modified
- path

## Tests Added
- test

## Commands Run
```bash
command
```

## Results
- Lint:
- Formatting:
- Unit:
- Integration:
- Flatpak:

## Manual Checks
- check

## Completion Gate
- [x] passed
- [ ] unresolved

## Known Limitations
Only limitations explicitly allowed by the MVP.

## Blockers or Owner Decisions
State “None” when there are none.
```

Do not mark a phase complete while any gate item is unresolved.

---

# 25. Definition of Done

ChromaSunder MVP is complete only when:

- Phases 0 through 7 pass.
- The final checklist passes.
- Installation from the signed `.flatpakref` works.
- A signed update works.
- Attribution and MIT requirements are met.
- No prohibited MVP feature exists.
- Version `1.0.0` is published.
