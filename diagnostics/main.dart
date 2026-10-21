import 'dart:js_interop';
import 'dart:js_interop_unsafe';

@JS('probeMemory')
external JSObject get memory;
@JS('probeView')
external JSUint8Array get view;

void main() {
  final values = <JSString>['Coin'.toJS, 'Gem'.toJS].toJS.toDart;
  try {
    print('[repro] old enum cast: ${values.cast<String>().first}');
  } catch (error) {
    print('[repro] old enum cast error: $error');
  }
  print('[repro] converted enum: ${values.map((e) => e.toDart).toList()}');
  final data = view.toDart;
  print('[repro] before grow Dart length=${data.length} isEmpty=${data.isEmpty} bufferBytes=${data.buffer.lengthInBytes}');
  memory.callMethod<JSNumber>('grow'.toJS, 1.toJS);
  print('[repro] after grow JS length=${view.getProperty<JSNumber>('length'.toJS).toDartInt} Dart length=${data.length} isEmpty=${data.isEmpty} bufferBytes=${data.buffer.lengthInBytes}');
  try {
    data[0] = 42;
    print('[repro] stale write returned ${data[0]}');
  } catch (error) {
    print('[repro] stale write error: $error');
  }
  print('[repro] DONE');
}
