# Roadmap

This is a to-do list of things I would like to implement to make this app nicer.

## V1.1 - The Simple Update

- [x] I want the settings to be half the width they currently are
- [x] I want the Export and Batch Queue to have it's own separate menu.
- [x] Info bubbles for each parameter
- [x] Make the flatpak name of the app have a space in it
- [x] Add About page

## V1.2 - The Useful Update

- [x] Drag-and-drop image importing
  Dropped files are validated and routed into either the editor or batch queue.

- [x] Recent files and recent presets
  Requires storing a short list of paths, removing missing entries, and adding menu items.

- [x] A small indicator that a mask is currently activated, and a "clear mask" button

- [x] Give the seed setting a random button

- [x] Make settings have a slider where applicable

## V1.3 - The Makeover

- [ ] Move Render Preview and Export buttons to bottom of window

- [ ] Batch thumbnails
  Thumbnail generation is simple, but the app must generate them asynchronously, cache them, avoid excessive memory use, and keep large queues responsive.

- [ ] Custom handmade logo/icon

- [ ] Add icons to Processing and Export buttons

## V1.4 - The Speed Update

- [ ] Figure out how to make rendering faster

## V1.5 - The Lightning Update

- [ ] Live preview while adjusting settings
  Requires debounce logic, preview-resolution scaling, job cancellation, stale-result prevention, and careful coordination between rapid UI changes and worker processes.

- [ ] Parallel batch processing
  Requires a managed worker pool, memory-aware concurrency limits, reliable cancellation, progress synchronization, failure isolation, and protection against several large images exhausting system memory.

## V1.6 - The Mathematical Update

- [ ] Additional sorting algorithms
  Simple pixel-value sorting methods are easy to add. Each new algorithm still requires UI integration, preset compatibility, validation, documentation, and golden-image tests.

- [ ] Built-in presets
  Mostly involves shipping a small set of read-only `.csunder` files and exposing them in the preset menu.
