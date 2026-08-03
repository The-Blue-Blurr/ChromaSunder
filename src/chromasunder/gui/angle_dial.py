"""Circular GTK angle input and dependency-free dial geometry."""

from __future__ import annotations

import math


def normalize_angle(angle: float, *, preserve_full_turn: bool = False) -> float:
    """Return an equivalent angle in the dial's zero-to-360-degree range."""
    value = float(angle)
    normalized = value % 360.0
    if preserve_full_turn and value > 0.0 and math.isclose(normalized, 0.0, abs_tol=1e-9):
        return 360.0
    return normalized


def angle_from_point(x: float, y: float, center_x: float, center_y: float) -> float:
    """Convert a screen coordinate to an angle with zero at right and 90 at top."""
    return normalize_angle(math.degrees(math.atan2(center_y - y, x - center_x)))


def point_for_angle(
    angle: float, center_x: float, center_y: float, radius: float
) -> tuple[float, float]:
    """Return the screen coordinate for an angle on a circle."""
    radians = math.radians(normalize_angle(angle))
    return center_x + radius * math.cos(radians), center_y - radius * math.sin(radians)


try:
    import gi

    gi.require_version("Gdk", "4.0")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gdk, Gtk
except ImportError:  # pragma: no cover - allows geometry tests on non-GTK hosts
    Gdk = Gtk = None


if Gtk is not None:

    class AngleDial(Gtk.DrawingArea):
        """A compact circular angle control backed by a Gtk.Adjustment."""

        def __init__(self, adjustment) -> None:
            super().__init__()
            self.adjustment = adjustment
            self._drag_origin = (0.0, 0.0)
            self.set_content_width(104)
            self.set_content_height(104)
            self.set_focusable(True)
            self.set_tooltip_text(
                "Drag to choose an angle. Use the adjacent number field for exact input."
            )
            self.set_draw_func(self._draw)
            self.connect("notify::has-focus", lambda *_args: self.queue_draw())

            drag = Gtk.GestureDrag.new()
            drag.connect("drag-begin", self._drag_begin)
            drag.connect("drag-update", self._drag_update)
            self.add_controller(drag)

            keys = Gtk.EventControllerKey.new()
            keys.connect("key-pressed", self._key_pressed)
            self.add_controller(keys)

            self.adjustment.connect("notify::value", lambda *_args: self.queue_draw())

        def _set_from_point(self, x: float, y: float) -> None:
            center_x = self.get_width() / 2.0
            center_y = self.get_height() / 2.0
            if math.hypot(x - center_x, y - center_y) < 3.0:
                return
            self.adjustment.set_value(round(angle_from_point(x, y, center_x, center_y)))

        def _drag_begin(self, _gesture, x: float, y: float) -> None:
            self._drag_origin = (x, y)
            self.grab_focus()
            self._set_from_point(x, y)

        def _drag_update(self, _gesture, offset_x: float, offset_y: float) -> None:
            self._set_from_point(
                self._drag_origin[0] + offset_x,
                self._drag_origin[1] + offset_y,
            )

        def _key_pressed(self, _controller, keyval, _keycode, state) -> bool:
            step = 15.0 if state & Gdk.ModifierType.SHIFT_MASK else 1.0
            if keyval in (Gdk.KEY_Right, Gdk.KEY_Up):
                self.adjustment.set_value(min(360.0, self.adjustment.get_value() + step))
            elif keyval in (Gdk.KEY_Left, Gdk.KEY_Down):
                self.adjustment.set_value(max(0.0, self.adjustment.get_value() - step))
            elif keyval == Gdk.KEY_Home:
                self.adjustment.set_value(0.0)
            elif keyval == Gdk.KEY_End:
                self.adjustment.set_value(360.0)
            else:
                return False
            return True

        def _draw(self, _area, context, width: int, height: int) -> None:
            center_x = width / 2.0
            center_y = height / 2.0
            radius = max(1.0, min(width, height) / 2.0 - 18.0)
            foreground = self.get_style_context().get_color()

            context.set_source_rgba(
                foreground.red,
                foreground.green,
                foreground.blue,
                0.55,
            )
            context.set_line_width(1.5)
            context.arc(center_x, center_y, radius, 0.0, math.tau)
            context.stroke()

            for angle in (0.0, 90.0, 180.0, 270.0):
                inner = point_for_angle(angle, center_x, center_y, radius - 5.0)
                outer = point_for_angle(angle, center_x, center_y, radius + 3.0)
                context.move_to(*inner)
                context.line_to(*outer)
                context.stroke()

            context.select_font_face("Sans")
            context.set_font_size(8.0)
            for angle, label in ((0, "0"), (90, "90"), (180, "180"), (270, "270")):
                label_x, label_y = point_for_angle(angle, center_x, center_y, radius + 11.0)
                extents = context.text_extents(label)
                context.move_to(
                    label_x - extents.x_bearing - extents.width / 2.0,
                    label_y - extents.y_bearing - extents.height / 2.0,
                )
                context.show_text(label)

            found, accent = self.get_style_context().lookup_color("accent_color")
            if not found:
                accent = foreground
            indicator = point_for_angle(
                self.adjustment.get_value(), center_x, center_y, radius - 6.0
            )
            context.set_source_rgba(accent.red, accent.green, accent.blue, accent.alpha)
            context.set_line_width(3.0)
            context.move_to(center_x, center_y)
            context.line_to(*indicator)
            context.stroke()
            context.arc(indicator[0], indicator[1], 5.0, 0.0, math.tau)
            context.fill()
            context.arc(center_x, center_y, 3.0, 0.0, math.tau)
            context.fill()

            if self.has_focus():
                context.set_source_rgba(accent.red, accent.green, accent.blue, 0.8)
                context.set_line_width(2.0)
                context.arc(center_x, center_y, radius + 8.0, 0.0, math.tau)
                context.stroke()

else:
    AngleDial = None
