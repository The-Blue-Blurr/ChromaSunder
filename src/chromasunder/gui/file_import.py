"""Helpers shared by GTK file-dialog and drag-and-drop imports."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class FileReference(Protocol):
    def get_path(self) -> str | None: ...

    def get_parse_name(self) -> str: ...


def local_paths(files: Iterable[FileReference]) -> tuple[list[str], list[str]]:
    """Split file references into local paths and unsupported non-local names."""

    paths: list[str] = []
    non_local: list[str] = []
    for file in files:
        path = file.get_path()
        if path:
            paths.append(path)
        else:
            non_local.append(file.get_parse_name())
    return paths, non_local
