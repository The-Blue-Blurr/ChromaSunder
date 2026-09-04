import 'dart:io';

import 'package:code_assets/code_assets.dart';
import 'package:hooks/hooks.dart';

Future<void> main(List<String> args) async {
  await build(args, (input, output) async {
    if (!input.config.buildCodeAssets) return;

    final config = input.config.code;
    final engineDirectory = input.packageRoot.resolve('../../engine/');
    final buildDirectory = input.outputDirectory.resolve('cmake-build/');
    final outputDirectory = input.outputDirectory.resolve('native/');
    await Directory.fromUri(buildDirectory).create(recursive: true);
    await Directory.fromUri(outputDirectory).create(recursive: true);

    final cmakeArguments = <String>[
      '-S',
      engineDirectory.toFilePath(),
      '-B',
      buildDirectory.toFilePath(),
      '-DBUILD_TESTING=OFF',
      '-DCHROMASUNDER_NATIVE_ASSET=ON',
      '-DCMAKE_BUILD_TYPE=Release',
      '-DCMAKE_LIBRARY_OUTPUT_DIRECTORY=${outputDirectory.toFilePath()}',
      '-DCMAKE_RUNTIME_OUTPUT_DIRECTORY=${outputDirectory.toFilePath()}',
      '-DCMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE=${outputDirectory.toFilePath()}',
    ];

    if (config.targetOS == OS.android) {
      final compiler = config.cCompiler?.compiler.toFilePath();
      if (compiler == null) {
        throw StateError('Flutter did not provide an Android NDK compiler.');
      }
      final marker =
          '${Platform.pathSeparator}toolchains${Platform.pathSeparator}llvm';
      final markerIndex = compiler.indexOf(marker);
      if (markerIndex < 0) {
        throw StateError('Cannot derive the Android NDK root from $compiler.');
      }
      final ndkRoot = compiler.substring(0, markerIndex);
      final abi = switch (config.targetArchitecture) {
        Architecture.arm => 'armeabi-v7a',
        Architecture.arm64 => 'arm64-v8a',
        Architecture.ia32 => 'x86',
        Architecture.x64 => 'x86_64',
        _ => throw UnsupportedError(
          'Unsupported Android architecture: ${config.targetArchitecture}',
        ),
      };
      cmakeArguments.addAll([
        '-DCMAKE_TOOLCHAIN_FILE=$ndkRoot/build/cmake/android.toolchain.cmake',
        '-DANDROID_ABI=$abi',
        '-DANDROID_PLATFORM=android-${config.android.targetNdkApi}',
        '-DANDROID_STL=c++_static',
      ]);
    } else if (config.targetOS == OS.windows) {
      final platform = switch (config.targetArchitecture) {
        Architecture.x64 => 'x64',
        Architecture.arm64 => 'ARM64',
        _ => throw UnsupportedError(
          'Unsupported Windows architecture: ${config.targetArchitecture}',
        ),
      };
      cmakeArguments.addAll(['-A', platform]);
    }

    await _run('cmake', cmakeArguments);
    await _run('cmake', [
      '--build',
      buildDirectory.toFilePath(),
      '--config',
      'Release',
      '--target',
      'chromasunder_engine',
    ]);

    final libraryName = config.targetOS.dylibFileName('chromasunder_engine');
    final library = outputDirectory.resolve(libraryName);
    if (!File.fromUri(library).existsSync()) {
      throw StateError('CMake did not produce ${library.toFilePath()}.');
    }
    output.assets.code.add(
      CodeAsset(
        package: input.packageName,
        name: 'chromasunder_native_bindings_generated.dart',
        linkMode: DynamicLoadingBundled(),
        file: library,
      ),
    );
    output.dependencies.addAll(
      await Directory.fromUri(engineDirectory)
          .list(recursive: true)
          .where((entry) => entry is File)
          .map((entry) => entry.uri)
          .toList(),
    );
  });
}

Future<void> _run(String executable, List<String> arguments) async {
  final result = await Process.run(executable, arguments);
  if (result.exitCode != 0) {
    stderr
      ..writeln(result.stdout)
      ..writeln(result.stderr);
    throw ProcessException(
      executable,
      arguments,
      'CMake command failed',
      result.exitCode,
    );
  }
}
