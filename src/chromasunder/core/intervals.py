"""Interval detection for the seven supported processing modes."""

from __future__ import annotations

import random
from collections.abc import Sequence

from .enums import IntervalFunction
from .sorting import sorting_key


def _luminance(pixel: Sequence[int]) -> float:
    return sorting_key(pixel, "lightness")


def _runs(flags: Sequence[bool], *, minimum_length: int = 2) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    start: int | None = None
    for index, enabled in enumerate(flags):
        if enabled and start is None:
            start = index
        elif not enabled and start is not None:
            if index - start >= minimum_length:
                intervals.append((start, index))
            start = None
    if start is not None and len(flags) - start >= minimum_length:
        intervals.append((start, len(flags)))
    return intervals


def _edge_intervals(row: Sequence[Sequence[int]], threshold: float) -> list[tuple[int, int]]:
    if len(row) < 2:
        return []
    boundaries = [0]
    previous = _luminance(row[0])
    for index in range(1, len(row)):
        current = _luminance(row[index])
        if abs(current - previous) >= threshold:
            boundaries.append(index)
        previous = current
    boundaries.append(len(row))
    return [
        (start, end)
        for start, end in zip(boundaries, boundaries[1:], strict=False)
        if end - start >= 2
    ]


def _random_intervals(
    length: int, characteristic_length: int, rng: random.Random
) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    start = 0
    while start < length:
        size = max(1, int(characteristic_length * rng.random()))
        end = min(length, start + size)
        if end - start >= 2:
            intervals.append((start, end))
        start = end
    return intervals


def _wave_intervals(
    length: int, characteristic_length: int, rng: random.Random
) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    start = 0
    while start < length:
        end = min(length, start + characteristic_length + rng.randint(0, 10))
        if end - start >= 2:
            intervals.append((start, end))
        start = end
    return intervals


def detect_intervals(
    row: Sequence[Sequence[int]],
    function: IntervalFunction | str,
    lower_threshold: float,
    upper_threshold: float,
    characteristic_length: int,
    rng: random.Random,
    interval_row: Sequence[int] | None = None,
) -> list[tuple[int, int]]:
    """Return half-open intervals for one row."""

    selected = IntervalFunction(function)
    if selected is IntervalFunction.THRESHOLD:
        flags = [lower_threshold <= _luminance(pixel) <= upper_threshold for pixel in row]
        return _runs(flags)
    if selected is IntervalFunction.EDGES:
        return _edge_intervals(row, lower_threshold)
    if selected is IntervalFunction.RANDOM:
        return _random_intervals(len(row), characteristic_length, rng)
    if selected is IntervalFunction.WAVES:
        return _wave_intervals(len(row), characteristic_length, rng)
    if selected is IntervalFunction.NONE:
        return [(0, len(row))] if len(row) >= 2 else []
    if selected is IntervalFunction.FILE:
        flags = [bool(value) for value in (interval_row or ())]
        return _runs(flags)
    if selected is IntervalFunction.FILE_EDGES:
        values = [1.0 if value else 0.0 for value in (interval_row or ())]
        if not values:
            return []
        boundaries = [0]
        previous = 0.0
        for index, current in enumerate(values):
            if abs(current - previous) >= lower_threshold:
                boundaries.append(index)
            previous = current
        boundaries.append(len(values))
        boundaries = list(dict.fromkeys(boundaries))
        return [
            (start, end)
            for start, end in zip(boundaries, boundaries[1:], strict=False)
            if end - start >= 2
        ]
    raise ValueError(f"Unsupported interval function: {function}")


def interval_sort_key(pixel: Sequence[int]) -> float:
    """Small helper useful to callers that inspect interval brightness."""

    return sorting_key(pixel, "lightness")
