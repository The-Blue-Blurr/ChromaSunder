# Chroma Sunder V1 Reference Renderer

This temporary package preserves the V1 RGBA8 renderer during the V2 migration. It depends only
on Pillow and the Python standard library and does not import Chroma Sunder's application, GUI,
or worker packages.

Run it from the repository root:

```bash
python reference/python/render_reference.py \
  --source testdata/sources/matrix.png \
  --settings-json testdata/settings/sort-lightness.json \
  --output-rgba /tmp/render.rgba \
  --print-sha256
```

Use `--mask`, `--interval-image`, and `--output` as needed. Output PNGs are deterministic for the
recorded Pillow baseline, while raw RGBA hashes are the primary migration parity contract.
