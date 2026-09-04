import 'package:chromasunder_native/chromasunder_native.dart';
import 'package:test/test.dart';

void main() {
  const service = NativeSmokeService();

  test('reports the engine ABI version', () {
    expect(service.abiVersion, 1);
  });

  test('calls through Dart FFI to C++', () {
    expect(service.add(20, 22), 42);
  });
}
