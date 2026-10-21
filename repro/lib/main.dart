import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:rive/rive.dart' as rive;

const runLabel = String.fromEnvironment('RUN_LABEL', defaultValue: 'newest');
const isWasm = bool.fromEnvironment('dart.tool.dart2wasm');

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MaterialApp(home: Repro()));
}

class Repro extends StatefulWidget {
  const Repro({super.key});

  @override
  State<Repro> createState() => _ReproState();
}

class _ReproState extends State<Repro> {
  final lines = <String>[];
  final retained = <rive.File>[];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => run());
  }

  void log(String message) {
    // ignore: avoid_print
    print('[repro] $message');
    setState(() => lines.add(message));
  }

  void check(String name, Object? Function() read) {
    try {
      log('PASS $name: ${read()}');
    } catch (error, stack) {
      log('FAIL $name: $error');
      // ignore: avoid_print
      print('[repro] STACK $name\n$stack');
    }
  }

  Future<rive.File> load(String name) async {
    final data = await rootBundle.load('assets/$name');
    log('LOAD $name bytes=${data.lengthInBytes}');
    final file = await rive.File.decode(
      data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes),
      riveFactory: rive.Factory.rive,
    );
    if (file == null) throw StateError('Could not decode $name');
    retained.add(file);
    log('LOADED $name viewModels=${file.viewModelCount}');
    return file;
  }

  void readEnums(rive.File file, String stage) {
    check('$stage file.enums', () {
      final enums = file.enums;
      if (enums.isEmpty) throw StateError('Fixture must contain an enum');
      // Force element access: merely asking for values.length masks bug A.
      return enums
          .map((e) => '${e.name}=${List<String>.of(e.values)}')
          .join('; ');
    });
  }

  void readPaths(rive.ViewModelInstance instance, String stage) {
    check('$stage number(Coin/Item_Value)', () {
      final number = instance.number('Coin/Item_Value');
      if (number == null) throw StateError('Missing number');
      try {
        return number.value;
      } finally {
        number.dispose();
      }
    });
    check('$stage enumerator(Item_Selection/Item_Selection)', () {
      final value = instance.enumerator('Item_Selection/Item_Selection');
      if (value == null) throw StateError('Missing enumerator');
      try {
        return value.value;
      } finally {
        value.dispose();
      }
    });
  }

  Future<void> run() async {
    log('START label=$runLabel compiler=${isWasm ? 'dart2wasm' : 'dart2js'}');
    try {
      log('INIT ${await rive.RiveNative.init()}');
      final small = await load('rewards.riv');
      final artboard = small.defaultArtboard()!;
      final model = small.defaultArtboardViewModel(artboard)!;
      log('MODEL ${model.name}');
      final instance = model.createDefaultInstance()!;
      readPaths(instance, 'before');
      readEnums(small, 'before');
      // Retain each decoded file so allocations accumulate. A single large
      // file may fit in the runtime's initial heap without growing memory.
      for (var i = 1; i <= 12; i++) {
        await load('semantics.riv');
        readPaths(instance, 'after large $i');
      }
      readEnums(small, 'after');
      readPaths(instance, 'retry');
      instance.dispose();
      model.dispose();
      artboard.dispose();
    } catch (error, stack) {
      log('FATAL $error');
      // ignore: avoid_print
      print('[repro] STACK fatal\n$stack');
    } finally {
      for (final file in retained.reversed) {
        file.dispose();
      }
      log('DONE');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Rive web interop reproduction')),
    body: SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: SelectableText(
        lines.join('\n'),
        style: const TextStyle(fontSize: 14),
      ),
    ),
  );
}
