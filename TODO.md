# Roadmap

This is a to-do list of things I would like to implement to make this app nicer.

## V1.1

- [x] I want the settings to be half the width they currently are
- [ ] I want the Export and Batch Queue to have it's own separate menu.
- [ ] Info bubbles for each parameter
- [x] Make the flatpak name of the app have a space in it

## V1.2

- [ ] Built-in presets
  Mostly involves shipping a small set of read-only `.csunder` files and exposing them in the preset menu.

- [ ] Drag-and-drop image importing
  GTK already supports file drops. The main work is validating dropped files and routing them into either the editor or batch queue.

- [ ] Recent files and recent presets
  Requires storing a short list of paths, removing missing entries, and adding menu items.

- [ ] A small indicator that a mask is currently activated, and a "clear mask" button

- [ ] Give the seed setting a random button

## V1.2

- [ ] Alternative color themes
  Supporting a few controlled themes is straightforward, but requires testing contrast, widget states, icons, dialogs, and accessibility across each theme.

- [ ] Batch thumbnails
  Thumbnail generation is simple, but the app must generate them asynchronously, cache them, avoid excessive memory use, and keep large queues responsive.

- [ ] Custom handmade logo/icon

## V1.3

- [ ] TIFF support
  Basic single-frame TIFF support is easy through Pillow. The difficulty comes from deciding how to handle color modes, high bit depth, alpha, compression types, multipage files, and large memory usage.

- [ ] Additional sorting algorithms
  Simple pixel-value sorting methods are easy to add. Each new algorithm still requires UI integration, preset compatibility, validation, documentation, and golden-image tests.

## V1.4

- [ ] Live preview while adjusting settings
  Requires debounce logic, preview-resolution scaling, job cancellation, stale-result prevention, and careful coordination between rapid UI changes and worker processes.

- [ ] Parallel batch processing
  Requires a managed worker pool, memory-aware concurrency limits, reliable cancellation, progress synchronization, failure isolation, and protection against several large images exhausting system memory.
