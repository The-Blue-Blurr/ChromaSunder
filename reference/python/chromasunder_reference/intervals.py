import random
from collections.abc import Sequence

from .enums import IntervalFunction
from .sorting import sorting_key


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


def detect_intervals(
    row: Sequence[Sequence[int]],
    function: IntervalFunction | str,
    lower_threshold: float,
    upper_threshold: float,
    characteristic_length: int,
    rng: random.Random,
    interval_row: Sequence[int] | None = None,
) -> list[tuple[int, int]]:
    selected = IntervalFunction(function)

    def luminance(pixel: Sequence[int]) -> float:
        return sorting_key(pixel, "lightness")

    if selected is IntervalFunction.THRESHOLD:
        return _runs([lower_threshold <= luminance(pixel) <= upper_threshold for pixel in row])
    if selected is IntervalFunction.EDGES:
        if len(row) < 2:
            return []
        boundaries = [0]
        previous = luminance(row[0])
        for index in range(1, len(row)):
            current = luminance(row[index])
            if abs(current - previous) >= lower_threshold:
                boundaries.append(index)
            previous = current
        boundaries.append(len(row))
        return [
            (start, end)
            for start, end in zip(boundaries, boundaries[1:], strict=False)
            if end - start >= 2
        ]
    if selected is IntervalFunction.RANDOM:
        intervals = []
        start = 0
        while start < len(row):
            size = max(1, int(characteristic_length * rng.random()))
            end = min(len(row), start + size)
            if end - start >= 2:
                intervals.append((start, end))
            start = end
        return intervals
    if selected is IntervalFunction.WAVES:
        intervals = []
        start = 0
        while start < len(row):
            end = min(len(row), start + characteristic_length + rng.randint(0, 10))
            if end - start >= 2:
                intervals.append((start, end))
            start = end
        return intervals
    if selected is IntervalFunction.NONE:
        return [(0, len(row))] if len(row) >= 2 else []
    if selected is IntervalFunction.FILE:
        return _runs([bool(value) for value in (interval_row or ())])
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
