# Roadmap

This is a to-do list of things I would like to implement to make this app nicer.

## V1.1 - The Simple Update

- [x] I want the settings to be half the width they currently are
- [x] I want the Export and Batch Queue to have it's own separate menu.
- [x] Info bubbles for each parameter
- [x] Make the flatpak name of the app have a space in it
- [x] Add About page

## V1.2 - The Useful Update

- [ ] Built-in presets
  Mostly involves shipping a small set of read-only `.csunder` files and exposing them in the preset menu.

- [ ] Drag-and-drop image importing
  GTK already supports file drops. The main work is validating dropped files and routing them into either the editor or batch queue.

- [ ] Recent files and recent presets
  Requires storing a short list of paths, removing missing entries, and adding menu items.

- [ ] A small indicator that a mask is currently activated, and a "clear mask" button

- [ ] Give the seed setting a random button

- [ ] Make settings have a slider where applicable

## V1.2 - The Makeover

- [ ] Alternative color themes
  Supporting a few controlled themes is straightforward, but requires testing contrast, widget states, icons, dialogs, and accessibility across each theme.

- [ ] Batch thumbnails
  Thumbnail generation is simple, but the app must generate them asynchronously, cache them, avoid excessive memory use, and keep large queues responsive.

- [ ] Custom handmade logo/icon

- [ ] Add icons to Processing and Export buttons

## V1.3 - The Mathematical Update

- [ ] TIFF support
  Basic single-frame TIFF support is easy through Pillow. The difficulty comes from deciding how to handle color modes, high bit depth, alpha, compression types, multipage files, and large memory usage.

- [ ] Additional sorting algorithms
  Simple pixel-value sorting methods are easy to add. Each new algorithm still requires UI integration, preset compatibility, validation, documentation, and golden-image tests.

## V1.4 - The Speed Update

- [ ] Live preview while adjusting settings
  Requires debounce logic, preview-resolution scaling, job cancellation, stale-result prevention, and careful coordination between rapid UI changes and worker processes.

- [ ] Parallel batch processing
  Requires a managed worker pool, memory-aware concurrency limits, reliable cancellation, progress synchronization, failure isolation, and protection against several large images exhausting system memory.
