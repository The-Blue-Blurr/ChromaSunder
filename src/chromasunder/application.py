"""Application bootstrap."""

from __future__ import annotations

import logging

from chromasunder import __version__

LOGGER = logging.getLogger(__name__)


def main() -> int:
    from chromasunder.logging_setup import configure_logging

    configure_logging()
    LOGGER.info("Starting ChromaSunder %s", __version__)
    try:
        import gi

        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gio, Gtk
    except ImportError as exc:
        raise SystemExit(
            "ChromaSunder requires GTK 4, libadwaita, PyGObject, and Pillow. "
            "Install the Fedora desktop dependencies before launching it."
        ) from exc

    from chromasunder.gui.main_window import MainWindow

    class Application(Adw.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id="io.github.the_blue_blurr.ChromaSunder",
                flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            )
            self.connect("activate", self._activate)
            self.connect("startup", self._startup)

        def _startup(self, _application) -> None:
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            about = Gio.SimpleAction.new("about", None)
            about.connect("activate", lambda _action, _parameter: self._about())
            self.add_action(about)
            quit_action = Gio.SimpleAction.new("quit", None)
            quit_action.connect("activate", lambda _action, _parameter: self.quit())
            self.add_action(quit_action)
            self.set_accels_for_action("app.quit", ["<Primary>q"])

        def _activate(self, application) -> None:
            window = self.get_active_window()
            if window is None:
                window = MainWindow(application)
            window.present()

        def _about(self) -> None:
            window = self.get_active_window()
            about = Adw.AboutDialog(
                application_name="Chroma Sunder",
                application_icon="io.github.the_blue_blurr.ChromaSunder",
                version=__version__,
                developer_name="The-Blue-Blurr",
                comments="A modernized pixel sorting application for Fedora GNOME.",
                website="https://github.com/The-Blue-Blurr/ChromaSunder",
                license_type=Gtk.License.MIT_X11,
                developers=["The-Blue-Blurr", "Satyarth and the original Pixelsort contributors"],
                designers=["Kim Asendorf, foundational ASDFPixelSort inspiration"],
            )
            about.present(window)

    return Application().run(None)
