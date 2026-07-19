# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project Overview

ChromaSunder is a Fedora-first, GNOME-native graphical pixel sorting tool. It is a Python package with a GTK 4/libadwaita desktop UI, a spawned rendering worker, a Pillow-based image-processing core, tests, and owner-operated Flatpak packaging.

The MVP is intentionally narrow. Do not add speculative features, public processing CLI behavior, telemetry, drag and drop, live preview, project files, recent lists, TIFF support, parallel batch processing, Flathub assumptions, or other out-of-scope features unless the user explicitly asks for them.

## Architecture Rules

Keep the dependency direction intact:

```text
GUI -> worker controller -> core -> Pillow and Python standard library
```

Important boundaries:

- `src/chromasunder/core/` must remain independent of GTK, PyGObject, libadwaita, Flatpak, and GUI concerns.
- `PixelSortSettings` is processing-only state. Do not persist source paths, mask paths, interval-image paths, export paths, or batch paths in `.csunder` presets.
- Render work should stay isolated from GTK in spawned Python worker processes.
- The worker writes full-resolution PNG cache files and display-sized PNG previews. Export should re-encode the full cache when possible rather than sorting again.
- Keep batch processing sequential unless explicitly asked to change that behavior.
- Preserve deterministic seeded behavior for random and wave interval logic.

## Repository Layout

- `src/chromasunder/core/`: image normalization, validation, interval detection, sorting, processing, export helpers, presets, and shared data models.
- `src/chromasunder/worker/`: spawned process protocol, rendering/export worker, lifecycle, cancellation, and cache management.
- `src/chromasunder/gui/`: GTK 4/libadwaita UI, settings/history controllers, dialogs, persistence, and batch UI/state.
- `tests/unit/`: core, preset, history, and batch model tests.
- `tests/integration/`: worker and batch integration tests using temporary files and generated images.
- `tests/performance/`: smoke performance tests.
- `data/`: desktop, AppStream, GSettings schema, and icon metadata.
- `flatpak/`: Flatpak manifest and packaging notes.
- `scripts/`: owner-operated Flatpak build, bundle, and repository publishing helpers.
- `docs/`: architecture, performance, release, and implementation-status documentation.

## Development Setup

Use Python 3.10 or newer. A normal local setup is:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

For GUI launches, the host also needs GTK 4, libadwaita, PyGObject, and Pillow. On non-GTK hosts, focus on core and worker tests.

Run the app with:

```bash
python -m chromasunder
```

The application ID is `io.github.the_blue_blurr.ChromaSunder`.

## Validation Commands

Before finishing behavior changes, run the relevant subset and prefer the full project checks when feasible:

```bash
python -m pytest
ruff check src tests
ruff format --check src tests
```

CI runs the same Python checks on Python 3.10 and 3.12, plus a GNOME 50 x86_64 Flatpak smoke build.

Useful targeted commands:

```bash
python -m pytest tests/unit
python -m pytest tests/integration/test_worker.py
python -m pytest tests/integration/test_batch.py
ruff check src tests
ruff format src tests
```

Only run `ruff format src tests` when formatting changes are intended.

## Coding Conventions

- Follow `pyproject.toml`: Ruff target `py310`, line length `100`, lint rules `E`, `F`, `I`, `B`, and `UP`, with `E501` ignored.
- Follow `.editorconfig`: UTF-8, LF endings, final newline, spaces, 4-space Python indentation, and 2-space Markdown/YAML indentation.
- Prefer small, focused edits. Avoid broad rewrites when a local fix is enough.
- Add tests for behavior changes, especially image processing, persistence, worker lifecycle, export, and batch behavior.
- Use temporary files/directories in tests. Do not depend on user files or host-specific image assets.
- Keep core tests runnable without GTK.
- Preserve atomic export/write behavior and metadata-stripping expectations.
- Clean up Pillow image handles in tests when opening or generating images.
- Avoid adding dependencies unless necessary and documented.

## Packaging And Release Notes

Flatpak distribution is self-hosted through GitHub Pages, not Flathub. The checked-in Flatpak descriptors intentionally do not contain release signing material.

Do not commit private signing keys, generated signing material, or owner-local release secrets. Treat `repo/`, `flatpak-build/`, `.flatpak-builder/`, generated `.flatpak` bundles, and cache directories as build artifacts unless the user explicitly asks otherwise.

Flatpak helpers:

```bash
scripts/build-flatpak.sh
scripts/make-bundle.sh
scripts/publish-repo.sh
```

Use packaging docs in `flatpak/README.md` and `docs/release.md` before changing release behavior.

## Documentation And Attribution

Preserve `ATTRIBUTION.md`, `THIRD_PARTY_NOTICES.md`, license references, and About dialog credits. If changing attribution-relevant code, documentation, packaging, or UI credits, update the relevant files together.

Keep `README.md`, `CONTRIBUTING.md`, `docs/architecture.md`, and `docs/implementation-status.md` consistent with meaningful architecture or workflow changes.

## Agent Workflow

- Inspect the relevant source and tests before editing. Do not assume framework behavior from file names alone.
- Respect uncommitted user changes. Do not revert unrelated files or generated artifacts unless explicitly instructed.
- Keep future-facing claims out of docs unless they are already implemented or clearly marked as remaining work.
- When GUI behavior changes, consider both state-controller behavior and GTK widget state.
- When worker behavior changes, check cancellation, cache cleanup, process completion, error reporting, and export re-encoding paths.
- When core processing changes, verify deterministic seeds, mask behavior, interval-image behavior, angle rotation, crop dimensions, and output modes as applicable.
