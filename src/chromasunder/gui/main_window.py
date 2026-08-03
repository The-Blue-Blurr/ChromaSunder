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
from chromasunder.core.exporting import suggest_output_path
from chromasunder.core.presets import PresetError, load_preset, save_preset
from chromasunder.core.validation import ValidationError
from chromasunder.gui.angle_dial import AngleDial, normalize_angle
from chromasunder.gui.batch.controller import BatchRunner
from chromasunder.gui.batch.model import (
    BatchItem,
    BatchSnapshot,
    BatchStatus,
    ConflictPolicy,
    OutputMode,
    inspect_item,
    numeric_suffix_path,
    preflight_outputs,
)
from chromasunder.gui.batch.view import build_batch_view
from chromasunder.gui.dialogs import (
    show_apply_preset_dialog,
    show_clear_recent_dialog,
    show_conflict_dialog,
    show_error,
    show_no_render_dialog,
    show_stale_export_dialog,
    show_suffix_dialog,
)
from chromasunder.gui.editor_controller import EditorController
from chromasunder.gui.file_import import local_paths
from chromasunder.gui.persistence import SettingsStore
from chromasunder.gui.recent import RecentStore
from chromasunder.gui.settings_controller import sensitivity_for_mode
from chromasunder.worker.controller import WorkerController, clean_abandoned_cache, new_render_paths

APP_TITLE = "Chroma Sunder"

SETTING_HELP = {
    "interval_function": (
        "Controls how each row is divided into intervals. Pixels are sorted only within each "
        "interval and never across its boundaries."
    ),
    "sorting_function": (
        "Controls which color property is used to arrange pixels inside every sorting interval."
    ),
    "lower_threshold": (
        "Sets the minimum lightness for Threshold mode, or the minimum brightness change that "
        "counts as an edge in Edges and File Edges modes."
    ),
    "upper_threshold": (
        "Sets the maximum lightness included in Threshold mode. Brighter pixels are left outside "
        "sorting intervals."
    ),
    "characteristic_length": (
        "Sets the typical interval length in pixels for Random and Waves modes. Larger values "
        "usually produce longer streaks."
    ),
    "angle": (
        "Sets the direction of sorting from 0 to 360 degrees. Drag the dial or enter a precise "
        "value; zero sorts horizontally and 90 degrees produces vertical sorting."
    ),
    "randomness": (
        "Sets the percentage of intervals that are skipped. Zero sorts every interval; higher "
        "values preserve more of the original image."
    ),
    "seed": (
        "Controls repeatable random choices. The same image, settings, and seed produce the same "
        "random pattern."
    ),
    "mask_image": (
        "Optionally limits where pixels can move. White areas of the mask can be sorted, while "
        "black areas remain unchanged."
    ),
    "interval_image": (
        "Provides black-and-white interval information for File and File Edges modes. It must "
        "have the same dimensions as the source image."
    ),
    "jpeg_quality": (
        "Sets JPEG compression quality. Higher values retain more detail but create larger files."
    ),
    "jpeg_background": (
        "Sets the color placed behind transparent pixels when exporting to JPEG, which does not "
        "support transparency."
    ),
    "output_suffix": (
        "Sets the text added to an exported filename before its extension, such as _pxsorted."
    ),
    "batch_output_mode": (
        "Controls batch file types. PNG always writes PNG files; Preserve keeps PNG sources as "
        "PNG and JPEG sources as JPEG."
    ),
}

INTERVAL_HELP = (
    (
        "Threshold",
        "Sorts connected runs of pixels whose lightness falls between the lower and upper "
        "thresholds.",
    ),
    (
        "Edges",
        "Uses strong lightness changes between neighboring pixels as the boundaries of each "
        "sorting interval.",
    ),
    (
        "Random",
        "Divides each row into randomly sized intervals. Characteristic length controls their "
        "typical maximum size.",
    ),
    (
        "Waves",
        "Divides each row into nearly even intervals with small random changes in length, creating "
        "a repeating wave-like pattern.",
    ),
    (
        "File",
        "Uses white runs in the selected black-and-white interval image as sorting intervals. The "
        "image must match the source dimensions.",
    ),
    (
        "File Edges",
        "Uses changes in the selected interval image as interval boundaries instead of detecting "
        "edges in the source image.",
    ),
    ("None", "Treats each complete row as one interval, stopping only at the image borders."),
)

SORTING_HELP = (
    ("Lightness", "Orders pixels from dark to light using their HSL lightness."),
    ("Hue", "Orders pixels by their position around the color wheel."),
    ("Saturation", "Orders pixels from muted or gray colors to stronger, more vivid colors."),
    ("Intensity", "Orders pixels by the average brightness of their red, green, and blue values."),
    ("Minimum", "Orders pixels by whichever of their red, green, or blue values is lowest."),
)


if Adw is not None:

    class MainWindow(Adw.ApplicationWindow):
        def __init__(self, application) -> None:
            super().__init__(application=application, title=APP_TITLE)
            self.set_default_size(1280, 860)
            self.editor = EditorController()
            self.worker = WorkerController()
            self.batch_runner = BatchRunner(WorkerController())
            self.store = SettingsStore()
            self.recent = RecentStore()
            self.batch_items: list[BatchItem] = []
            self.batch_output_folder: str | None = None
            self._render_snapshot = None
            self._pending_export: Path | None = None
            self._worker_operation = "render"
            self._render_timeout = None
            self._batch_timeout = None
            self._busy = False
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
                "cancel": (self._cancel_render, ["Escape"]),
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

            self.open_button = Gtk.Button(label="Open")
            self.open_button.connect("clicked", lambda _button: self._open_image())
            header.pack_start(self.open_button)
            self.recents_button = Gtk.MenuButton(label="Recents")
            self.recents_button.set_menu_model(self._recent_images_menu())
            header.pack_start(self.recents_button)
            self.presets_button = Gtk.MenuButton(label="Presets")
            self.presets_button.set_menu_model(self._preset_menu())
            header.pack_start(self.presets_button)

            self.undo_button = Gtk.Button(label="Undo")
            self.undo_button.connect("clicked", lambda _button: self._undo())
            self.redo_button = Gtk.Button(label="Redo")
            self.redo_button.connect("clicked", lambda _button: self._redo())
            self.help_button = Gtk.Button(label="Help")
            self.help_button.connect("clicked", lambda _button: self._show_help())
            self.about_button = Gtk.Button(label="About")
            self.about_button.set_action_name("app.about")
            header.pack_start(self.undo_button)
            header.pack_start(self.redo_button)
            header.pack_start(self.help_button)
            header.pack_start(self.about_button)

            self.render_button = Gtk.Button(label="Render")
            self.render_button.add_css_class("suggested-action")
            self.render_button.connect("clicked", lambda _button: self._render())
            header.pack_end(self.render_button)
            self.export_button = Gtk.Button(label="Export")
            self.export_button.connect("clicked", lambda _button: self._choose_export_destination())
            header.pack_end(self.export_button)

            paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
            paned.set_position(1040)
            self.stale_banner = Adw.Banner()
            self.stale_banner.set_revealed(False)
            content.append(self.stale_banner)
            content.append(paned)
            paned.set_start_child(self._build_preview_panel())
            self.controls_panel = self._build_controls_panel()
            paned.set_end_child(self.controls_panel)

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
            self._recent_presets_section = Gio.Menu()
            menu.append_section("Recent Presets", self._recent_presets_section)
            menu.append_section(None, Gio.Menu())
            menu.append("Clear Recent Presets", "win.clear-recent-presets")
            menu.append_section(None, Gio.Menu())
            menu.append("Load Preset", "win.load-preset")
            menu.append("Save Preset", "win.save-preset")
            menu.append("Reset Settings", "win.reset-settings")
            menu.append("New Variation", "win.new-variation")
            for name, callback in (
                ("clear-recent-presets", self._clear_recent_presets),
                ("load-preset", self._load_preset),
                ("save-preset", self._save_preset),
                ("reset-settings", self._reset_settings),
                ("new-variation", self._new_variation),
            ):
                action = Gio.SimpleAction.new(name, None)
                action.connect("activate", lambda _action, _parameter, fn=callback: fn())
                self.add_action(action)
            self._refresh_recent_menus()
            return menu

        def _recent_images_menu(self):
            menu = Gio.Menu()
            self._recent_images_section = Gio.Menu()
            menu.append_section("Recent Images", self._recent_images_section)
            menu.append_section(None, Gio.Menu())
            menu.append("Clear Recent Files", "win.clear-recent-images")
            action = Gio.SimpleAction.new("clear-recent-images", None)
            action.connect("activate", lambda _action, _parameter: self._clear_recent_images())
            self.add_action(action)
            no_op = Gio.SimpleAction.new("no-op", None)
            no_op.set_enabled(False)
            self.add_action(no_op)
            self._refresh_recent_menus()
            return menu

        def _refresh_recent_menus(self) -> None:
            if not hasattr(self, "_recent_images_section"):
                return
            self._recent_images_section.remove_all()
            for index, path in enumerate(self.recent.images):
                self._recent_images_section.append(
                    self._recent_label(path), f"win.open-recent-image-{index}"
                )
                self._ensure_recent_action(
                    f"open-recent-image-{index}", lambda index=index: self._open_recent_image(index)
                )
            if not self.recent.images:
                self._recent_images_section.append("No recent images", "win.no-op")
            if hasattr(self, "_recent_presets_section"):
                self._recent_presets_section.remove_all()
                for index, path in enumerate(self.recent.presets):
                    self._recent_presets_section.append(
                        self._recent_label(path), f"win.open-recent-preset-{index}"
                    )
                    self._ensure_recent_action(
                        f"open-recent-preset-{index}",
                        lambda index=index: self._open_recent_preset(index),
                    )
                if not self.recent.presets:
                    self._recent_presets_section.append("No recent presets", "win.no-op")

        def _ensure_recent_action(self, name: str, callback) -> None:
            if self.lookup_action(name) is not None:
                return
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _action, _parameter: callback())
            self.add_action(action)

        def _recent_label(self, path: str) -> str:
            item = Path(path)
            label = f"{item.name} ({item.parent.name})"
            if not self.recent.is_available(path):
                label += " [unavailable]"
            return label

        def _refresh_recent_menu_models(self) -> None:
            self._refresh_recent_menus()

        def _open_recent_image(self, index: int) -> None:
            if self._busy or index >= len(self.recent.images):
                return
            path = self.recent.images[index]
            if not self.recent.is_available(path):
                show_error(
                    Adw, self, "Unable to open recent image", f"The file is unavailable:\n{path}"
                )
                return
            try:
                self._open_source_path(path)
            except (ValidationError, OSError) as exc:
                show_error(Adw, self, "Unable to open image", str(exc))

        def _open_recent_preset(self, index: int) -> None:
            if self._busy or index >= len(self.recent.presets):
                return
            path = self.recent.presets[index]
            if not self.recent.is_available(path):
                show_error(
                    Adw, self, "Unable to load recent preset", f"The file is unavailable:\n{path}"
                )
                return
            self._load_preset_path(path)

        def _clear_recent_images(self) -> None:
            show_clear_recent_dialog(
                Adw,
                self,
                "files",
                lambda response: self._finish_clear_recent_images(response),
            )

        def _finish_clear_recent_images(self, response: str) -> None:
            if response == "clear":
                self.recent.clear_images()
                self._refresh_recent_menu_models()

        def _clear_recent_presets(self) -> None:
            show_clear_recent_dialog(
                Adw,
                self,
                "presets",
                lambda response: self._finish_clear_recent_presets(response),
            )

        def _finish_clear_recent_presets(self, response: str) -> None:
            if response == "clear":
                self.recent.clear_presets()
                self._refresh_recent_menu_models()

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
            empty = Gtk.Label(label="Open an image or drop it here", xalign=0.5, yalign=0.5)
            self.preview_stack.add_named(empty, "empty")
            self.original_picture = Gtk.Picture()
            self.original_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            self.rendered_picture = Gtk.Picture()
            self.rendered_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            self.preview_stack.add_named(self.original_picture, "original")
            self.preview_stack.add_named(self.rendered_picture, "rendered")
            self.preview_stack.set_visible_child_name("empty")
            self.preview_stack.add_controller(self._file_drop_target(self._drop_source))
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
            scroller.set_min_content_width(220)
            scroller.set_propagate_natural_width(False)
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            controls.set_hexpand(True)
            controls.set_margin_top(12)
            controls.set_margin_bottom(12)
            controls.set_margin_start(12)
            controls.set_margin_end(12)
            scroller.set_child(controls)

            self.controls_stack = Adw.ViewStack()
            self.controls_stack.set_hexpand(True)
            controls_switcher = Adw.ViewSwitcher()
            controls_switcher.set_stack(self.controls_stack)
            controls_switcher.set_hexpand(True)
            controls.append(controls_switcher)
            controls.append(self.controls_stack)

            processing_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            export_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            self.controls_stack.add_titled(processing_page, "processing", "Processing")
            self.controls_stack.add_titled(export_page, "export", "Export")
            self.controls_stack.set_visible_child_name("processing")

            processing = Adw.PreferencesGroup(title="Processing")
            processing_page.append(processing)
            self.interval_row = self._combo_row(
                "Interval function", list(IntervalFunction), self._interval_changed
            )
            self.sorting_row = self._combo_row(
                "Sorting function", list(SortingFunction), self._sorting_changed
            )
            self._add_info_popover(self.interval_row, SETTING_HELP["interval_function"])
            self._add_info_popover(self.sorting_row, SETTING_HELP["sorting_function"])
            processing.add(self.interval_row)
            processing.add(self.sorting_row)
            self.lower_row = self._slider_row("Lower threshold", 0.0, 1.0, 0.01, 2)
            self.upper_row = self._slider_row("Upper threshold", 0.0, 1.0, 0.01, 2)
            self.length_row = self._spin_row("Characteristic length", 1, 10000, 1, 0)
            self.angle_row = self._angle_row("Angle")
            self.randomness_row = self._slider_row("Randomness", 0, 100, 1, 1)
            self.seed_row = self._seed_row("Seed")
            self.seed_randomize_button = Gtk.Button(icon_name="media-playlist-shuffle-symbolic")
            self.seed_randomize_button.set_valign(Gtk.Align.CENTER)
            self.seed_randomize_button.add_css_class("flat")
            self.seed_randomize_button.set_tooltip_text("Randomize seed")
            self.seed_randomize_button.update_property(
                [Gtk.AccessibleProperty.LABEL], ["Randomize seed"]
            )
            self.seed_randomize_button.connect("clicked", lambda _button: self._new_variation())
            self.seed_row.add_suffix(self.seed_randomize_button)
            for row, help_key in (
                (self.lower_row, "lower_threshold"),
                (self.upper_row, "upper_threshold"),
                (self.length_row, "characteristic_length"),
                (self.angle_row, "angle"),
                (self.randomness_row, "randomness"),
                (self.seed_row, "seed"),
            ):
                self._add_info_popover(row, SETTING_HELP[help_key])
                processing.add(row)
                if row is self.seed_row:
                    row._chromasunder_entry.connect(
                        "activate",
                        lambda _entry, numeric_row=row: self._numeric_changed(numeric_row),
                    )
                    focus = Gtk.EventControllerFocus.new()
                    focus.connect(
                        "leave", lambda _focus, numeric_row=row: self._numeric_changed(numeric_row)
                    )
                    row._chromasunder_entry.add_controller(focus)
                else:
                    adjustment = getattr(row, "_chromasunder_adjustment", row)
                    adjustment.connect(
                        "notify::value",
                        lambda _adjustment, pspec, numeric_row=row: self._numeric_changed(
                            numeric_row, pspec
                        ),
                    )

            auxiliary = Adw.PreferencesGroup(title="Auxiliary Images")
            processing_page.append(auxiliary)
            self.mask_row = self._file_row("Mask image", self._choose_mask)
            self.interval_image_row = self._file_row("Interval image", self._choose_interval_image)
            self._add_info_popover(self.mask_row, SETTING_HELP["mask_image"])
            self._add_info_popover(self.interval_image_row, SETTING_HELP["interval_image"])
            auxiliary.add(self.mask_row)
            auxiliary.add(self.interval_image_row)

            export_group = Adw.PreferencesGroup(title="Export")
            export_page.append(export_group)
            self.jpeg_quality_row = self._spin_row("JPEG quality", 1, 100, 1, 0)
            self.jpeg_quality_row.set_value(95)
            self.jpeg_quality_row.connect("notify::value", self._jpeg_quality_changed)
            self.jpeg_background_row = Adw.EntryRow(title="JPEG background")
            self.jpeg_background_row.set_text("black")
            self.jpeg_background_row.connect("notify::text", self._jpeg_background_changed)
            self.suffix_row = Adw.EntryRow(title="Default output suffix")
            self.suffix_row.set_text("_pxsorted")
            self.suffix_row.connect("notify::text", self._suffix_changed)
            self._add_info_popover(self.jpeg_quality_row, SETTING_HELP["jpeg_quality"])
            self._add_info_popover(self.jpeg_background_row, SETTING_HELP["jpeg_background"])
            self._add_info_popover(self.suffix_row, SETTING_HELP["output_suffix"])
            export_group.add(self.jpeg_quality_row)
            export_group.add(self.jpeg_background_row)
            export_group.add(self.suffix_row)

            self.batch_output_mode_row = self._combo_row(
                "Batch output mode", list(OutputMode), self._batch_output_mode_changed
            )
            self._add_info_popover(self.batch_output_mode_row, SETTING_HELP["batch_output_mode"])
            export_page.append(self.batch_output_mode_row)

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
            batch_group.add_controller(self._file_drop_target(self._drop_batch))
            export_page.append(batch_group)
            return scroller

        def _file_drop_target(self, callback):
            target = Gtk.DropTarget.new(Gdk.FileList.__gtype__, Gdk.DragAction.COPY)
            target.set_gtypes([Gdk.FileList.__gtype__, Gio.File.__gtype__])
            target.connect("accept", self._accept_file_drop)
            target.connect("drop", callback)
            return target

        def _accept_file_drop(self, _target, drop) -> bool:
            if self._busy:
                return False
            formats = drop.get_formats().union_deserialize_gtypes()
            return formats.contain_gtype(Gdk.FileList.__gtype__) or formats.contain_gtype(
                Gio.File.__gtype__
            )

        @staticmethod
        def _dropped_files(value):
            if isinstance(value, Gdk.FileList):
                return value.get_files()
            if isinstance(value, Gio.File):
                return [value]
            return []

        def _drop_source(self, _target, value, _x, _y) -> bool:
            if self._busy:
                return False
            files = self._dropped_files(value)
            paths, non_local = local_paths(files)
            if len(files) != 1:
                show_error(
                    Adw,
                    self,
                    "Unable to open image",
                    "Drop exactly one image onto the preview.",
                )
                return True
            if non_local:
                show_error(
                    Adw,
                    self,
                    "Unable to open image",
                    "Only local image files can be opened.",
                )
                return True
            try:
                self._open_source_path(paths[0])
            except (ValidationError, OSError) as exc:
                show_error(Adw, self, "Unable to open image", str(exc))
            return True

        def _drop_batch(self, _target, value, _x, _y) -> bool:
            if self._busy:
                return False
            files = self._dropped_files(value)
            if not files:
                return False
            paths, non_local = local_paths(files)
            failures = [f"{name}: only local image files are supported" for name in non_local]
            failures.extend(self._add_batch_paths(paths))
            self.batch_toggle.set_active(True)
            self._report_batch_import_failures(failures)
            return True

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
            row = Adw.SpinRow.new(adjustment, step, digits)
            row.set_title(title)
            row._chromasunder_syncing = False
            return row

        def _slider_row(self, title, lower, upper, step, digits):
            adjustment = Gtk.Adjustment(
                value=lower, lower=lower, upper=upper, step_increment=step, page_increment=step * 10
            )
            row = Adw.ActionRow(title=title)
            controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            controls.set_hexpand(True)

            scale = Gtk.Scale.new(Gtk.Orientation.HORIZONTAL, adjustment)
            scale.set_draw_value(False)
            scale.set_hexpand(True)
            scale.set_size_request(100, -1)
            controls.append(scale)

            spin = Gtk.SpinButton.new(adjustment, step, digits)
            spin.set_width_chars(5)
            spin.set_valign(Gtk.Align.CENTER)
            controls.append(spin)

            row.add_suffix(controls)
            row.set_activatable_widget(spin)
            row._chromasunder_adjustment = adjustment
            row._chromasunder_syncing = False
            return row

        def _angle_row(self, title):
            adjustment = Gtk.Adjustment(
                value=0, lower=0, upper=360, step_increment=1, page_increment=15
            )
            row = Adw.ActionRow(title=title)
            controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            dial = AngleDial(adjustment)
            controls.append(dial)

            spin = Gtk.SpinButton.new(adjustment, 1, 0)
            spin.set_width_chars(4)
            spin.set_valign(Gtk.Align.CENTER)
            controls.append(spin)

            row.add_suffix(controls)
            row.set_activatable_widget(spin)
            row._chromasunder_adjustment = adjustment
            row._chromasunder_syncing = False
            return row

        def _seed_row(self, title):
            row = Adw.ActionRow(title=title)
            entry = Gtk.Entry()
            entry.set_width_chars(10)
            entry.set_max_width_chars(10)
            entry.set_max_length(10)
            entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
            entry.set_valign(Gtk.Align.CENTER)
            row.add_suffix(entry)
            row.set_activatable_widget(entry)
            row._chromasunder_entry = entry
            row._chromasunder_syncing = False
            return row

        def _file_row(self, title, callback):
            row = Adw.ActionRow(title=title, subtitle="None selected")
            indicator = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            indicator.set_pixel_size(16)
            indicator.set_visible(False)
            row.add_prefix(indicator)

            button = Gtk.Button(label="Choose")
            button.set_valign(Gtk.Align.CENTER)
            button.connect("clicked", lambda _button: callback(row))
            row.add_suffix(button)

            clear_button = Gtk.Button(icon_name="edit-clear-symbolic")
            clear_button.set_valign(Gtk.Align.CENTER)
            clear_button.add_css_class("flat")
            clear_button.set_tooltip_text(f"Clear {title.lower()}")
            clear_button.update_property([Gtk.AccessibleProperty.LABEL], [f"Clear {title.lower()}"])
            clear_button.set_sensitive(False)
            clear_button.connect("clicked", lambda _button: self._clear_file_row(row))
            row.add_suffix(clear_button)

            row._chromasunder_indicator = indicator
            row._chromasunder_button = button
            row._chromasunder_clear_button = clear_button
            return row

        @staticmethod
        def _sync_file_row(row, path: str | None) -> None:
            selected = bool(path)
            row.set_subtitle(Path(path).name if path else "None selected")
            row._chromasunder_indicator.set_visible(selected)
            row._chromasunder_clear_button.set_sensitive(selected)

        def _clear_file_row(self, row) -> None:
            if row is self.mask_row:
                self.editor.set_mask(None)
            elif row is self.interval_image_row:
                self.editor.set_interval_image(None)
            else:
                return
            self._sync_file_row(row, None)
            self._set_stale_banner()

        def _add_info_popover(self, row, text) -> None:
            button = Gtk.MenuButton(icon_name="dialog-information-symbolic")
            button.set_valign(Gtk.Align.CENTER)
            button.add_css_class("flat")

            label = Gtk.Label(label=text, wrap=True, xalign=0)
            label.set_max_width_chars(38)
            label.set_margin_top(12)
            label.set_margin_bottom(12)
            label.set_margin_start(12)
            label.set_margin_end(12)

            popover = Gtk.Popover()
            popover.set_child(label)
            button.set_popover(popover)
            row.add_suffix(button)

        def _show_help(self) -> None:
            dialog = Adw.Window(title="Pixel Sorting Help", transient_for=self, modal=True)
            dialog.set_destroy_with_parent(True)
            width = max(420, int(self.get_width() * 0.82))
            height = max(440, int(self.get_height() * 0.82))
            dialog.set_default_size(width, height)

            toolbar = Adw.ToolbarView()
            header = Adw.HeaderBar()
            close_button = Gtk.Button(label="Close")
            close_button.connect("clicked", lambda _button: dialog.close())
            header.pack_end(close_button)
            toolbar.add_top_bar(header)

            scroller = Gtk.ScrolledWindow()
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
            content.set_margin_top(18)
            content.set_margin_bottom(24)
            content.set_margin_start(24)
            content.set_margin_end(24)

            introduction = Gtk.Label(
                label=(
                    "Pixel sorting divides image rows into intervals, then rearranges the pixels "
                    "inside each interval according to a selected color property. Interval modes "
                    "control where sorting can happen; sorting modes control the resulting order."
                ),
                wrap=True,
                xalign=0,
            )
            introduction.add_css_class("title-4")
            content.append(introduction)
            content.append(
                self._help_group(
                    "Interval Functions",
                    "Choose how the boundaries of sortable sections are found.",
                    INTERVAL_HELP,
                )
            )
            content.append(
                self._help_group(
                    "Sorting Functions",
                    "Choose the color property used to order pixels within each interval.",
                    SORTING_HELP,
                )
            )

            scroller.set_child(content)
            toolbar.set_content(scroller)
            dialog.set_content(toolbar)
            dialog.present()

        def _help_group(self, title, description, entries):
            group = Adw.PreferencesGroup(title=title, description=description)
            for entry_title, entry_description in entries:
                row = Adw.ActionRow(title=entry_title, subtitle=entry_description)
                group.add(row)
            return group

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
                (
                    self.angle_row,
                    normalize_angle(settings.angle, preserve_full_turn=True),
                ),
                (self.randomness_row, settings.randomness),
                (self.seed_row, settings.seed),
            ):
                row._chromasunder_syncing = True
                self._set_numeric_value(row, value)
                row._chromasunder_syncing = False
            sensitivity = sensitivity_for_mode(settings.interval_function)
            self.lower_row.set_sensitive(sensitivity.lower)
            self.upper_row.set_sensitive(sensitivity.upper)
            self.length_row.set_sensitive(sensitivity.length)
            self.interval_image_row.set_sensitive(sensitivity.interval_image)
            self.undo_button.set_sensitive(self.editor.settings_controller.history.can_undo)
            self.redo_button.set_sensitive(self.editor.settings_controller.history.can_redo)
            self._set_stale_banner()
            self._persist("last-processing-settings", settings.to_dict())

        def _interval_changed(self, row, _pspec) -> None:
            values = list(IntervalFunction)
            self.editor.update_settings(interval_function=values[row.get_selected()])

        def _sorting_changed(self, row, _pspec) -> None:
            values = list(SortingFunction)
            self.editor.update_settings(sorting_function=values[row.get_selected()])

        def _numeric_changed(self, row, _pspec=None) -> None:
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
                    value = self._get_numeric_value(row)
                    if name in {"characteristic_length", "seed"}:
                        value = int(value)
                    if name == "seed" and value > 2**31 - 1:
                        raise ValidationError("The seed must be between 0 and 2147483647.")
                    self.editor.update_settings(**{name: value})
                except (ValueError, ValidationError) as exc:
                    row._chromasunder_syncing = True
                    self._set_numeric_value(row, getattr(self.editor.settings, name))
                    row._chromasunder_syncing = False
                    self.status_label.set_text(
                        str(exc)
                        if isinstance(exc, ValidationError)
                        else "The seed must be an integer."
                    )

        @staticmethod
        def _get_numeric_value(row) -> float:
            entry = getattr(row, "_chromasunder_entry", None)
            if entry is not None:
                return int(entry.get_text())
            adjustment = getattr(row, "_chromasunder_adjustment", None)
            return adjustment.get_value() if adjustment is not None else row.get_value()

        @staticmethod
        def _set_numeric_value(row, value) -> None:
            entry = getattr(row, "_chromasunder_entry", None)
            if entry is not None:
                entry.set_text(str(int(value)))
                return
            adjustment = getattr(row, "_chromasunder_adjustment", None)
            if adjustment is not None:
                adjustment.set_value(value)
            else:
                row.set_value(value)

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
                paths, non_local = local_paths([file])
                if non_local:
                    raise ValidationError("Only local image files can be opened.", "non-local-file")
                self._open_source_path(paths[0])
            except GLib.Error as exc:
                if not exc.matches(Gtk.DialogError.quark(), Gtk.DialogError.DISMISSED):
                    show_error(Adw, self, "Unable to open image", str(exc))
            except (ValidationError, OSError) as exc:
                show_error(Adw, self, "Unable to open image", str(exc))

        def _open_source_path(self, path: str) -> None:
            self.editor.open_source(path)
            self.recent.add_image(path)
            self._refresh_recent_menu_models()
            self._sync_file_row(self.mask_row, self.editor.state.mask_path)
            self._sync_file_row(self.interval_image_row, self.editor.state.interval_path)
            self._show_source(path)
            self._clear_rendered_view()
            self.status_label.set_text(Path(path).name)

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
                    self._sync_file_row(row, self.editor.state.mask_path)
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
                    self._sync_file_row(row, self.editor.state.interval_path)
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
                self._worker_operation = "render"
                self.worker.start(request)
                self._set_busy(True)
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
                    self.worker.finish()
                    if self._worker_operation == "export":
                        destination = Path(payload["output_path"])
                        self._pending_export = None
                        self._finish_render_ui(f"Exported {destination.name}")
                        return False
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
                    operation = "Export" if self._worker_operation == "export" else "Render"
                    self._pending_export = None
                    self._finish_render_ui(f"{operation} failed")
                    show_error(
                        Adw,
                        self,
                        f"{operation} failed",
                        payload.get("message", "The worker failed."),
                        payload.get("details"),
                    )
                    return False
                if kind == "cancelled":
                    self._finish_render_ui("Render cancelled")
                    return False
            process = self.worker.process
            if process is not None and not process.is_alive():
                operation = "Export" if self._worker_operation == "export" else "Render"
                self._pending_export = None
                self._finish_render_ui(f"{operation} worker exited unexpectedly")
                show_error(
                    Adw,
                    self,
                    f"{operation} failed",
                    f"The {operation.lower()} worker exited unexpectedly.",
                )
                return False
            return True

        def _finish_render_ui(self, message: str) -> None:
            self.worker.close()
            self._set_busy(False)
            self.progress.set_visible(False)
            self.cancel_button.set_visible(False)
            self.status_label.set_text(message)
            self._set_stale_banner()

        def _cancel_render(self) -> None:
            if self.worker.active:
                self.worker.cancel()
                operation = "Export" if self._worker_operation == "export" else "Render"
                self._pending_export = None
                self._finish_render_ui(f"{operation} cancelled")
            elif self.batch_runner.active:
                self._cancel_batch()

        def _set_busy(self, busy: bool) -> None:
            self._busy = busy
            for widget in (
                self.open_button,
                self.recents_button,
                self.presets_button,
                self.render_button,
                self.export_button,
                self.controls_panel,
            ):
                widget.set_sensitive(not busy)
            self.undo_button.set_sensitive(
                not busy and self.editor.settings_controller.history.can_undo
            )
            self.redo_button.set_sensitive(
                not busy and self.editor.settings_controller.history.can_redo
            )
            for name in (
                "open",
                "render",
                "export",
                "undo-settings",
                "redo-settings",
                "load-preset",
                "save-preset",
                "reset-settings",
                "new-variation",
            ):
                action = self.lookup_action(name)
                if action is not None:
                    enabled = not busy
                    if name == "undo-settings":
                        enabled = enabled and self.editor.settings_controller.history.can_undo
                    elif name == "redo-settings":
                        enabled = enabled and self.editor.settings_controller.history.can_redo
                    action.set_enabled(enabled)

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
                self._persist("jpeg-quality", self.jpeg_quality)

        def _jpeg_background_changed(self, row, _pspec) -> None:
            self._persist("jpeg-background", row.get_text() or "black")

        def _suffix_changed(self, row, _pspec) -> None:
            self._persist("default-output-suffix", row.get_text() or "_pxsorted")

        def _batch_output_mode_changed(self, _row, _pspec) -> None:
            if hasattr(self, "batch_output_mode_row"):
                self._persist(
                    "last-output-mode",
                    str(list(OutputMode)[self.batch_output_mode_row.get_selected()]),
                )

        def _choose_export_destination(self) -> None:
            if not self.editor.has_source:
                show_error(Adw, self, "Nothing to export", "Open an image first.")
                return
            default = suggest_output_path(
                self.editor.state.source_path,
                suffix=self.suffix_row.get_text() or "_pxsorted",
                output_format="PNG",
            )
            self._save_dialog(
                "Export Image", default.name, self._finish_export_destination, export_filter=True
            )

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
            extension = destination.suffix.lower()
            if extension not in {".png", ".jpg", ".jpeg"}:
                show_error(
                    Adw,
                    self,
                    "Export failed",
                    "Choose a PNG (.png) or JPEG (.jpg or .jpeg) destination.",
                )
                self._pending_export = None
                return
            try:
                self._pending_export = destination
                self._worker_operation = "export"
                self.worker.start(
                    {
                        "operation": "export",
                        "cache_path": self.editor.state.cache_path,
                        "output_path": str(destination),
                        "output_format": "JPEG" if extension in {".jpg", ".jpeg"} else "PNG",
                        "jpeg_quality": getattr(self, "jpeg_quality", 95),
                        "jpeg_background": self.jpeg_background_row.get_text() or "black",
                    }
                )
                self._set_busy(True)
                self.progress.set_visible(True)
                self.progress.pulse()
                self.cancel_button.set_visible(True)
                self.status_label.set_text("Exporting full-resolution image...")
                self._render_timeout = GLib.timeout_add(50, self._poll_render)
            except (OSError, ValidationError, RuntimeError) as exc:
                show_error(Adw, self, "Export failed", str(exc))
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
                    self._load_preset_path(file.get_path())
            except (GLib.Error, PresetError) as exc:
                if isinstance(exc, PresetError):
                    show_error(Adw, self, "Invalid preset", str(exc))

        def _load_preset_path(self, path: str) -> None:
            try:
                settings = load_preset(path)
            except (PresetError, OSError) as exc:
                show_error(Adw, self, "Invalid preset", str(exc))
                return
            if settings == self.editor.settings:
                self.recent.add_preset(path)
                self._refresh_recent_menu_models()
                return
            show_apply_preset_dialog(
                Adw,
                self,
                lambda response: self._finish_apply_preset(response, path, settings),
            )

        def _finish_apply_preset(self, response: str, path: str, settings) -> None:
            if response != "apply":
                return
            self.editor.settings_controller.apply_preset(settings)
            self.recent.add_preset(path)
            self._refresh_recent_menu_models()

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

        def _add_batch_images(self) -> None:
            self._open_dialog("Add Images", True, self._finish_add_batch, image_filter=True)

        def _finish_add_batch(self, dialog, result) -> None:
            try:
                files = dialog.open_multiple_finish(result)
                references = [files.get_item(index) for index in range(files.get_n_items())]
                paths, non_local = local_paths(references)
                failures = [f"{name}: only local image files are supported" for name in non_local]
                failures.extend(self._add_batch_paths(paths))
                self._report_batch_import_failures(failures)
            except GLib.Error:
                return

        def _add_batch_paths(self, paths) -> list[str]:
            failures = []
            for path in paths:
                try:
                    self.batch_items.append(inspect_item(path))
                except (ValidationError, OSError) as exc:
                    failures.append(f"{Path(path).name}: {exc}")
            self._refresh_batch_list()
            return failures

        def _report_batch_import_failures(self, failures: list[str]) -> None:
            if failures:
                show_error(
                    Adw,
                    self,
                    "Some images could not be added",
                    f"{len(failures)} file(s) were not added to the batch queue.",
                    "\n".join(failures),
                )

        def _refresh_batch_list(self) -> None:
            while (child := self.batch_list.get_first_child()) is not None:
                self.batch_list.remove(child)
            for item in self.batch_items:
                row = Gtk.ListBoxRow()
                dimensions = (
                    f"{item.dimensions[0]}x{item.dimensions[1]}"
                    if item.dimensions
                    else "unknown size"
                )
                output = Path(item.proposed_output).name if item.proposed_output else "not assigned"
                details = (
                    f"{Path(item.source_path).name} | {dimensions} | "
                    f"{item.source_format or 'unknown'} | {output} | {item.status}"
                )
                if item.message:
                    details = f"{details} | {item.message}"
                row.set_child(Gtk.Label(label=details, xalign=0, wrap=True))
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
                seen = set()
                for item in self.batch_items:
                    output = Path(item.proposed_output or "")
                    if output.exists() or output in seen:
                        item.status = BatchStatus.SKIPPED
                    seen.add(output)
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
                show_suffix_dialog(
                    Adw,
                    Gtk,
                    self,
                    snapshot.suffix,
                    lambda suffix: self._apply_custom_suffix(suffix, snapshot),
                )
                return
            self._run_batch(snapshot)

        def _apply_custom_suffix(self, suffix: str | None, snapshot: BatchSnapshot) -> None:
            if not suffix:
                return
            snapshot = replace(snapshot, suffix=suffix)
            conflicts = preflight_outputs(self.batch_items, snapshot)
            if conflicts.has_conflicts:
                show_conflict_dialog(
                    Adw, self, lambda choice: self._apply_conflict_choice(choice, snapshot)
                )
                return
            self.suffix_row.set_text(suffix)
            self._run_batch(snapshot)

        def _run_batch(self, snapshot: BatchSnapshot) -> None:
            try:
                self.batch_runner.start(self.batch_items, snapshot, callback=self._batch_event)
                self._set_busy(True)
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
                item_number = self.batch_runner.current_index + 1
                item_total = len(self.batch_items)
                row_fraction = payload.get("done", 0) / max(1, payload.get("total", 1))
                overall = ((item_number - 1) + row_fraction) / max(1, item_total)
                summary = self.batch_runner.summary
                self.status_label.set_text(
                    f"Processing {item_number} of {item_total}: {Path(item.source_path).name} | "
                    f"{summary.completed} completed, {summary.skipped} skipped, "
                    f"{summary.failed} failed"
                )
                self.progress.set_visible(True)
                self.progress.set_fraction(overall)
            elif event == "finished":
                summary = payload.get("summary")
                self.status_label.set_text(
                    f"Batch complete: {summary.completed} completed, {summary.skipped} skipped, "
                    f"{summary.failed} failed, {summary.cancelled} cancelled."
                )
                self.progress.set_visible(False)
                self.cancel_button.set_visible(False)
                self._set_busy(False)

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
                dialog.set_filters(filters)
                dialog.set_default_filter(filters.get_item(0))
            if multiple:
                dialog.open_multiple(self, None, callback)
            else:
                dialog.open(self, None, callback)

        def _save_dialog(self, title, initial_name, callback, *, export_filter=False) -> None:
            dialog = Gtk.FileDialog(title=title, initial_name=initial_name)
            if export_filter:
                filters = Gio.ListStore.new(Gtk.FileFilter)
                png_filter = Gtk.FileFilter(name="PNG image")
                png_filter.add_mime_type("image/png")
                png_filter.add_pattern("*.png")
                jpeg_filter = Gtk.FileFilter(name="JPEG image")
                jpeg_filter.add_mime_type("image/jpeg")
                jpeg_filter.add_pattern("*.jpg")
                jpeg_filter.add_pattern("*.jpeg")
                filters.append(png_filter)
                filters.append(jpeg_filter)
                dialog.set_filters(filters)
                dialog.set_default_filter(png_filter)
            dialog.save(self, None, callback)

        def _folder_dialog(self, title, callback) -> None:
            dialog = Gtk.FileDialog(title=title)
            dialog.select_folder(self, None, callback)

        def _restore_settings(self) -> None:
            try:
                values = self.store.get("last-processing-settings", {})
                if values:
                    from chromasunder.core.models import PixelSortSettings

                    self.editor.settings_controller.restore(PixelSortSettings.from_dict(values))
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

        def _persist(self, key: str, value) -> None:
            try:
                self.store.set(key, value)
            except Exception:
                pass

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
