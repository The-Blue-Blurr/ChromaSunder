"""Reusable libadwaita dialogs."""

from __future__ import annotations

from collections.abc import Callable


def show_error(Adw, parent, title: str, message: str, details: str | None = None) -> None:
    dialog = Adw.AlertDialog.new(title, message)
    if details:
        dialog.set_body_use_markup(False)
        dialog.set_extra_child(None)
        message = f"{message}\n\nTechnical details:\n{details}"
        dialog.set_body(message)
    dialog.add_response("ok", "OK")
    dialog.set_default_response("ok")
    dialog.present(parent)


def show_stale_export_dialog(Adw, parent, on_choice: Callable[[str], None]) -> None:
    dialog = Adw.AlertDialog.new(
        "The settings have changed since this preview was rendered.",
        "Choose how you want to continue exporting.",
    )
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("existing", "Export Existing Render")
    dialog.add_response("render", "Render Current Settings and Export")
    dialog.set_response_appearance("render", Adw.ResponseAppearance.SUGGESTED)
    dialog.choose(None, lambda _dialog, result: on_choice(dialog.choose_finish(result)))
    dialog.present(parent)


def show_no_render_dialog(Adw, parent, on_choice: Callable[[str], None]) -> None:
    dialog = Adw.AlertDialog.new(
        "No rendered image is available.", "Render the current settings before exporting?"
    )
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("render", "Render and Export")
    dialog.set_response_appearance("render", Adw.ResponseAppearance.SUGGESTED)
    dialog.choose(None, lambda _dialog, result: on_choice(dialog.choose_finish(result)))
    dialog.present(parent)


def show_conflict_dialog(Adw, parent, on_choice: Callable[[str], None]) -> None:
    dialog = Adw.AlertDialog.new(
        "Some batch outputs already exist.",
        "Choose one policy for the complete batch.",
    )
    for identifier, label in (
        ("cancel", "Cancel"),
        ("suffix", "Use Different Filename Suffix"),
        ("numeric", "Add Numeric Suffix"),
        ("skip", "Skip Existing"),
        ("overwrite", "Overwrite Existing"),
    ):
        dialog.add_response(identifier, label)
    dialog.set_response_appearance("overwrite", Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.choose(None, lambda _dialog, result: on_choice(dialog.choose_finish(result)))
    dialog.present(parent)
