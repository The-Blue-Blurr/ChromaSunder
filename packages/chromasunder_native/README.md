# chromasunder_native

Native-assets package for the Chroma Sunder C++ engine. Generated FFI bindings remain private
behind `NativeSmokeService`.

The build hook compiles the authoritative sources under `../../engine`; it contains no duplicate
engine implementation. Standalone and installable native builds remain defined by
`engine/CMakeLists.txt`. `native_toolchain_c` is used in the hook because it supplies Flutter's
selected Linux, Windows, or Android cross-toolchain directly to the same C++ source.

Regenerate bindings with:

```bash
dart run ffigen --config ffigen.yaml
```
