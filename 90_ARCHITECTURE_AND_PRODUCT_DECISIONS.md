# Chroma Sunder V2 — Locked Architecture and Product Decisions

This file summarizes decisions already made with the product owner. Treat them as requirements, not suggestions.

## Platform/order

1. Linux x86-64 desktop MVP first.
2. Android full-parity MVP immediately afterward.
3. Windows remains build/test-clean in CI throughout, then receives hands-on validation and a portable ZIP after Android parity.
4. macOS and iOS are later targets only.

Linux is the only hands-on desktop test environment initially. Primary development machine is Fedora.

Android:

- Android 13+ only
- `minSdk 33`
- 64-bit only
- `arm64-v8a` real-device target
- `x86_64` emulator/development target
- universal APK for MVP

## Distribution

- Linux: AppImage only for MVP.
- Windows: portable ZIP initially; proper installer later.
- Android: direct universal APK.
- No Google Play Store work.
- No other app-store work in MVP.
- No built-in update system in MVP.

## Repository/versioning

- V2 eventually completely replaces the V1 repository implementation.
- No permanent legacy application remains in-tree.
- Keep only a stripped Python reference renderer during migration, then delete it before final replacement.
- V1 remains recoverable through Git tags/history.
- Version numbers are ordinary `2.0.x` values; no alpha/beta/rc suffixes.

## Licensing/dependencies

- Remain MIT licensed and open source.
- Preserve existing attribution.
- Mature dependencies are allowed when genuinely useful; do not go overboard.
- Ask before committing to a large/uncertain dependency.
- Do not add OpenCV by default.

## Core architecture

- Flutter frontend/application shell.
- C++20 native processing engine.
- Stable C ABI between Dart and C++.
- Full-resolution images remain native-side.
- Flutter receives display preview bytes/metadata, not working full-resolution buffers.
- Engine independent from Flutter and testable standalone through CMake.
- CPU renderer for MVP.
- Keep a small render-backend seam for future GPU acceleration.
- One visible processing operation in MVP; engine internally pipeline-ready for multiple stages later.

## Image precision/color

- Process 8-bit images as 8-bit.
- Process 16-bit images as 16-bit.
- Do not silently reduce 16-bit working data to 8-bit.
- UI controls remain normalized where appropriate; engine operates at actual bit depth.
- Internal working color space: defined sRGB.
- Convert non-sRGB ICC sources correctly at import while retaining source bit depth.
- Apply EXIF orientation on import.
- General EXIF/GPS metadata preservation is not required.
- RGBA is one pixel; alpha moves with the pixel.

## Formats

MVP:

- PNG input/output, including 16-bit.
- JPEG input/output; JPEG export is 8-bit.
- JPEG alpha is flattened onto black for MVP.

Architecture must make TIFF/WebP/additional codecs easy later.

## Processing compatibility

Preserve current V1 interval/sorting semantics for MVP unless explicitly changed.

Intentional V2 differences:

- Same seed does not need to reproduce V1/Python output.
- V2 seed must be deterministic within V2 across platforms/worker counts.
- Arbitrary angles use true directional paths, not image rotation; non-cardinal results may differ from V1.

Directional path design must support future bent, curved, and flow-field sorting.

## Masks / interval images

- Exact source dimension match required.
- No scale-to-fit or alignment workflow.
- Masks are image-specific inputs, not reusable preset data.
- MVP masks are binary.
- Weighted/grayscale mask support may be added later; keep the API extensible.
- Presets never contain masks or interval-image references.

## Preview/render behavior

Live Preview:

- Toggleable.
- ON by default.
- Debounced while sliders/controls are actively changing.
- Obsolete preview jobs are cancelled.
- Final control release triggers immediate newest preview.

Low Resolution Preview:

- Default preview mode.
- Resolution derived from physical viewport pixels: logical viewport × device pixel ratio.
- Preserve source aspect ratio.
- Never upscale processing beyond source resolution.
- Use a simple small minimum proxy clamp; approximately 256 pixels on the longest side is acceptable as an initial constant.
- 16-bit source uses a 16-bit proxy; convert only completed display representation to 8-bit.
- Scale pixel-distance/spatial settings such as Characteristic Length to proxy scale.
- Do not scale angle, normalized thresholds, or randomness percentage.

Full Resolution Preview:

- Separate toggle.
- OFF by default.
- If a full-resolution live preview completes successfully, it counts as the current valid full-resolution render.

Render button:

- Always full resolution.
- Successful result is exportable.
- Cancelled result is discarded; previous completed full render remains valid.

Progress:

- Show real stage + percentage.

## Stale export behavior

If settings/aux inputs differ from the last completed full render and user exports, show these choices:

1. Render Current Settings & Export
2. Export Previous Full-Resolution Render
3. Cancel

Do not silently choose for the user.

## Memory/performance

- No hard render-time target yet.
- Correctness first, benchmark second, measured optimization third.
- Adaptive CPU scheduling.
- User may cap CPU usage.
- Desktop can be aggressive; Android defaults should be more conservative.
- Estimate memory before large renders and fail safely if over a device-specific budget.
- No full tiling/out-of-core engine in MVP.
- Buffer/storage abstractions must leave room for mapped/disk-backed storage later.

## Editor/document model

- Source is immutable while open.
- No external file watching/reload workflow in MVP.
- Non-destructive editor.
- One open document in MVP.
- Architecture should permit multiple documents later.
- No project/session files in MVP, but document state should be serializable later.
- General Undo/Redo for render-affecting editor state, not full pixel buffers.
- History includes settings, preset application, mask selection/removal, interval-image selection/removal.

## Presets

- `.csunder` remains the preset extension.
- Processing settings only.
- Never include mask, interval-image, source, or export paths.
- Portable between Linux, Windows, Android.
- Best-effort V1 schema import; do not distort V2 architecture for obsolete behavior.
- Recent Presets is MVP.
- Recent source files are post-MVP.

## Desktop UI

- Preserve the current Chroma Sunder layout/workflow rather than redesigning it.
- Modernized GNOME/libadwaita-inspired feel with moderate cyberpunk flair.
- Near-black main surface.
- Dark purple primary brand color.
- Cyan main secondary/accent.
- Dark-only MVP; alternate schemes much later.
- Desktop environment/window manager owns minimize/maximize/close.
- Chroma Sunder has its own application toolbar below native chrome.
- Preserve current toolbar organization as closely as MVP scope permits.
- Original / Rendered preview toggle only.
- Fit-to-window only for MVP; zoom/pan later.
- Normal editor is shown on startup; no separate start screen.
- Desktop drag-and-drop source import is MVP.

## Export naming/location

- PNG is default export format.
- Option to preserve source format where supported.
- User-selectable global default export directory.
- Also allow Export Beside Source when platform/source permits.
- Automatic suffix: `_sorted`.
- Example: `example.png` -> `example_sorted.png`.
- Collision numbering: `example_sorted_2.png`, `_3`, etc.
- If source stem already ends `_sorted`, do not append another `_sorted`; use numbering as necessary.
- Filename templates later.

## Persistence

Remember practical non-document state, including:

- processing settings
- Live Preview setting
- Full Resolution Preview setting
- export format/default directory
- CPU cap
- window size/position
- panel/divider positions
- Original/Rendered selection

Do not automatically reopen the last source image.

## Android UX/integration

Must have full Linux core-MVP capability parity.

Support portrait and landscape.

Import:

- system file picker
- system Photo Picker/gallery
- Open with Chroma Sunder
- Share to Chroma Sunder

Export:

- Save As
- Save to Gallery
- Share Export
- persistent default export directory

No camera capture.

## Privacy/logging

Permanent product direction:

- no telemetry
- no analytics
- no cloud processing
- no accounts
- no online preset service
- no image upload
- no remote crash reporting

Local rotating logs are required. Desktop should expose Open Log Folder. Do not log raw image data.
