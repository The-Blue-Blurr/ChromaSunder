"""Small GTK batch queue view. The queue deliberately has no thumbnails or drag handles."""

from __future__ import annotations

from collections.abc import Callable


def build_batch_view(Gtk, Adw, model, callbacks: dict[str, Callable]):
    """Build the collapsible queue widget without embedding processing logic."""

    group = Adw.PreferencesGroup(title="Batch Queue")
    revealer = Gtk.Revealer(reveal_child=False)
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    for label, key in (
        ("Add Images", "add"),
        ("Remove Selected", "remove"),
        ("Clear Queue", "clear"),
        ("Choose Output Folder", "folder"),
        ("Start Batch", "start"),
        ("Cancel Batch", "cancel"),
    ):
        button = Gtk.Button(label=label)
        button.connect("clicked", lambda _button, action=key: callbacks[action]())
        buttons.append(button)
    content.append(buttons)
    list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
    content.append(list_box)
    revealer.set_child(content)
    toggle = Gtk.ToggleButton(label="Batch Queue (0 files)")
    toggle.connect("toggled", lambda button: revealer.set_reveal_child(button.get_active()))
    group.add(toggle)
    group.add(revealer)
    return group, list_box, toggle
