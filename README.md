# ChromaSunder

ChromaSunder is a Fedora-first, GNOME-native graphical pixel sorting tool. It
provides a guided interface for the documented Pixelsort-style interval and
sorting functions, full-resolution worker rendering, masks, interval images,
settings-only presets, and sequential batch processing.

The MVP is intentionally narrow:

- GTK 4 and libadwaita, dark mode only
- PNG and JPEG input and output
- Render work isolated from GTK in a spawned Python process
- PNG output by default, with JPEG export available
- `.csunder` settings presets and settings-only undo/redo
- One shared settings, mask, and interval image state for a batch
- Self-hosted Flatpak distribution, not Flathub

Live preview, drag and drop, recent lists, built-in presets, project files,
parallel batch processing, TIFF, telemetry, and public processing CLI features
are deliberately outside the MVP.

## Development

The core can be exercised without GTK:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
ruff check src tests
```

On Fedora, install GTK 4, libadwaita, PyGObject, and Pillow before launching:

```bash
python -m chromasunder
```

The application ID is `io.github.the_blue_blurr.ChromaSunder`.

## Distribution

The project uses a signed Flatpak repository hosted through GitHub Pages. See
[`flatpak/README.md`](flatpak/README.md) and [`docs/release.md`](docs/release.md)
for the owner-operated release process. Stable releases are tag-driven and do
not use Flathub.

## Attribution

See [`ATTRIBUTION.md`](ATTRIBUTION.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md),
and the About dialog for credit to Satyarth, the original Pixelsort
contributors, and Kim Asendorf's foundational work.

