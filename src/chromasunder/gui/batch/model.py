"""Batch queue data structures and conflict preflight."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python 3.10 compatibility

    class StrEnum(str, Enum):
        def __str__(self) -> str:
            return self.value


from collections.abc import Iterable
from pathlib import Path

from chromasunder.core.enums import IntervalFunction
from chromasunder.core.imaging import normalize_binary_image, normalize_image
from chromasunder.core.models import PixelSortSettings
from chromasunder.core.validation import ValidationError


class OutputMode(StrEnum):
    PNG = "png"
    PRESERVE = "preserve"


class ConflictPolicy(StrEnum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    NUMERIC_SUFFIX = "numeric-suffix"


class BatchStatus(StrEnum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    SKIPPED = "Skipped"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


@dataclass(slots=True)
class BatchItem:
    source_path: str
    dimensions: tuple[int, int] | None = None
    source_format: str | None = None
    proposed_output: str | None = None
    status: BatchStatus = BatchStatus.PENDING
    message: str = ""


@dataclass(frozen=True, slots=True)
class BatchSnapshot:
    settings: PixelSortSettings
    output_folder: str
    output_mode: OutputMode = OutputMode.PNG
    mask_path: str | None = None
    interval_path: str | None = None
    jpeg_quality: int = 95
    jpeg_background: str = "black"
    suffix: str = "_pxsorted"
    conflict_policy: ConflictPolicy = ConflictPolicy.SKIP


@dataclass(slots=True)
class BatchSummary:
    total: int
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    cancelled: int = 0


@dataclass(frozen=True, slots=True)
class ConflictReport:
    conflicts: tuple[Path, ...] = ()

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)


def inspect_item(path: str | Path) -> BatchItem:
    normalized = normalize_image(path)
    try:
        return BatchItem(str(path), normalized.dimensions, normalized.format)
    finally:
        normalized.image.close()


def _extension(item: BatchItem, mode: OutputMode) -> str:
    if mode is OutputMode.PRESERVE and item.source_format in {"PNG", "JPEG"}:
        return ".jpg" if item.source_format == "JPEG" else ".png"
    return ".png"


def build_output_path(item: BatchItem, snapshot: BatchSnapshot, suffix: str | None = None) -> Path:
    source = Path(item.source_path)
    chosen_suffix = snapshot.suffix if suffix is None else suffix
    return (
        Path(snapshot.output_folder).expanduser()
        / f"{source.stem}{chosen_suffix}{_extension(item, snapshot.output_mode)}"
    )


def assign_proposed_outputs(
    items: Iterable[BatchItem], snapshot: BatchSnapshot, suffix: str | None = None
) -> None:
    for item in items:
        item.proposed_output = str(build_output_path(item, snapshot, suffix))


def preflight_outputs(items: Iterable[BatchItem], snapshot: BatchSnapshot) -> ConflictReport:
    materialized = list(items)
    assign_proposed_outputs(materialized, snapshot)
    seen: set[Path] = set()
    conflicts: list[Path] = []
    for item in materialized:
        path = Path(item.proposed_output or build_output_path(item, snapshot))
        if path.exists() or path in seen:
            conflicts.append(path)
        seen.add(path)
    return ConflictReport(tuple(dict.fromkeys(conflicts)))


def numeric_suffix_path(path: str | Path, used: set[Path] | None = None) -> Path:
    candidate = Path(path)
    used_paths = used or set()
    if not candidate.exists() and candidate not in used_paths:
        return candidate
    index = 1
    while True:
        numbered = candidate.with_name(f"{candidate.stem}_{index}{candidate.suffix}")
        if not numbered.exists() and numbered not in used_paths:
            return numbered
        index += 1


def validate_batch_dimensions(items: Iterable[BatchItem], snapshot: BatchSnapshot) -> None:
    materialized = list(items)
    if not materialized:
        raise ValidationError("Add at least one image to the batch queue.", "empty-batch")
    dimensions = []
    for item in materialized:
        if item.dimensions is None:
            inspected = inspect_item(item.source_path)
            item.dimensions = inspected.dimensions
            item.source_format = inspected.source_format
        dimensions.append(item.dimensions)
    if snapshot.mask_path or snapshot.interval_path:
        first = dimensions[0]
        if any(value != first for value in dimensions):
            raise ValidationError(
                "Shared mask and interval images require identical input dimensions.",
                "dimension-mismatch",
            )
        if snapshot.mask_path:
            mask = normalize_binary_image(snapshot.mask_path, first)
            mask.close()
        if snapshot.interval_path:
            interval = normalize_binary_image(snapshot.interval_path, first)
            interval.close()
    if (
        snapshot.settings.interval_function in (IntervalFunction.FILE, IntervalFunction.FILE_EDGES)
        and not snapshot.interval_path
    ):
        raise ValidationError(
            "An interval image is required for the selected interval function.",
            "missing-interval-image",
        )
