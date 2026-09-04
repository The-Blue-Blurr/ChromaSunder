# Chroma Sunder V2 Agent Guide

Chroma Sunder V2 replaces the Python/GTK application with a Flutter application backed by
a portable C++20 engine. Read the following before changing the repository:

1. `00_README_AND_AGENT_OPERATING_RULES.md`
2. `90_ARCHITECTURE_AND_PRODUCT_DECISIONS.md`
3. `91_TEST_GATE_MATRIX.md`
4. `92_DEPENDENCY_AND_LICENSE_POLICY.md`
5. `93_CURRENT_V1_REPO_MAP.md`
6. The current numbered milestone file

Execute milestones in order and satisfy every hard gate before beginning the next milestone.
The old V1 prohibitions on Live Preview and desktop drag-and-drop are not authoritative for V2.

## Invariants

- Flutter owns the application shell; C++ owns full-resolution processing.
- Keep full-resolution working and render buffers native-side.
- Processing is local-only. Do not add telemetry, analytics, cloud services, accounts, uploads,
  remote crash reporting, or other network behavior.
- Keep the source image immutable while its document is open.
- Preserve source precision: U8 remains U8 and U16 remains U16.
- Use sRGB working color with ICC-aware import and apply EXIF orientation.
- Move RGBA as one pixel. Require exact canonical dimensions for masks and interval images.
- Use direct directional paths for arbitrary angles, not rotate/sort/rotate-back.
- Keep the engine pipeline-ready and expose a narrow future render-backend seam.
- Keep the standalone CMake engine authoritative and independent of Flutter.
- Keep generated FFI bindings behind a handwritten Dart service.
- Preserve deterministic output and never use `-ffast-math` or portable `-march=native` builds.
- Preserve MIT licensing, `ATTRIBUTION.md`, and `THIRD_PARTY_NOTICES.md`.

## Migration Safety

- V1 source is temporary reference material until the migration gates permit its deletion.
- Never discard unrelated or uncommitted work, rewrite history, or merge V2 to `main` early.
- Do not port pixel sorting before Milestone 1 is complete.
- Add dependencies only when justified and record them in `docs/v2/DEPENDENCIES.md` and notices
  when required. Do not add OpenCV by default.
- Run the smallest relevant tests while iterating and all required gate checks before handoff.
- End each milestone with the implemented work, exact test results, artifacts, limitations,
  PASS/FAIL gate evidence, and next-milestone readiness.
