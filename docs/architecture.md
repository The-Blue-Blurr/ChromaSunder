# Architecture

ChromaSunder keeps the image engine independent from the desktop shell.

```text
GTK/libadwaita GUI
        |
worker controller and batch state machine
        |
spawned render worker
        |
core models, validation, intervals, sorting, imaging, export
        |
Pillow and Python standard library
```

`PixelSortSettings` contains only processing values. Source, auxiliary-image,
export, and batch paths remain outside that model so `.csunder` files cannot
silently persist user paths. `RenderSnapshot` captures file identity,
settings, and engine version so an older render remains viewable but is never
mistaken for a current one.

The worker writes a lossless full-resolution PNG cache and a display-sized PNG.
The GUI only displays the small preview, while export re-encodes the full
cache without sorting again.

