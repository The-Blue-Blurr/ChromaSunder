"""Mathematically explicit pixel sorting keys."""

from __future__ import annotations

import colorsys
from collections.abc import Callable, Sequence

from .enums import SortingFunction

Pixel = Sequence[int]
SortingKey = Callable[[Pixel], float | int]


def _lightness_key(pixel: Pixel) -> int:
    red, green, blue = pixel[:3]
    return max(red, green, blue) + min(red, green, blue)


def _hue_key(pixel: Pixel) -> float:
    red, green, blue = (channel / 255.0 for channel in pixel[:3])
    return colorsys.rgb_to_hls(red, green, blue)[0]


def _saturation_key(pixel: Pixel) -> float:
    red, green, blue = (channel / 255.0 for channel in pixel[:3])
    return colorsys.rgb_to_hls(red, green, blue)[2]


def _intensity_key(pixel: Pixel) -> int:
    return pixel[0] + pixel[1] + pixel[2]


def _minimum_key(pixel: Pixel) -> int:
    return min(pixel[0], pixel[1], pixel[2])


_SORTING_KEYS: dict[SortingFunction, SortingKey] = {
    SortingFunction.LIGHTNESS: _lightness_key,
    SortingFunction.HUE: _hue_key,
    SortingFunction.SATURATION: _saturation_key,
    SortingFunction.INTENSITY: _intensity_key,
    SortingFunction.MINIMUM: _minimum_key,
}


def sorting_key_function(function: SortingFunction | str) -> SortingKey:
    """Resolve a sort key once for use in the rendering hot path."""

    return _SORTING_KEYS[SortingFunction(function)]


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
