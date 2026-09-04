# Milestone 4 — Linux Desktop MVP

## Objective

Turn the validated engine/application-state vertical slice into the complete Linux desktop MVP while preserving the current Chroma Sunder workflow and layout.

Primary local target:

```text
Fedora, Linux x86-64
```

Primary release artifact:

```text
ChromaSunder-x86_64.AppImage
```

Windows must remain build/test-clean in CI throughout this milestone, but real Windows UX validation is Milestone 6.

## 1. Preserve the current desktop layout

Do not redesign the editor architecture into a radically different creative application.

Use the V1 `src/chromasunder/gui/main_window.py` as the layout/workflow reference while implementing it idiomatically in Flutter.

### Native window chrome

Use normal desktop/window-manager decorations.

Do not create a frameless/custom title bar containing close/maximize/minimize.

The desktop environment owns:

- window title/chrome
- minimize
- maximize/restore
- close

Inside that native frame, Chroma Sunder owns its application toolbar and content.

## 2. Main application toolbar

Follow the current V1 organization as closely as MVP scope permits.

Required actions/concepts:

- Open
- Presets
- Recent Presets through the Presets menu
- Undo
- Redo
- Help
- About
- Render
- Export

V1's Recent Source Files action is not an MVP requirement; do not add it merely to mirror the old toolbar.

Keep Render/Export in the same general high-prominence/right-side role as the current app.

### Keyboard shortcuts

Preserve unless Flutter/platform conventions force a documented conflict:

- Ctrl+O -> Open
- Ctrl+R -> Render
- Ctrl+E -> Export
- Ctrl+Z -> Undo
- Ctrl+Shift+Z -> Redo
- Escape -> Cancel active cancellable job

Add shortcut tests where practical.

## 3. Main content layout

Use a horizontal desktop split similar to current V1:

```text
┌───────────────────────────────────────────────────────────┐
│ Application toolbar                                       │
├────────────────────────────────────┬──────────────────────┤
│                                    │                      │
│              Preview               │      Controls        │
│                                    │                      │
│                                    │                      │
├────────────────────────────────────┴──────────────────────┤
│ Status / stage / percentage / cancel                      │
└───────────────────────────────────────────────────────────┘
```

Use a resizable divider/pane.

Persist divider position later in this milestone.

Do not force the old exact pixel width (`~1040`) on every display, but use current V1 proportions as the initial/default reference.

## 4. Empty editor state

No dedicated startup/start screen.

On application launch with no document:

- render the normal editor shell
- disable actions that require a document
- preview area contains a clear Open/Drop prompt
- support drag-and-drop source opening

A V1-like message such as "Open an image or drop it here" is appropriate.

Do not automatically reopen the last source.

## 5. Preview area

MVP preview modes:

- Original
- Rendered

No split before/after mode.

No zoom/pan in MVP.

Always fit displayed image into the available preview region while preserving aspect ratio.

The low-resolution processing size is handled by the Milestone 3 preview controller; the widget should not independently invent another image resize policy.

### Original

- display cached display representation of canonical source/proxy
- no sorting job required just to switch to Original

### Rendered

- display newest successful preview/full-render display representation
- loading state must be distinct from absence/error
- if current settings are stale relative to the last full render, do not misrepresent the stale full render as current low-res preview

## 6. Live Preview controls

Expose both:

- Live Preview
- Full Resolution Preview

Required defaults are already in application preferences:

- Live Preview ON
- Full Resolution Preview OFF

Place these controls in a location consistent with current workflow without overcrowding the main toolbar. A compact preview/settings-area placement is acceptable.

Provide clear tooltip/help text explaining:

- Low-res Live Preview adapts to physical preview resolution.
- Full Resolution Preview may be substantially more expensive.
- Render always computes full resolution.

Do not show technical memory math in ordinary UI unless an error occurs.

## 7. Processing controls panel

Preserve current V1 control concepts and grouping.

Use a Processing tab/section with:

- Interval Function
- Sorting Function
- Lower Threshold
- Upper Threshold
- Characteristic Length
- Angle
- Randomness
- Seed
- Mask
- Interval Image

### Interval/sorting selectors

Expose exact user-facing mode names corresponding to current modes:

Intervals:

- Threshold
- Edges
- Random
- Waves
- File
- File Edges
- None

Sorting:

- Lightness
- Hue
- Saturation
- Intensity
- Minimum

### Control sensitivity

Preserve current behavior:

| Interval mode | Lower | Upper | Characteristic Length | Interval Image |
|---|---:|---:|---:|---:|
| Threshold | enabled | enabled | disabled | disabled |
| Edges | enabled | disabled | disabled | disabled |
| Random | disabled | disabled | enabled | disabled |
| Waves | disabled | disabled | enabled | disabled |
| File | disabled | disabled | disabled | enabled |
| File Edges | enabled | disabled | disabled | enabled |
| None | disabled | disabled | disabled | disabled |

Mask remains independently optional.

Disabled controls keep their stored values but do not affect the current mode unless the engine semantics require them.

## 8. Threshold UI

Main UI remains normalized regardless of bit depth.

Display threshold controls in a human-friendly normalized form, e.g. 0–100% or equivalent consistent slider representation.

The engine receives normalized threshold values.

Do not expose 0–65535 raw ranges as the primary control for 16-bit images.

If advanced/debug effective raw values are shown, they must be secondary/nonessential and not complicate MVP implementation.

## 9. Characteristic Length

Display/store it in source-image pixel units.

Low-resolution preview scaling is handled transparently by the preview controller; the control itself must never change from `120` to `18` merely because a proxy is being processed.

Use appropriate numeric validation and input affordances.

## 10. Angle control

Preserve the existing user-facing angle convention:

- 0° right
- 90° up
- 180° left
- 270° down

Recreate a modern angle control/dial only if it remains simple and accessible. Numeric entry plus dial/drag behavior may coexist.

Preserve useful current keyboard semantics where practical:

- normal increment: 1°
- Shift-modified larger increment: 15°

The UI should make clear that V2 angle sorting is direct pixel-path sorting; do not expose or mention legacy image rotation as a processing mode.

## 11. Seed/randomness UX

Randomness:

- normalized percentage 0–100

Seed:

- display an integer value
- allow direct editing
- validate nonnegative V2 seed range

Retain or recreate a "New Variation"-style action associated with presets/settings if current workflow makes it useful. It should generate/update only the seed as one undoable action and schedule Live Preview as normal.

Do not promise V1 seed compatibility.

## 12. Auxiliary Mask UI

Provide:

- Choose Mask
- current mask filename/status
- Remove/Clear Mask

On import:

- native/application layer validates exact canonical source dimensions
- mismatch produces a clear error and leaves current mask unchanged

Do not offer scale/crop/alignment.

Explain minimally in error text that masks are designed for the specific source dimensions.

## 13. Interval Image UI

Provide corresponding:

- Choose Interval Image
- current filename/status
- Remove/Clear Interval Image

File/File Edges control availability should direct the user to choose an interval image when required.

Exact dimensions are mandatory.

## 14. Visual design system

MVP is dark-only.

Create centralized design/theme tokens.

Initial palette direction:

```text
Base background     #0A0A0D
Raised surface      #111116
Primary dark purple #241038
Purple highlight    #3A1758
Cyan accent         #32D7FF
Primary text        #F4F4F6
Secondary text      #A5A5B0
Default border      #24242C
```

These exact hex values may be tuned during implementation for contrast/readability, but preserve the role hierarchy:

- black/near-black is the dominant visual field
- dark purple is the actual primary brand color
- cyan is the major secondary/accent

### Style target

Aim for:

> modern GNOME/libadwaita clarity with a moderate cyberpunk flair

Use cyberpunk influence selectively:

- cyan active indicators/focus
- purple selected/raised areas
- restrained glow around important active/render states
- subtle technical detail
- modern motion

Do not create:

- rainbow/RGB gaming aesthetic
- neon glow on every control
- low-contrast purple-on-black text
- decorative effects that reduce legibility

## 15. Accessibility/usability

Even though the theme is dark-only:

- meet reasonable text/control contrast
- preserve visible keyboard focus
- controls must have semantic labels/tooltips
- do not encode state by color alone
- disabled controls must remain readable as disabled
- progress/cancellation must have accessible text/state

Use compact desktop density inspired by GNOME, but do not make touch-target-size assumptions for Android here; Android adapts later.

## 16. Desktop file Open

Use a system-native/system-integrated file picker where Flutter/platform tooling permits.

MVP supported source filters:

- PNG
- JPEG/JPG

Do not advertise TIFF/WebP yet.

On successful source import:

- replace current document
- clear document Undo/Redo history
- retain application preferences
- create fresh preview according to Live Preview setting

If opening a new source while a native job is active:

- cancel/supersede current document jobs safely before releasing document
- never allow late old-document job completion to update the new document UI

## 17. Desktop drag-and-drop

Drag-and-drop source import is required.

Requirements:

- accept one supported source file dropped onto the app/preview area
- route through the same `openSource` workflow as Open dialog
- do not create a separate decode behavior
- unsupported/multiple files produce a clear bounded error/choice; do not accidentally start batch behavior
- masks/interval images are not inferred from arbitrary drops in MVP unless a deliberately labeled drop target exists; source drop is the required workflow

Add at least one integration/widget test around the drop-handler state path where tooling permits.

## 18. Presets menu/workflow

Required:

- Load Preset
- Save Preset
- Recent Presets
- Clear Recent Presets
- Reset Settings
- New Variation if retained from V1 behavior

Presets remain settings-only.

Applying a preset:

- changes processing settings only
- does not change mask/interval image
- is one Undo action
- triggers Live Preview as appropriate
- marks previous full render stale

## 19. Help/About

About screen/dialog should include:

- Chroma Sunder name/version (`2.0.x`)
- MIT license reference
- existing author/project attribution
- Pixelsort attribution required by current project notices
- link/copyable project information only if it does not create background network activity

It is acceptable for an explicit user-clicked hyperlink to open a browser if product owner considers that ordinary Help/About behavior; do not make the app perform background requests. If strict no-online interpretation is uncertain for hyperlinks, keep links as copyable text rather than fetching them internally.

Help should document:

- modes/controls
- Live Preview vs Full Resolution Preview vs Render
- 16-bit behavior
- mask/interval dimension requirement
- export behavior

## 20. Progress/status area

Preserve the current bottom status/progress concept.

When active job exists, show:

- friendly stage text
- percentage
- Cancel when job is cancellable

Examples:

```text
Preparing image…
Generating paths…
Sorting… 63%
Building preview…
Encoding…
```

Do not fake percentage during indeterminate substeps. If a tiny substep lacks a meaningful percentage, keep prior stage weighting or show stage without misleading micro-progress.

When no job active, use status area for concise document/readiness messages.

## 21. Export controls and workflow

Keep a distinct Export tab/section similar to V1.

### Format options

Required:

- PNG (default)
- JPEG
- Preserve Source Format

If Preserve Source is selected:

- PNG source -> PNG
- JPEG source -> JPEG
- no unsupported codec magically added

### JPEG quality

Expose quality 1–100.

Use current/default UX around approximately 95 unless product state already dictates a different persisted default.

Do not expose JPEG background color picker in MVP. Transparency flattens to black.

### 16-bit format warning

If current render is U16 and export choice is JPEG:

- make the precision reduction explicit in the export flow/status/warning
- do not silently pretend JPEG remains 16-bit

PNG can preserve U16.

## 22. Default export directory

Provide a desktop preference/control allowing the user to select a global default directory.

Store a normal desktop filesystem path.

If it later becomes unavailable:

- show a clear error/fallback to Save As selection
- do not silently write elsewhere

Also expose:

```text
Export Beside Source
```

when the source has a meaningful filesystem parent path.

If source is not filesystem-backed in a future platform scenario, disable/hide this option.

## 23. Automatic output filename

Implement one centralized pure function with exhaustive tests.

### Normal source

```text
example.png
-> example_sorted.png
```

### Existing collision

```text
example_sorted.png exists
-> example_sorted_2.png
-> example_sorted_3.png
```

### Source already ends `_sorted`

If source is:

```text
example_sorted.png
```

Do not generate:

```text
example_sorted_sorted.png
```

Treat stem as already suffixed and use it directly if safe/appropriate or numbering when destination conflicts. Because exporting beside source would conflict with the source itself, the practical beside-source result should become:

```text
example_sorted_2.png
```

rather than overwrite the immutable source without explicit overwrite confirmation.

### General requirements

- preserve Unicode name safely
- support stems with multiple dots
- extension matches selected output format
- collision check continues until unused name
- do not overwrite source automatically
- filename templates/suffix editor are post-MVP

## 24. Stale export dialog

Implement the application-state decision exactly.

When previous full render is stale:

Buttons/actions:

1. **Render Current Settings & Export**
2. **Export Previous Full-Resolution Render**
3. **Cancel**

Do not word choice 2 in a way that implies it contains current preview/settings.

When no full render exists:

- prompt/start current full render for export
- do not show nonexistent "previous" choice

Test all branches.

## 25. Preferences persistence on Linux

Persist practical non-document state through a simple versioned application preferences store.

Use appropriate XDG paths, not hardcoded home subdirectories.

Persist:

- processing settings
- Live Preview preference
- Full Resolution Preview preference
- export mode/format
- JPEG quality
- default export directory
- CPU automatic/cap setting
- window size
- window position where Flutter/window manager makes it reliable
- divider/panel position
- Original/Rendered selection
- other small non-document UI preferences approved by the model

Do not persist/reopen active source document.

Do not require GSettings/GTK schemas in V2.

Use atomic preference writes where practical and recover gracefully from malformed preference files.

## 26. Local rotating logs

Implement local-only logging with appropriate XDG data/state/cache location.

Native and Flutter logs may be separate or unified, but timestamps/job IDs should permit correlation.

Log useful diagnostics:

- app/engine version
- startup environment summary
- import/export failures
- typed native errors
- job stage failure/cancellation
- memory-budget rejection
- relevant dimensions/bit depth/mode names

Do **not** log:

- raw image pixels
- full binary image content
- unnecessary EXIF/GPS metadata
- secret OS paths beyond what is required for debugging; avoid excessive personal path logging

Provide **Open Log Folder** from Help/menu.

Use rotation/size limits so logs cannot grow indefinitely.

## 27. Offline/privacy hardening

Do not add:

- HTTP client behavior
- update checker
- analytics
- crash upload
- account/login
- remote presets

Audit Flutter dependencies for hidden telemetry/network SDKs.

Normal operation must work with no network connection.

## 28. CPU preference UI

Expose an advanced/simple processing preference:

- Automatic (default)
- optional max worker/core cap

Do not make users choose a thread count during normal operation.

The app passes policy to native engine; it does not implement rendering threads in Dart.

## 29. Memory-budget error UX

If native engine rejects a full render for estimated memory:

Display a clear actionable message containing, where useful:

- image dimensions
- bit depth
- estimated memory requirement
- configured/safe available budget

Do not suggest silently reducing output bit depth.

It is acceptable to recommend:

- close other work/retry
- use a device with more memory
- keep using low-res preview

Do not implement tiled fallback in MVP.

## 30. Integration test flows

At minimum implement automated integration tests where Flutter/Linux tooling is reliable, plus a documented manual smoke checklist for UI pieces that cannot be robustly automated.

Required flows from `91_TEST_GATE_MATRIX.md`:

1. launch empty editor
2. Open PNG8
3. drag/drop source
4. Live Preview setting change
5. Full Resolution Preview
6. explicit Render
7. render cancel retaining prior full result
8. mask add/remove
9. interval-image add/remove
10. save/load/Recent Presets
11. Undo/Redo
12. stale Export Previous
13. stale Render Current & Export
14. export PNG/JPEG/default-dir/beside-source

Also manually test PNG16 on Fedora before gate completion.

## 31. AppImage packaging

Primary release artifact:

```text
ChromaSunder-x86_64.AppImage
```

### Build environment

Do not build the only release artifact on a cutting-edge Fedora host and assume broad compatibility.

Set up an AppImage packaging job in a controlled older supported Ubuntu CI/container environment compatible with Flutter Linux build requirements.

Use a maintained AppImage packaging toolchain such as `linuxdeploy`/appropriate Flutter packaging integration, but keep packaging scripts under repository control and review third-party actions/tools.

### Bundle requirements

Ensure the AppImage contains/resolves:

- Flutter Linux application assets
- C++ engine/shared native libraries
- required codec/color libraries not guaranteed on target
- license/third-party notices as appropriate

Do not bundle V1 Python, Pillow, PyGObject, GTK application code, or Flatpak runtime assumptions merely because they existed in V1.

Flutter itself may still depend on normal Linux desktop system libraries; document runtime expectations.

### Test release artifact

On Fedora:

1. download/copy the actual CI-produced AppImage
2. mark executable
3. launch outside build tree
4. complete representative import/render/export workflow
5. verify logs/preferences use expected user dirs
6. verify no dependency on developer absolute paths

Generate SHA-256 checksum.

## 32. Windows CI must stay green

Every significant Flutter/native change in this milestone must continue to run Windows CI:

- native build/tests
- `flutter analyze`
- `flutter test`
- Windows release build

Do not add Linux-only imports into shared Dart code.

Platform-specific desktop file/dialog/drag code must be behind adapters or cross-platform packages that actually support Windows.

## 33. Required documentation

Update/create:

- `docs/v2/UI_DESIGN_SYSTEM.md`
- `docs/v2/LINUX_BUILD.md`
- `docs/v2/EXPORT_BEHAVIOR.md`
- `docs/v2/PREFERENCES.md`
- `docs/v2/LOGGING.md`
- user-facing README for Linux development/run/build

## Hard completion gates

### Functionality

- [ ] All seven interval modes accessible and work through UI.
- [ ] All five sorting modes accessible and work through UI.
- [ ] Direct directional angles work.
- [ ] PNG8, PNG16, JPEG import/export work.
- [ ] ICC-aware import and EXIF orientation work through application.
- [ ] Mask and interval-image workflows enforce exact dimensions.
- [ ] Live Preview defaults ON and works.
- [ ] Low-res preview is viewport/DPR-aware.
- [ ] Full Resolution Preview works and can satisfy export freshness.
- [ ] Render always full resolution.
- [ ] Cancellation preserves previous full result.
- [ ] Stage + percentage displayed.
- [ ] Original/Rendered works.
- [ ] Presets + Recent Presets work.
- [ ] General Undo/Redo works.
- [ ] Drag/drop source works.
- [ ] Default export directory works.
- [ ] Export Beside Source works when eligible.
- [ ] `_sorted` filename/collision rules pass tests.
- [ ] stale-export 3-choice behavior works.

### UI/design

- [ ] Native desktop chrome owns window controls.
- [ ] Current V1 layout/workflow remains recognizable.
- [ ] dark near-black/purple/cyan theme is centralized and readable.
- [ ] no light-theme work added.
- [ ] fit-to-window only; no accidental zoom/pan scope creep.
- [ ] empty editor is normal editor, not separate start page.

### Persistence/privacy

- [ ] practical preferences persist.
- [ ] active source is not reopened automatically.
- [ ] local rotating logs work and Open Log Folder exists.
- [ ] no telemetry/cloud/account/update-check behavior added.

### Quality/release

- [ ] C++ unit/equivalence tests green.
- [ ] FFI tests green.
- [ ] Dart state tests green.
- [ ] Flutter widget tests green.
- [ ] critical Linux integration flows green/documented.
- [ ] Windows CI green.
- [ ] AppImage produced in controlled CI environment.
- [ ] CI-produced AppImage passes real Fedora smoke test.
- [ ] AppImage SHA-256 generated.

## End-of-milestone handoff

Provide:

- screenshots or concise description of final desktop layout/theme
- full automated test command/results
- Linux integration/manual smoke checklist result
- AppImage filename, size, SHA-256, build job
- Fedora validation result
- Windows CI result
- remaining limitations explicitly limited to post-MVP items

If all hard gates pass, immediately proceed to Android Milestone 5 before implementing desktop post-MVP features such as batch, source recents, zoom/pan, TIFF, or themes.
