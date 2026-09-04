from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

from chromasunder.core.models import PixelSortSettings
from chromasunder.core.processing import render_file

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "testdata" / "golden-v1" / "manifest.json"
CLI = ROOT / "reference" / "python" / "render_reference.py"


def test_reference_cli_has_no_v1_runtime_imports():
    source = (ROOT / "reference" / "python" / "chromasunder_reference" / "renderer.py").read_text()
    assert "chromasunder.core" not in source
    assert "chromasunder.gui" not in source
    assert "chromasunder.worker" not in source
    assert "gi.repository" not in source


def test_reference_cli_reproduces_manifest(tmp_path):
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["baseline"] == "v1-a5475cb-pillow-11.1.0"
    assert len(manifest["cases"]) >= 20
    for case in manifest["cases"]:
        output = tmp_path / f"{case['name']}.rgba"
        command = [
            sys.executable,
            str(CLI),
            "--source",
            str(ROOT / "testdata" / case["source"]),
            "--settings-json",
            str(ROOT / "testdata" / case["settings"]),
            "--output-rgba",
            str(output),
            "--print-sha256",
        ]
        if case["mask"]:
            command.extend(("--mask", str(ROOT / "testdata" / case["mask"])))
        if case["interval_image"]:
            command.extend(("--interval-image", str(ROOT / "testdata" / case["interval_image"])))
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        assert completed.stdout.strip() == case["rgba_sha256"]
        assert hashlib.sha256(output.read_bytes()).hexdigest() == case["rgba_sha256"]
        assert output.read_bytes() == (ROOT / "testdata" / case["output"]).read_bytes()


def test_manifest_goldens_match_v1_production():
    manifest = json.loads(MANIFEST.read_text())
    for case in manifest["cases"]:
        values = json.loads((ROOT / "testdata" / case["settings"]).read_text())
        rendered = render_file(
            str(ROOT / "testdata" / case["source"]),
            PixelSortSettings.from_dict(values),
            mask_path=str(ROOT / "testdata" / case["mask"]) if case["mask"] else None,
            interval_path=(
                str(ROOT / "testdata" / case["interval_image"]) if case["interval_image"] else None
            ),
        )
        try:
            assert list(rendered.size) == case["dimensions"]
            assert hashlib.sha256(rendered.tobytes()).hexdigest() == case["rgba_sha256"]
        finally:
            rendered.close()


def test_fixture_pngs_are_small():
    for path in (ROOT / "testdata").rglob("*.png"):
        with Image.open(path) as image:
            assert image.width <= 7
            assert image.height <= 5
