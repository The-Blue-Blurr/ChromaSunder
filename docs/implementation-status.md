# ChromaSunder MVP implementation status

## Completed locally

- Repository structure, Python packaging, application metadata, MIT license,
  attribution notices, and project documentation.
- Dependency-free core models, validation, normalization, HSL sorting keys,
  seven interval functions, deterministic seeded randomness, masks, interval
  images, angle rotation, cropping, and row-at-a-time processing.
- Atomic PNG and JPEG export helpers with metadata stripping and worker-based
  full-resolution cache re-encoding.
- Settings-only `.csunder` presets, settings-only history, render snapshots,
  persistence adapter, and stale-render state.
- Spawned worker process with full-resolution cache, display preview, process
  cancellation, cache cleanup, and structured failure messages.
- GTK 4 and libadwaita editor window with dark mode, portals through GTK file
  dialogs, controls, original/rendered toggle, presets, export, keyboard
  shortcuts, drag-and-drop image importing, and a collapsible batch queue.
- Sequential batch runner with shared settings, seed, mask, interval image,
  dimension validation, PNG and preserve-format modes, output conflict
  handling, failure continuation, cancellation, and summary counts.
- Self-hosted Flatpak manifest, `.flatpakref`, GNOME runtime reference, and
  local packaging scripts.
- Pull-request and main-branch CI for lint, formatting, tests, and an x86_64
  Flatpak smoke build using the GNOME 50 runtime.

## Latest local verification

```text
Ruff lint:       passed
Ruff formatting: passed
Pytest:          34 passed
Compileall:      passed
XML metadata:    parsed successfully
YAML manifests:  parsed successfully
GNOME 50 Flatpak: built, installed, and launched successfully
GSettings:       sandboxed read/write passed
Standalone bundle and SHA-256: installed and verified
```

The local Fedora host provides GTK 4.22.4, libadwaita, Flatpak 1.18.0, and
flatpak-builder 1.4.10. Portal services were active during launch testing.

## Remaining release work

The Flatpak smoke workflow has not yet run on GitHub. Signing material, GitHub
Pages publication, and the tagged release workflow are not complete. The
dedicated private signing key must remain outside the repository.

## Incomplete MVP gates

- Worker crash, cache ownership, GUI state, golden image, conflict-policy, and
  auxiliary-image batch coverage remain incomplete.
- Mask and interval-image large benchmarks, accessibility review, and the full
  Fedora manual matrix have not been run. Initial large-image and rotated
  peak-memory measurements are recorded in `docs/performance.md`.
- A dedicated public signing key must be embedded in the Flatpak descriptors;
  GitHub Pages installation and second-version update tests are owner-side
  release gates.
