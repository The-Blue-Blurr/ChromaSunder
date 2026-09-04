import 'chromasunder_native_bindings_generated.dart' as bindings;

/// Handwritten boundary above generated C ABI bindings.
class NativeSmokeService {
  const NativeSmokeService();

  int get abiVersion => bindings.cs_abi_version();

  int add(int a, int b) => bindings.cs_smoke_add(a, b);
}
