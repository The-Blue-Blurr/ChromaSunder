import pytest
from PIL import Image

from chromasunder.core.validation import ValidationError
from chromasunder.gui.batch.model import inspect_item
from chromasunder.gui.editor_controller import EditorController
from chromasunder.gui.file_import import local_paths


class FakeFile:
    def __init__(self, path, name):
        self.path = path
        self.name = name

    def get_path(self):
        return self.path

    def get_parse_name(self):
        return self.name


def test_local_paths_separates_non_local_files():
    paths, non_local = local_paths(
        [
            FakeFile("/tmp/first.png", "first.png"),
            FakeFile(None, "sftp://example/image.jpg"),
            FakeFile("/tmp/second.jpg", "second.jpg"),
        ]
    )

    assert paths == ["/tmp/first.png", "/tmp/second.jpg"]
    assert non_local == ["sftp://example/image.jpg"]


def test_local_paths_accepts_an_empty_drop():
    assert local_paths([]) == ([], [])


def test_source_and_batch_import_accept_supported_images(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (3, 2), "red").save(source)

    editor = EditorController()
    editor.open_source(str(source))
    item = inspect_item(source)

    assert editor.state.source_path == str(source.resolve())
    assert item.dimensions == (3, 2)
    assert item.source_format == "PNG"


def test_source_and_batch_import_reject_unsupported_images(tmp_path):
    source = tmp_path / "source.bmp"
    Image.new("RGB", (3, 2), "red").save(source)

    with pytest.raises(ValidationError, match="Only PNG and JPEG"):
        EditorController().open_source(str(source))
    with pytest.raises(ValidationError, match="Only PNG and JPEG"):
        inspect_item(source)


def test_opening_a_new_source_removes_the_previous_render(tmp_path):
    source = tmp_path / "source.png"
    cache = tmp_path / "cache.png"
    preview = tmp_path / "preview.png"
    Image.new("RGB", (3, 2), "red").save(source)
    cache.touch()
    preview.touch()
    editor = EditorController()
    editor.state.cache_path = str(cache)
    editor.state.preview_path = str(preview)

    editor.open_source(str(source))

    assert not cache.exists()
    assert not preview.exists()
