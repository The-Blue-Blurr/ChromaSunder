"""Mathematically explicit pixel sorting keys."""

from __future__ import annotations

import colorsys
from collections.abc import Sequence

from .enums import SortingFunction


def sorting_key(pixel: Sequence[int], function: SortingFunction | str) -> float:
    """Return a stable ascending key for an RGB or RGBA pixel."""

    selected = SortingFunction(function)
    red, green, blue = (channel / 255.0 for channel in pixel[:3])
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    if selected is SortingFunction.LIGHTNESS:
        return lightness
    if selected is SortingFunction.HUE:
        return hue
    if selected is SortingFunction.SATURATION:
        return saturation
    if selected is SortingFunction.INTENSITY:
        return (red + green + blue) / 3.0
    if selected is SortingFunction.MINIMUM:
        return min(red, green, blue)
    raise ValueError(f"Unsupported sorting function: {function}")
