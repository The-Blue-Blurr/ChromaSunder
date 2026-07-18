# Contributing

Keep the dependency direction intact:

```text
GUI -> worker controller -> core -> Pillow and the Python standard library
```

The core must never import GTK, PyGObject, libadwaita, or Flatpak modules.
Do not add a public processing CLI or any feature listed as prohibited in the
MVP plan. Add tests with behavior changes and preserve the attribution files.

Before opening a pull request, run:

```bash
python -m pytest
ruff check src tests
ruff format --check src tests
```

Small, focused commits are preferred. Stable releases are created only from
signed tags after the Flatpak and update checks have passed.

