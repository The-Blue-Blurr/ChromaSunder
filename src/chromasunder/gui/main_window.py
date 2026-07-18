"""The GTK 4 and libadwaita editor window."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

try:
    import gi

    gi.require_version("Adw", "1")
    gi.require_version("Gdk", "4.0")
    gi.require_version("Gio", "2.0")
    gi.require_version("GLib", "2.0")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Adw, Gdk, Gio, GLib, Gtk
except ImportError:  # pragma: no cover - exercised only on non-GTK development hosts
    Adw = Gdk = Gio = GLib = Gtk = None

from chromasunder.core.enums import IntervalFunction, SortingFunction
from chromasunder.core.exporting import save_jpeg, save_png, suggest_output_path
from chromasunder.core.imaging import normalize_image
from chromasunder.core.presets import PresetError, load_preset, save_preset
from chromasunder.core.validation import ValidationError
from chromasunder.gui.batch.controller import BatchRunner
from chromasunder.gui.batch.model import (
    BatchItem,
    BatchSnapshot,
    BatchStatus,
    ConflictPolicy,
    OutputMode,
    assign_proposed_outputs,
    numeric_suffix_path,
    preflight_outputs,
)
from chromasunder.gui.batch.view import build_batch_view
from chromasunder.gui.dialogs import (
    show_conflict_dialog,
    show_error,
    show_no_render_dialog,
    show_stale_export_dialog,
)
from chromasunder.gui.editor_controller import EditorController
from chromasunder.gui.persistence import SettingsStore
from chromasunder.gui.settings_controller import sensitivity_for_mode
from chromasunder.worker.controller import WorkerController, clean_abandoned_cache, new_render_paths

APP_TITLE = "ChromaSunder"


if Adw is not None:

    class MainWindow(Adw.ApplicationWindow):
        def __init__(self, application) -> None:
            super().__init__(application=application, title=APP_TITLE)
            self.set_default_size(1280, 860)
            self.editor = EditorController()
            self.worker = WorkerController()
            self.batch_runner = BatchRunner(WorkerController())
            self.store = SettingsStore()
            self.batch_items: list[BatchItem] = []
            self.batch_output_folder: str | None = None
            self._render_snapshot = None
            self._pending_export: Path | None = None
            self._render_timeout = None
            self._batch_timeout = None
            self._build_ui()
            self._restore_settings()
            self.editor.settings_controller.add_listener(
                lambda _settings: self._on_settings_changed()
            )
            self.connect("close-request", self._on_close_request)
            clean_abandoned_cache()

        def _install_shortcuts(self) -> None:
            actions = {
                "open": (self._open_image, ["<Primary>o"]),
                "render": (self._render, ["<Primary>r"]),
                "export": (self._choose_export_destination, ["<Primary>e"]),
                "undo-settings": (self._undo, ["<Primary>z"]),
                "redo-settings": (self._redo, ["<Primary><Shift>z"]),
                "cancel": (self._cancel_render, ["<Escape>"]),
            }
            for name, (callback, accelerators) in actions.items():
                action = Gio.SimpleAction.new(name, None)
                action.connect("activate", lambda _action, _parameter, fn=callback: fn())
                self.add_action(action)
                self.get_application().set_accels_for_action(f"win.{name}", accelerators)

        def _build_ui(self) -> None:
            self._install_shortcuts()
            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            toolbar.add_top_bar(header)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            toolbar.set_content(content)
            self.set_content(toolbar)

            open_button = Gtk.Button(label="Open")
            open_button.connect("clicked", lambda _button: self._open_image())
            header.pack_start(open_button)
            presets_button = Gtk.MenuButton(label="Presets")
            presets_button.set_menu_model(self._preset_menu())
            header.pack_start(presets_button)

            self.undo_button = Gtk.Button(label="Undo")
            self.undo_button.connect("clicked", lambda _button: self._undo())
            self.redo_button = Gtk.Button(label="Redo")
            self.redo_button.connect("clicked", lambda _button: self._redo())
            header.pack_start(self.undo_button)
            header.pack_start(self.redo_button)

            self.render_button = Gtk.Button(label="Render Preview")
            self.render_button.add_css_class("suggested-action")
            self.render_button.connect("clicked", lambda _button: self._render())
            header.pack_end(self.render_button)
            self.export_button = Gtk.Button(label="Export")
            self.export_button.connect("clicked", lambda _button: self._choose_export_destination())
            header.pack_end(self.export_button)

            paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
            paned.set_position(850)
            self.stale_banner = Adw.Banner()
            self.stale_banner.set_revealed(False)
            content.append(self.stale_banner)
            content.append(paned)
            paned.set_start_child(self._build_preview_panel())
            paned.set_end_child(self._build_controls_panel())

            self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.status_box.set_margin_top(8)
            self.status_box.set_margin_bottom(8)
            self.status_box.set_margin_start(12)
            self.status_box.set_margin_end(12)
            self.status_label = Gtk.Label(label="Open an image to begin.", xalign=0)
            self.status_label.set_hexpand(True)
            self.progress = Gtk.ProgressBar()
            self.progress.set_visible(False)
            self.cancel_button = Gtk.Button(label="Cancel")
            self.cancel_button.set_visible(False)
            self.cancel_button.connect("clicked", lambda _button: self._cancel_render())
            self.status_box.append(self.status_label)
            self.status_box.append(self.progress)
            self.status_box.append(self.cancel_button)
            content.append(self.status_box)

        def _preset_menu(self):
            menu = Gio.Menu()
            menu.append("Load Preset", "win.load-preset")
            menu.append("Save Preset", "win.save-preset")
            menu.append("Reset Settings", "win.reset-settings")
            menu.append("New Variation", "win.new-variation")
            menu.append("About", "app.about")
            for name, callback in (
                ("load-preset", self._load_preset),
                ("save-preset", self._save_preset),
                ("reset-settings", self._reset_settings),
                ("new-variation", self._new_variation),
            ):
                action = Gio.SimpleAction.new(name, None)
                action.connect("activate", lambda _action, _parameter, fn=callback: fn())
                self.add_action(action)
            return menu

        def _build_preview_panel(self):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_margin_top(12)
            box.set_margin_bottom(12)
            box.set_margin_start(12)
            box.set_margin_end(12)
            self.preview_stack = Gtk.Stack()
            self.preview_stack.set_hexpand(True)
            self.preview_stack.set_vexpand(True)
            self.preview_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            empty = Gtk.Label(label="Open a PNG or JPEG image", xalign=0.5, yalign=0.5)
            self.preview_stack.add_named(empty, "empty")
            self.original_picture = Gtk.Picture()
            self.original_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            self.rendered_picture = Gtk.Picture()
            self.rendered_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            self.preview_stack.add_named(self.original_picture, "original")
            self.preview_stack.add_named(self.rendered_picture, "rendered")
            self.preview_stack.set_visible_child_name("empty")
            box.append(self.preview_stack)

            toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            self.original_toggle = Gtk.ToggleButton(label="Original")
            self.rendered_toggle = Gtk.ToggleButton(label="Rendered")
            self.rendered_toggle.set_group(self.original_toggle)
            self.original_toggle.set_active(True)
            self.original_toggle.connect("toggled", self._toggle_preview)
            self.rendered_toggle.connect("toggled", self._toggle_preview)
            self.rendered_toggle.set_sensitive(False)
            toggle_box.append(self.original_toggle)
            toggle_box.append(self.rendered_toggle)
            box.append(toggle_box)
            return box

        def _build_controls_panel(self):
            scroller = Gtk.ScrolledWindow()
            scroller.set_min_content_width(360)
            controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            controls.set_margin_top(12)
            controls.set_margin_bottom(12)
            controls.set_margin_start(12)
            controls.set_margin_end(12)
            scroller.set_child(controls)

            processing = Adw.PreferencesGroup(title="Processing")
            controls.append(processing)
            self.interval_row = self._combo_row(
                "Interval function", list(IntervalFunction), self._interval_changed
            )
            self.sorting_row = self._combo_row(
                "Sorting function", list(SortingFunction), self._sorting_changed
            )
            processing.add(self.interval_row)
            processing.add(self.sorting_row)
            self.lower_row = self._spin_row("Lower threshold", 0.0, 1.0, 0.01, 2)
            self.upper_row = self._spin_row("Upper threshold", 0.0, 1.0, 0.01, 2)
            self.length_row = self._spin_row("Characteristic length", 1, 10000, 1, 0)
            self.angle_row = self._spin_row("Angle", -360, 360, 1, 2)
            self.randomness_row = self._spin_row("Randomness", 0, 100, 1, 1)
            self.seed_row = self._spin_row("Seed", 0, 2**31 - 1, 1, 0)
            for row in (
                self.lower_row,
                self.upper_row,
                self.length_row,
                self.angle_row,
                self.randomness_row,
                self.seed_row,
            ):
                processing.add(row)
                row.connect("notify::value", self._numeric_changed)

            auxiliary = Adw.PreferencesGroup(title="Auxiliary Images")
            controls.append(auxiliary)
            self.mask_row = self._file_row("Mask image", self._choose_mask)
            self.interval_image_row = self._file_row("Interval image", self._choose_interval_image)
            auxiliary.add(self.mask_row)
            auxiliary.add(self.interval_image_row)

            export_group = Adw.PreferencesGroup(title="Export")
            controls.append(export_group)
            self.jpeg_quality_row = self._spin_row("JPEG quality", 1, 100, 1, 0)
            self.jpeg_quality_row.set_value(95)
            self.jpeg_quality_row.connect("notify::value", self._jpeg_quality_changed)
            self.jpeg_background_row = Adw.EntryRow(title="JPEG background")
            self.jpeg_background_row.set_text("black")
            self.suffix_row = Adw.EntryRow(title="Default output suffix")
            self.suffix_row.set_text("_pxsorted")
            export_group.add(self.jpeg_quality_row)
            export_group.add(self.jpeg_background_row)
            export_group.add(self.suffix_row)

            self.batch_output_mode_row = self._combo_row(
                "Batch output mode", list(OutputMode), self._batch_output_mode_changed
            )
            controls.append(self.batch_output_mode_row)

            batch_group, self.batch_list, self.batch_toggle = build_batch_view(
                Gtk,
                Adw,
                self.batch_items,
                {
                    "add": self._add_batch_images,
                    "remove": self._remove_batch_image,
                    "clear": self._clear_batch,
                    "folder": self._choose_batch_folder,
                    "start": self._start_batch,
                    "cancel": self._cancel_batch,
                },
            )
            controls.append(batch_group)
            return scroller

        def _combo_row(self, title, values, callback):
            row = Adw.ComboRow(title=title)
            row.set_model(Gtk.StringList.new([str(value) for value in values]))
            row.connect("notify::selected", callback)
            row._chromasunder_values = values
            return row

        def _spin_row(self, title, lower, upper, step, digits):
            adjustment = Gtk.Adjustment(
                value=lower, lower=lower, upper=upper, step_increment=step, page_increment=step * 10
            )
            row = Adw.SpinRow.new(adjustment, title)
            row.set_digits(digits)
            row._chromasunder_syncing = False
            return row

        def _file_row(self, title, callback):
            row = Adw.ActionRow(title=title, subtitle="None selected")
            button = Gtk.Button(label="Choose")
            button.set_valign(Gtk.Align.CENTER)
            button.connect("clicked", lambda _button: callback(row))
            row.add_suffix(button)
            row._chromasunder_button = button
            return row

        def _on_settings_changed(self) -> None:
            if not hasattr(self, "interval_row"):
                return
            settings = self.editor.settings
            self.interval_row.set_selected(list(IntervalFunction).index(settings.interval_function))
            self.sorting_row.set_selected(list(SortingFunction).index(settings.sorting_function))
            for row, value in (
                (self.lower_row, settings.lower_threshold),
                (self.upper_row, settings.upper_threshold),
                (self.length_row, settings.characteristic_length),
                (self.angle_row, settings.angle),
                (self.randomness_row, settings.randomness),
                (self.seed_row, settings.seed),
            ):
                row._chromasunder_syncing = True
                row.set_value(value)
                row._chromasunder_syncing = False
            sensitivity = sensitivity_for_mode(settings.interval_function)
            self.lower_row.set_sensitive(sensitivity.lower)
            self.upper_row.set_sensitive(sensitivity.upper)
            self.length_row.set_sensitive(sensitivity.length)
            self.interval_image_row.set_sensitive(sensitivity.interval_image)
            self.undo_button.set_sensitive(self.editor.settings_controller.history.can_undo)
            self.redo_button.set_sensitive(self.editor.settings_controller.history.can_redo)
            self._set_stale_banner()

        def _interval_changed(self, row, _pspec) -> None:
            values = list(IntervalFunction)
            self.editor.update_settings(interval_function=values[row.get_selected()])

        def _sorting_changed(self, row, _pspec) -> None:
            values = list(SortingFunction)
            self.editor.update_settings(sorting_function=values[row.get_selected()])

        def _numeric_changed(self, row, _pspec) -> None:
            if getattr(row, "_chromasunder_syncing", False):
                return
            values = {
                self.lower_row: "lower_threshold",
                self.upper_row: "upper_threshold",
                self.length_row: "characteristic_length",
                self.angle_row: "angle",
                self.randomness_row: "randomness",
                self.seed_row: "seed",
            }
            name = values.get(row)
            if name:
                try:
                    value = row.get_value()
                    if name in {"characteristic_length", "seed"}:
                        value = int(value)
                    self.editor.update_settings(**{name: value})
                except ValidationError as exc:
                    self.status_label.set_text(str(exc))

        def _toggle_preview(self, button) -> None:
            if button is self.original_toggle and button.get_active():
                self.preview_stack.set_visible_child_name("original")
            elif button is self.rendered_toggle and button.get_active() and self.editor.has_render:
                self.preview_stack.set_visible_child_name("rendered")

        def _open_image(self) -> None:
            self._open_dialog("Open Image", False, self._finish_open_image, image_filter=True)

        def _finish_open_image(self, dialog, result) -> None:
            try:
                file = dialog.open_finish(result)
                if file is None:
                    return
                self.editor.open_source(file.get_path())
                self._show_source(file.get_path())
                self._clear_rendered_view()
                self.status_label.set_text(Path(file.get_path()).name)
            except GLib.Error as exc:
                if not exc.matches(Gtk.DialogError.quark(), Gtk.DialogError.DISMISSED):
                    show_error(Adw, self, "Unable to open image", str(exc))
            except (ValidationError, OSError) as exc:
                show_error(Adw, self, "Unable to open image", str(exc))

        def _show_source(self, path: str) -> None:
            self.original_picture.set_filename(path)
            self.preview_stack.set_visible_child_name("original")
            self.original_toggle.set_active(True)
            self._on_settings_changed()

        def _clear_rendered_view(self) -> None:
            self.editor.clear_render()
            self.rendered_toggle.set_sensitive(False)
            self.rendered_toggle.set_active(False)
            self.original_toggle.set_active(True)
            self._set_stale_banner()

        def _choose_mask(self, row) -> None:
            self._open_dialog(
                "Choose Mask Image",
                False,
                lambda dialog, result: self._finish_mask(dialog, result, row),
                image_filter=True,
            )

        def _finish_mask(self, dialog, result, row) -> None:
            try:
                file = dialog.open_finish(result)
                if file:
                    path = file.get_path()
                    self.editor.set_mask(path)
                    row.set_subtitle(Path(path).name)
                    self._set_stale_banner()
            except GLib.Error:
                return

        def _choose_interval_image(self, row) -> None:
            self._open_dialog(
                "Choose Interval Image",
                False,
                lambda dialog, result: self._finish_interval(dialog, result, row),
                image_filter=True,
            )

        def _finish_interval(self, dialog, result, row) -> None:
            try:
                file = dialog.open_finish(result)
                if file:
                    path = file.get_path()
                    self.editor.set_interval_image(path)
                    row.set_subtitle(Path(path).name)
                    self._set_stale_banner()
            except GLib.Error:
                return

        def _render(self, export_after: Path | None = None) -> None:
            if self.worker.active:
                return
            try:
                snapshot = self.editor.snapshot()
                cache_path, preview_path = new_render_paths()
                request = {
                    "source_path": self.editor.state.source_path,
                    "settings": snapshot.settings.to_dict(),
                    "mask_path": self.editor.state.mask_path,
                    "interval_path": self.editor.state.interval_path,
                    "cache_path": str(cache_path),
                    "preview_path": str(preview_path),
                }
                self._render_snapshot = snapshot
                self._pending_export = export_after
                self.worker.start(request)
                self.render_button.set_sensitive(False)
                self.export_button.set_sensitive(False)
                self.progress.set_visible(True)
                self.progress.pulse()
                self.cancel_button.set_visible(True)
                self.status_label.set_text("Rendering full-resolution image...")
                self._render_timeout = GLib.timeout_add(50, self._poll_render)
            except (ValidationError, OSError) as exc:
                show_error(Adw, self, "Unable to render", str(exc))

        def _poll_render(self) -> bool:
            messages = self.worker.poll()
            self.progress.pulse()
            for message in messages:
                kind = message.get("kind")
                payload = message.get("payload", {})
                if kind == "complete":
                    self.editor.mark_rendered(
                        self._render_snapshot,
                        payload["cache_path"],
                        payload["preview_path"],
                    )
                    self.rendered_picture.set_filename(payload["preview_path"])
                    self.rendered_toggle.set_sensitive(True)
                    self.rendered_toggle.set_active(True)
                    self.preview_stack.set_visible_child_name("rendered")
                    export_after = self._pending_export
                    self._finish_render_ui("Render complete")
                    if export_after:
                        self._export_render(export_after)
                    return False
                if kind == "error":
                    self._finish_render_ui("Render failed")
                    show_error(
                        Adw,
                        self,
                        "Render failed",
                        payload.get("message", "The worker failed."),
                        payload.get("details"),
                    )
                    return False
                if kind == "cancelled":
                    self._finish_render_ui("Render cancelled")
                    return False
            process = self.worker.process
            if process is not None and not process.is_alive():
                self._finish_render_ui("Render worker exited unexpectedly")
                show_error(Adw, self, "Render failed", "The render worker exited unexpectedly.")
                return False
            return True

        def _finish_render_ui(self, message: str) -> None:
            self.worker.close()
            self.render_button.set_sensitive(True)
            self.export_button.set_sensitive(True)
            self.progress.set_visible(False)
            self.cancel_button.set_visible(False)
            self.status_label.set_text(message)
            self._set_stale_banner()

        def _cancel_render(self) -> None:
            if self.worker.active:
                self.worker.cancel()
                self._finish_render_ui("Render cancelled")

        def _set_stale_banner(self) -> None:
            if not self.editor.has_render:
                self.stale_banner.set_revealed(False)
                return
            if self.editor.rendered_is_current():
                self.stale_banner.set_revealed(False)
                self.status_label.set_text("Rendered preview is current.")
            else:
                self.stale_banner.set_title(
                    "The settings have changed since this preview was rendered."
                )
                self.stale_banner.set_revealed(True)
                self.status_label.set_text(
                    "The rendered preview is stale because settings or source selections changed."
                )

        def _jpeg_quality_changed(self, row, _pspec) -> None:
            if not getattr(row, "_chromasunder_syncing", False):
                self.jpeg_quality = int(row.get_value())

        def _batch_output_mode_changed(self, _row, _pspec) -> None:
            return

        def _choose_export_destination(self) -> None:
            if not self.editor.has_source:
                show_error(Adw, self, "Nothing to export", "Open an image first.")
                return
            default = suggest_output_path(self.editor.state.source_path, output_format="PNG")
            self._save_dialog("Export Image", default.name, self._finish_export_destination)

        def _finish_export_destination(self, dialog, result) -> None:
            try:
                file = dialog.save_finish(result)
                if file is None:
                    return
                destination = Path(file.get_path())
                if not destination.suffix:
                    destination = destination.with_suffix(".png")
                if not self.editor.has_render:
                    self._pending_export = destination
                    show_no_render_dialog(Adw, self, self._export_choice)
                elif not self.editor.rendered_is_current():
                    self._pending_export = destination
                    show_stale_export_dialog(Adw, self, self._export_choice)
                else:
                    self._export_render(destination)
            except GLib.Error:
                return

        def _export_choice(self, choice: str) -> None:
            destination = self._pending_export
            if choice == "render" and destination:
                self._render(destination)
            elif choice == "existing" and destination:
                self._export_render(destination)
            else:
                self._pending_export = None

        def _export_render(self, destination: Path) -> None:
            if not self.editor.state.cache_path:
                return
            try:
                with __import__("PIL.Image", fromlist=["Image"]).open(
                    self.editor.state.cache_path
                ) as image:
                    if destination.suffix.lower() in {".jpg", ".jpeg"}:
                        save_jpeg(
                            image,
                            destination,
                            quality=getattr(self, "jpeg_quality", 95),
                            background=self.jpeg_background_row.get_text() or "black",
                        )
                    else:
                        save_png(image, destination)
                self.status_label.set_text(f"Exported {destination.name}")
            except (OSError, ValidationError) as exc:
                show_error(Adw, self, "Export failed", str(exc))
            finally:
                self._pending_export = None

        def _undo(self) -> None:
            self.editor.settings_controller.undo()
            self._on_settings_changed()

        def _redo(self) -> None:
            self.editor.settings_controller.redo()
            self._on_settings_changed()

        def _load_preset(self) -> None:
            self._open_dialog("Load Preset", False, self._finish_load_preset, preset_filter=True)

        def _finish_load_preset(self, dialog, result) -> None:
            try:
                file = dialog.open_finish(result)
                if file:
                    settings = load_preset(file.get_path())
                    self.editor.settings_controller.apply_preset(settings)
                    self._on_settings_changed()
            except (GLib.Error, PresetError) as exc:
                if isinstance(exc, PresetError):
                    show_error(Adw, self, "Invalid preset", str(exc))

        def _save_preset(self) -> None:
            self._save_dialog("Save Preset", "settings.csunder", self._finish_save_preset)

        def _finish_save_preset(self, dialog, result) -> None:
            try:
                file = dialog.save_finish(result)
                if file:
                    save_preset(file.get_path(), self.editor.settings)
                    self.status_label.set_text("Preset saved.")
            except (GLib.Error, PresetError) as exc:
                if isinstance(exc, PresetError):
                    show_error(Adw, self, "Unable to save preset", str(exc))

        def _reset_settings(self) -> None:
            self.editor.settings_controller.reset()
            self._on_settings_changed()

        def _new_variation(self) -> None:
            self.editor.settings_controller.new_variation()
            self._on_settings_changed()

        def _add_batch_images(self) -> None:
            self._open_dialog("Add Images", True, self._finish_add_batch, image_filter=True)

        def _finish_add_batch(self, dialog, result) -> None:
            try:
                files = dialog.open_multiple_finish(result)
                for index in range(files.get_n_items()):
                    file = files.get_item(index)
                    try:
                        item = BatchItem(file.get_path())
                        normalized = normalize_image(file.get_path())
                        item.dimensions = normalized.dimensions
                        item.source_format = normalized.format
                        normalized.image.close()
                        self.batch_items.append(item)
                    except (ValidationError, OSError) as exc:
                        show_error(Adw, self, "Unable to add image", str(exc))
                self._refresh_batch_list()
            except GLib.Error:
                return

        def _refresh_batch_list(self) -> None:
            while (child := self.batch_list.get_first_child()) is not None:
                self.batch_list.remove(child)
            for item in self.batch_items:
                row = Gtk.ListBoxRow()
                row.set_child(
                    Gtk.Label(label=f"{Path(item.source_path).name}  |  {item.status}", xalign=0)
                )
                self.batch_list.append(row)
            self.batch_toggle.set_label(f"Batch Queue ({len(self.batch_items)} files)")

        def _remove_batch_image(self) -> None:
            row = self.batch_list.get_selected_row()
            if row is not None:
                index = row.get_index()
                if 0 <= index < len(self.batch_items):
                    self.batch_items.pop(index)
                    self._refresh_batch_list()

        def _clear_batch(self) -> None:
            self.batch_items.clear()
            self._refresh_batch_list()

        def _choose_batch_folder(self) -> None:
            self._folder_dialog("Choose Output Folder", self._finish_batch_folder)

        def _finish_batch_folder(self, dialog, result) -> None:
            try:
                file = dialog.select_folder_finish(result)
                if file:
                    self.batch_output_folder = file.get_path()
                    self.status_label.set_text(f"Batch output folder: {self.batch_output_folder}")
            except GLib.Error:
                return

        def _start_batch(self) -> None:
            if not self.batch_items or not self.batch_output_folder:
                show_error(
                    Adw, self, "Batch is not ready", "Add images and choose an output folder first."
                )
                return
            snapshot = BatchSnapshot(
                settings=self.editor.settings,
                output_folder=self.batch_output_folder,
                output_mode=list(OutputMode)[self.batch_output_mode_row.get_selected()],
                mask_path=self.editor.state.mask_path,
                interval_path=self.editor.state.interval_path,
                jpeg_quality=getattr(self, "jpeg_quality", 95),
                jpeg_background=self.jpeg_background_row.get_text() or "black",
                suffix=self.suffix_row.get_text() or "_pxsorted",
            )
            conflicts = preflight_outputs(self.batch_items, snapshot)
            if conflicts.has_conflicts:
                show_conflict_dialog(
                    Adw, self, lambda choice: self._apply_conflict_choice(choice, snapshot)
                )
                return
            self._run_batch(snapshot)

        def _apply_conflict_choice(self, choice: str, snapshot: BatchSnapshot) -> None:
            if choice == "cancel":
                return
            if choice == "skip":
                for item in self.batch_items:
                    if item.proposed_output and Path(item.proposed_output).exists():
                        item.status = BatchStatus.SKIPPED
                snapshot = replace(snapshot, conflict_policy=ConflictPolicy.SKIP)
            elif choice == "numeric":
                used = set()
                for item in self.batch_items:
                    path = Path(item.proposed_output or "")
                    chosen = numeric_suffix_path(path, used)
                    item.proposed_output = str(chosen)
                    used.add(chosen)
                snapshot = replace(snapshot, conflict_policy=ConflictPolicy.NUMERIC_SUFFIX)
            elif choice == "overwrite":
                snapshot = replace(snapshot, conflict_policy=ConflictPolicy.OVERWRITE)
            elif choice == "suffix":
                suffix = self.suffix_row.get_text().strip() or "_pxsorted"
                if suffix == snapshot.suffix:
                    suffix = f"{suffix}_batch"
                snapshot = replace(snapshot, suffix=suffix)
                assign_proposed_outputs(self.batch_items, snapshot)
            self._run_batch(snapshot)

        def _run_batch(self, snapshot: BatchSnapshot) -> None:
            try:
                self.batch_runner.start(self.batch_items, snapshot, callback=self._batch_event)
                self.render_button.set_sensitive(False)
                self.export_button.set_sensitive(False)
                self.cancel_button.set_visible(True)
                self.status_label.set_text("Starting batch...")
                self._batch_timeout = GLib.timeout_add(50, self._poll_batch)
            except (ValidationError, RuntimeError) as exc:
                show_error(Adw, self, "Batch cannot start", str(exc))

        def _poll_batch(self) -> bool:
            self.batch_runner.poll()
            return self.batch_runner.active

        def _batch_event(self, event: str, item: BatchItem | None, payload) -> None:
            self._refresh_batch_list()
            if event == "progress":
                self.status_label.set_text(f"Processing {Path(item.source_path).name}...")
                self.progress.set_visible(True)
                self.progress.pulse()
            elif event == "finished":
                summary = payload.get("summary")
                self.status_label.set_text(
                    f"Batch complete: {summary.completed} completed, {summary.skipped} skipped, "
                    f"{summary.failed} failed, {summary.cancelled} cancelled."
                )
                self.progress.set_visible(False)
                self.cancel_button.set_visible(False)
                self.render_button.set_sensitive(True)
                self.export_button.set_sensitive(True)

        def _cancel_batch(self) -> None:
            self.batch_runner.cancel()
            self._refresh_batch_list()

        def _open_dialog(
            self, title, multiple, callback, *, image_filter=False, preset_filter=False
        ) -> None:
            dialog = Gtk.FileDialog(title=title)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            if image_filter:
                image_filter_obj = Gtk.FileFilter(name="PNG and JPEG images")
                image_filter_obj.add_mime_type("image/png")
                image_filter_obj.add_mime_type("image/jpeg")
                filters.append(image_filter_obj)
            if preset_filter:
                preset_filter_obj = Gtk.FileFilter(name="ChromaSunder presets")
                preset_filter_obj.add_pattern("*.csunder")
                filters.append(preset_filter_obj)
            if filters.get_n_items():
                dialog.set_default_filter(filters.get_item(0))
            if multiple:
                dialog.open_multiple(self, None, callback)
            else:
                dialog.open(self, None, callback)

        def _save_dialog(self, title, initial_name, callback) -> None:
            dialog = Gtk.FileDialog(title=title, initial_name=initial_name)
            dialog.save(self, None, callback)

        def _folder_dialog(self, title, callback) -> None:
            dialog = Gtk.FileDialog(title=title)
            dialog.select_folder(self, None, callback)

        def _restore_settings(self) -> None:
            try:
                values = self.store.get("last-processing-settings", {})
                if values:
                    from chromasunder.core.models import PixelSortSettings

                    self.editor.settings_controller.apply_preset(
                        PixelSortSettings.from_dict(values)
                    )
                self.jpeg_quality = int(self.store.get("jpeg-quality", 95))
                self.jpeg_background_row.set_text(self.store.get("jpeg-background", "black"))
                self.suffix_row.set_text(self.store.get("default-output-suffix", "_pxsorted"))
                self.batch_output_mode_row.set_selected(
                    list(OutputMode).index(
                        OutputMode(self.store.get("last-output-mode", OutputMode.PNG.value))
                    )
                )
                self.jpeg_quality_row.set_value(self.jpeg_quality)
                self.set_default_size(
                    int(self.store.get("window-width", 1280)),
                    int(self.store.get("window-height", 860)),
                )
                self.batch_toggle.set_active(bool(self.store.get("batch-queue-expanded", False)))
                if self.store.get("window-maximized", False):
                    self.maximize()
            except Exception:
                pass
            self._on_settings_changed()

        def _on_close_request(self, *_args) -> bool:
            self.worker.cancel()
            self.batch_runner.cancel()
            try:
                self.store.set("last-processing-settings", self.editor.settings.to_dict())
                self.store.set("jpeg-quality", getattr(self, "jpeg_quality", 95))
                self.store.set("jpeg-background", self.jpeg_background_row.get_text() or "black")
                self.store.set(
                    "last-output-mode",
                    str(list(OutputMode)[self.batch_output_mode_row.get_selected()]),
                )
                self.store.set("window-width", self.get_width())
                self.store.set("window-height", self.get_height())
                self.store.set("window-maximized", self.is_maximized())
                self.store.set("batch-queue-expanded", self.batch_toggle.get_active())
                self.store.set("default-output-suffix", self.suffix_row.get_text() or "_pxsorted")
            except Exception:
                pass
            return False


else:

    class MainWindow:  # pragma: no cover - only a friendly import fallback
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("GTK 4 and libadwaita are required to run ChromaSunder.")
