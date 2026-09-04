import 'package:chromasunder_native/chromasunder_native.dart';
import 'package:flutter/material.dart';

void main() => runApp(const ChromaSunderApp());

class ChromaSunderApp extends StatelessWidget {
  const ChromaSunderApp({
    super.key,
    this.nativeService = const NativeSmokeService(),
  });

  final NativeSmokeService nativeService;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Chroma Sunder',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6E3CBC),
          brightness: Brightness.dark,
        ),
      ),
      home: Scaffold(
        appBar: AppBar(title: const Text('Chroma Sunder V2')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Native engine connected'),
              const SizedBox(height: 12),
              Text('ABI ${nativeService.abiVersion}'),
              Text('Smoke result: ${nativeService.add(20, 22)}'),
            ],
          ),
        ),
      ),
    );
  }
}
