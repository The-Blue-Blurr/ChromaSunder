import 'package:chromasunder_native/chromasunder_native.dart';
import 'package:flutter/material.dart';

void main() => runApp(const ExampleApp());

class ExampleApp extends StatelessWidget {
  const ExampleApp({super.key});

  @override
  Widget build(BuildContext context) {
    const service = NativeSmokeService();
    return MaterialApp(
      home: Scaffold(
        body: Center(child: Text('Native smoke: ${service.add(20, 22)}')),
      ),
    );
  }
}
