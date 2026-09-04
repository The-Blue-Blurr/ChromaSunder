# Milestone 5 — Android Full-Parity MVP

## Objective

Bring the completed Linux core MVP to Android immediately, using the same Flutter application architecture and the same C++ engine. Android is **not** a reduced companion app. The milestone is complete only when Android exposes the same core-MVP processing capabilities as Linux.

Target:

```text
Android 13+
minSdk 33
64-bit only
arm64-v8a + x86_64
```

Initial release artifact:

```text
ChromaSunder-Android.apk
```

Direct download only. Do not add Google Play Store/App Bundle/store-listing work.

## 1. Confirm shared-engine parity before Android UI work

Before adding substantial Android UI/platform code:

1. Build the C++ engine for `arm64-v8a` and `x86_64`.
2. Run native tests through an Android-compatible test path where practical.
3. Run selected cross-platform render-hash fixtures using the Android native library.
4. Verify deterministic V2 hashes match Linux for:
   - U8 deterministic sort
   - U16 deterministic sort
   - a V2 RNG case
   - one non-cardinal direct-angle case
   - mask case
   - interval-image case

If hashes differ, investigate the native semantic portability issue before writing platform-specific UI work.

## 2. Android platform architecture

Keep Android-specific functionality outside the C++ engine.

Recommended boundary:

```text
Flutter/Dart app state
        ↓
Typed Android platform adapter
        ↓
Kotlin Android APIs
        ↓
app-private file/URI bridge
        ↓
shared NativeEngine Dart API
        ↓
C++ engine
```

Prefer a typed platform bridge such as Pigeon or another narrow strongly typed channel over a growing set of loosely typed method names.

Use third-party plugins only where they are mature, clearly maintained, and reduce more complexity than they add. Do not add multiple overlapping file/share/storage plugins when a focused Kotlin adapter is clearer.

## 3. Content URI rule — never pass Android URIs to C++

The engine must remain platform-neutral and must not know `content://` URI semantics.

For an incoming Android source/mask/interval/preset content URI:

1. Use `ContentResolver` to open the content.
2. Copy the **original encoded bytes** to an app-private temporary/snapshot file.
3. Preserve a safe extension or provide sniffable metadata so native codec detection works.
4. Close streams reliably.
5. Pass the local app-private snapshot path/file handle supported by the native adapter to C++.

Do **not** decode and re-encode the image in Dart/Kotlin merely to make a local file. That could:

- destroy 16-bit precision
- alter ICC data
- change JPEG content/orientation metadata before the native import pipeline sees it

The snapshot is raw encoded input bytes.

Track lifecycle so app-private snapshots are removed when the document is closed/app cleanup occurs, while native canonical source remains valid for active work.

## 4. Android manifest/platform baseline

Set/verify:

- min SDK 33
- target/compile SDK according to current supported Flutter/Android tooling
- portrait + landscape support
- `arm64-v8a` and `x86_64` native libraries only

Do not intentionally request broad legacy external-storage permissions.

Do not intentionally request `android.permission.INTERNET` for MVP.

At release gate, inspect the **merged manifest** because transitive libraries can inject permissions.

Do not add camera permission/camera capability.

## 5. System document picker source import

Implement a normal Android document-open workflow using Storage Access Framework semantics.

For source images:

- filter/advertise PNG and JPEG MIME types where practical
- allow system providers, not only local filesystem
- copy selected encoded content to app-private snapshot
- route through the exact same document-open state service used by desktop

Opening a new source:

- safely cancels/supersedes old document jobs
- releases old document/native resources after safe cancellation/lifecycle
- clears document history
- leaves application preferences intact

Do not add batch/multiple-file behavior.

## 6. Photo Picker / gallery import

Android 13+ includes the system Photo Picker. Implement photo-library selection for normal source images.

Requirements:

- user can select one source image
- resulting content is snapshotted as original encoded bytes where API permits
- same native import/color/EXIF pipeline runs afterward
- no separate lower-quality "gallery decode" path

Masks/interval images may use the document picker; they do not need photo-gallery shortcuts unless simple to support without ambiguity.

## 7. Open With / ACTION_VIEW integration

Register Chroma Sunder so supported image content can be opened from another Android application/file manager.

Handle:

- incoming intent on cold start
- incoming intent when app already exists

Route through one central incoming-document service.

Do not let a second incoming intent race an existing open/import job. Use document generation IDs and safe replacement semantics.

## 8. Share To / ACTION_SEND import

Allow another app to share one image to Chroma Sunder.

Support expected image MIME types and URI grants.

Route through the same raw-byte snapshot/import path.

If multiple images are sent:

- do not silently create batch behavior
- reject with a clear message or choose one only if explicit UI asks the user; simplest MVP behavior is clear rejection of multi-share

## 9. Auxiliary Mask / Interval Image on Android

Provide the same user capabilities as desktop:

- choose mask
- remove mask
- choose interval image
- remove interval image

Selected auxiliary URI is snapshotted as encoded bytes and passed to native import.

Native/application validation requires exact post-orientation canonical source dimensions.

On mismatch:

- show clear error
- leave previous valid auxiliary selection unchanged
- do not scale/crop

## 10. Responsive mobile layout

Android must support both portrait and landscape from MVP.

Do not duplicate engine/application state between orientations. Rotation rebuilds/reflows widgets while retaining the same document/job state.

### Portrait recommendation

Use a vertically organized editor:

```text
┌───────────────────────────┐
│ Preview                   │
│                           │
├───────────────────────────┤
│ Original | Rendered       │
│ Live / Full-res preview   │
│ Render / Export           │
├───────────────────────────┤
│ Scrollable Processing     │
│ settings                  │
└───────────────────────────┘
```

Exact navigation may use a bottom sheet/tab/expansion layout if it remains clear and keeps every control available.

### Landscape recommendation

Use a desktop-like two-pane composition where screen size allows:

```text
Preview | Settings
```

Do not assume all landscape devices are tablets; use responsive breakpoints based on available logical size, not orientation alone.

## 11. Full feature parity checklist in UI

Android must expose:

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

Settings:

- Lower
- Upper
- Characteristic Length
- Angle
- Randomness
- Seed
- Mask
- Interval Image

Workflow:

- Original / Rendered
- Live Preview
- Full Resolution Preview
- Render
- Cancel
- Export
- Undo/Redo
- Load/Save/Recent Presets
- Reset Settings
- New Variation if retained on desktop

No desktop MVP capability may disappear merely because the screen is small.

## 12. Touch UX

Reuse theme/design language but adjust density/hit targets for touch.

- controls must have comfortable touch targets
- sliders must use the same debounced Live Preview controller
- slider gesture should still coalesce into one Undo step
- angle control must be touch-friendly; numeric entry remains available
- long lists/settings must scroll reliably without fighting sliders
- do not require hover for discoverability

Keep near-black/dark-purple/cyan identity.

No separate light theme.

## 13. Preview behavior must remain identical semantically

Use the shared preview sizing/controller from Milestone 3.

Physical target comes from Flutter logical viewport × device pixel ratio.

Rules remain:

- no processing upscaling beyond source
- simple minimum proxy clamp
- U16 proxy stays U16 through sorting
- spatial settings scale for proxy
- Live Preview defaults ON
- Full Resolution Preview defaults OFF
- obsolete jobs cancelled/superseded

Do not create a hardcoded "mobile preview 720p" path unless measurements later justify a user-approved policy change.

## 14. Android CPU scheduling policy

Use the same native thread pool/engine but feed a more conservative automatic policy.

Consider:

- available processors
- active workload size
- responsiveness
- thermal/battery concerns

Do not use every logical core unconditionally.

The same advanced CPU cap preference must remain available.

Tune only with real Android benchmarks; do not create device-model allowlists.

## 15. Android memory budget policy

Use a more conservative default safe render budget than desktop.

Base it on runtime memory information/platform constraints, not a single fixed universal number.

Before full render:

- native estimator runs
- platform/app provides allowed budget policy
- unsafe operation returns typed memory error

UI should explain that low-res preview can still work even when a full 16-bit render is too large for the device.

Do not silently reduce bit depth/resolution for a requested full render.

## 16. Android Save As

Implement document-create/save workflow through Android system storage.

Recommended flow:

1. Determine export format/name in shared Dart application layer.
2. Native engine exports/encodes the desired result to an app-private temporary file (or streams through a future API; temporary file is simpler for MVP).
3. Android adapter launches/uses system Create Document destination.
4. Copy encoded output bytes from temp file to destination `OutputStream`.
5. Flush/close and verify success.
6. Remove temp file.

Do not pass destination content URI into the C++ codec layer.

If destination copy fails, report failure and keep native completed render intact.

## 17. Default export directory on Android

Support a persistent user-selected directory through the system directory tree picker (`ACTION_OPEN_DOCUMENT_TREE` semantics).

When selected:

- take persistable URI permission using the flags granted by the system
- store the directory URI reference in Android-aware preferences
- verify permission when reusing it
- if permission/provider disappears, prompt user to choose a new default rather than failing silently

### Naming/collision in a document tree

Use shared `_sorted` name generation semantics, but query child names in the selected document tree.

Examples:

```text
example_sorted.png
example_sorted_2.png
example_sorted_3.png
```

If source stem is already `_sorted`, do not append twice.

Create a new document in the tree with correct MIME type and copy the native encoded temp output into it.

Do not assume a filesystem path can be obtained from the directory URI.

## 18. Save to Gallery

Implement gallery output using Android MediaStore/public media APIs appropriate to Android 13+.

Recommended location category:

```text
Pictures/Chroma Sunder
```

or similarly clear product folder.

Set:

- display name using shared naming rules
- correct MIME type
- relative path/category

Write encoded bytes from native temp output.

Ensure incomplete MediaStore entries are cleaned up on failure.

PNG16 should remain encoded PNG16 when saving to gallery if Android MediaStore/provider accepts the file bytes; do not re-decode/re-encode through an Android bitmap.

## 19. Share Export

Allow user to share a completed export directly to another Android app.

Safe flow:

- native encode to app-private/cache file
- expose it with a temporary content URI via FileProvider or equivalent secure Android mechanism
- grant read permission through share intent
- set correct MIME type

Do not expose raw `file://` URIs.

Clean cache exports according to a bounded cleanup policy; do not delete before recipient has a chance to read.

## 20. Export choice UI

Android Export action should offer appropriate options:

- Save to Default Directory (when configured)
- Save As
- Save to Gallery
- Share Export
- Export Beside Source only when the source came from a filesystem/document context where that concept can be safely and meaningfully implemented; it is not required for arbitrary Photo Picker/share URIs

The stale-render three-choice logic occurs **before** destination workflow where applicable.

Do not bypass stale-state logic for Gallery/Share.

## 21. Presets on Android

Presets use the same `.csunder` schema/content as desktop.

Support:

- Load Preset through document picker
- Save Preset through document-create flow or app-managed preset folder with explicit export; choose the simplest cross-platform portable approach
- Recent Presets using durable content URI access where possible

A recent preset whose URI grant/provider is unavailable should be removed/marked unavailable gracefully.

Presets still contain no mask/interval/source/export references.

Round-trip fixtures must prove desktop <-> Android portability at the JSON model level.

## 22. Preferences on Android

Persist the same logical preferences where meaningful:

- processing settings
- Live Preview
- Full Resolution Preview
- export format
- JPEG quality
- default export directory URI
- CPU cap/automatic
- Original/Rendered selection

Desktop-only window geometry/divider positions should remain platform-scoped and should not corrupt Android preferences.

Do not reopen previous source automatically.

## 23. Android local logs

Keep logs local in app-private storage.

Provide an in-app diagnostics action that can:

- show/copy log location conceptually
- share/export log file through explicit Android share/save action if useful

Do not upload automatically.

Use rotating bounded logs.

Do not log raw image content or excessive personal metadata.

Desktop-specific "Open Log Folder" need not map literally to Android; provide the closest useful local diagnostics UX.

## 24. Android privacy audit

At no point add:

- analytics SDK
- Firebase Analytics/Crashlytics unless explicitly requested later (currently prohibited)
- cloud storage
- account/auth SDK
- remote config
- update SDK

Inspect:

- `AndroidManifest.xml`
- merged release manifest
- Gradle dependencies

Ensure no intentional Internet permission exists for MVP.

If a required dependency injects Internet permission even though it is unused, remove/override it where safe and confirm app still functions.

## 25. APK architecture and universal packaging

MVP universal APK contains:

- `arm64-v8a`
- `x86_64`

Do not include 32-bit `armeabi-v7a`.

Do not create split per-ABI public packages yet.

Verify APK contents with appropriate Android build tooling/unzip inspection.

## 26. Signing/secrets

Development/debug signing can use normal Android tooling.

For any public release signing setup:

- never commit keystore
- never commit passwords
- use environment/secret storage in CI
- document backup responsibility

If no permanent release key has been provided/decided, do not invent one and publish irreversible release identity decisions silently. Ask the user before establishing final public signing credentials.

Do not add Play App Signing.

## 27. Android testing matrix

### Automated

- shared Dart model/widget tests
- Android platform adapter unit tests where practical
- native cross-build/tests
- x86_64 emulator integration flows
- orientation/responsive widget tests

### Real device — mandatory before completion

Use Android 13+ ARM64 device.

Test all flows in `91_TEST_GATE_MATRIX.md`, especially:

- document picker
- Photo Picker
- Open With
- Share To
- PNG8
- PNG16
- JPEG
- mask exact dimensions
- interval image exact dimensions
- all modes controls available
- Live Preview
- Full Resolution Preview
- full Render
- cancel retaining prior full result
- Save As
- default export directory persisted across app restart
- Gallery
- Share Export
- portrait
- landscape
- memory-budget failure

## 28. Performance/thermal smoke testing

Do not set a hard seconds target.

Record on at least one representative ARM64 Android device:

- low-res preview dimensions and latency for common source
- full 12–24MP U8 case if device permits
- U16 large case if safe
- worker count selected automatically
- peak/observed memory if measurable
- obvious thermal/throttling behavior during repeated full renders

If Android repeatedly overheats/stalls, tune scheduler policy; do not fork algorithm semantics.

## 29. Universal APK release artifact

Produce direct-download artifact with an unambiguous versioned filename, for example:

```text
ChromaSunder-2.0.x-Android.apk
```

The roadmap's shorthand `ChromaSunder-Android.apk` is acceptable for CI-latest artifacts, but public releases should preferably include version.

Generate SHA-256.

Verify APK installs without Play services/store dependencies.

## 30. Required documentation

Create/update:

- `docs/v2/ANDROID_DEVELOPMENT.md`
- `docs/v2/ANDROID_STORAGE.md`
- `docs/v2/ANDROID_INTENTS.md`
- `docs/v2/ANDROID_RELEASE.md`
- `docs/v2/RESPONSIVE_UI.md`

Document explicit Android 13+/64-bit requirements.

## Hard completion gates

### Native parity

- [ ] Android ARM64 native output hashes match Linux for selected deterministic U8/U16/RNG/angle/mask/interval fixtures.
- [ ] x86_64 emulator native path works.
- [ ] no Android-specific renderer fork exists.

### Import

- [ ] system file picker opens source.
- [ ] Photo Picker opens source.
- [ ] Open With/ACTION_VIEW opens source.
- [ ] Share To/ACTION_SEND opens source.
- [ ] incoming content is copied as original encoded bytes, not bitmap-reencoded.
- [ ] mask/interval import enforces exact dimensions.

### UI parity

- [ ] every Linux core MVP processing mode/control exists on Android.
- [ ] portrait layout complete.
- [ ] landscape layout complete.
- [ ] rotation retains active document/state safely.
- [ ] touch controls usable and slider Undo coalescing works.
- [ ] near-black/purple/cyan visual identity preserved.

### Preview/render

- [ ] Live Preview semantics match desktop.
- [ ] Full Resolution Preview semantics match desktop.
- [ ] U16 proxy remains U16 before display conversion.
- [ ] explicit full Render works.
- [ ] cancellation retains previous full result.
- [ ] stage + percentage displayed.
- [ ] Android CPU policy is adaptive/conservative.
- [ ] memory-budget rejection is graceful.

### Export

- [ ] Save As works.
- [ ] default export directory selection persists permission/reference.
- [ ] default-directory `_sorted` collision naming works.
- [ ] Save to Gallery works.
- [ ] Share Export works using safe content URI.
- [ ] PNG16 export remains PNG16 when applicable.
- [ ] JPEG U16 precision-reduction warning/flow remains correct.
- [ ] stale-render logic applies to all export destinations.

### Presets/preferences/logging/privacy

- [ ] desktop/Android preset portability tests pass.
- [ ] Recent Presets works with Android URI realities.
- [ ] preferences persist without restoring source.
- [ ] local rotating logs work.
- [ ] final merged manifest has no unintended Internet permission.
- [ ] no telemetry/cloud/account/store dependency added.

### Packaging

- [ ] minSdk 33 verified.
- [ ] only intended 64-bit ABIs packaged.
- [ ] universal APK installs on ARM64 Android 13+ device.
- [ ] x86_64 emulator/development path works.
- [ ] direct APK requires no Google Play distribution setup.
- [ ] release signing secrets are not committed.
- [ ] APK SHA-256 generated.

## End-of-milestone handoff

Provide:

- ARM64 real-device model/Android version used for testing
- x86_64 emulator config
- cross-platform render hash comparison results
- all Android import/export integration results
- merged manifest permission audit
- APK filename/size/SHA-256
- Android benchmark/smoke observations
- Windows CI status (must still be green)

After this milestone, do **not** immediately add post-MVP features. Proceed to Milestone 6 for Windows real validation, repository replacement, release hardening, and cleanup.
