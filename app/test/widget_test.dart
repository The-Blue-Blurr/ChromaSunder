import 'package:chromasunder/main.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('displays the native C++ smoke result', (tester) async {
    await tester.pumpWidget(const ChromaSunderApp());

    expect(find.text('Native engine connected'), findsOneWidget);
    expect(find.text('ABI 1'), findsOneWidget);
    expect(find.text('Smoke result: 42'), findsOneWidget);
  });
}
