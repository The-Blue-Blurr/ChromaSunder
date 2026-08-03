"""Small GTK batch queue view. The queue deliberately has no thumbnails or drag handles."""

from __future__ import annotations

from collections.abc import Callable


def build_batch_view(Gtk, Adw, model, callbacks: dict[str, Callable]):
    """Build the collapsible queue widget without embedding processing logic."""

    group = Adw.PreferencesGroup(title="Batch Queue")
    revealer = Gtk.Revealer(reveal_child=False)
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    buttons = Gtk.FlowBox()
    buttons.set_column_spacing(6)
    buttons.set_row_spacing(6)
    buttons.set_homogeneous(False)
    buttons.set_min_children_per_line(1)
    buttons.set_max_children_per_line(3)
    buttons.set_selection_mode(Gtk.SelectionMode.NONE)
    for label, key in (
        ("Add Images", "add"),
        ("Remove Selected", "remove"),
        ("Clear Queue", "clear"),
        ("Choose Output Folder", "folder"),
        ("Start Batch", "start"),
        ("Cancel Batch", "cancel"),
    ):
        button = Gtk.Button(label=label)
        button.set_hexpand(False)
        button.connect("clicked", lambda _button, action=key: callbacks[action]())
        buttons.insert(button, -1)
    content.append(buttons)
    content.append(Gtk.Label(label="Drop PNG or JPEG images here", xalign=0))
    list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
    content.append(list_box)
    revealer.set_child(content)
    toggle = Gtk.ToggleButton(label="Batch Queue (0 files)")
    toggle.connect("toggled", lambda button: revealer.set_reveal_child(button.get_active()))
    group.add(toggle)
    group.add(revealer)
    return group, list_box, toggle
