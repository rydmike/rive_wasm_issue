# Flutter web dart2wasm: enum conversion and detached heap views in rive_native

Two Dart-to-JavaScript interop failures reproduce on Flutter 3.47.7 / Dart
3.13.5 in headless Chrome with both the latest published prerelease pair and
the latest stable pair. The public reproduction and captures are included here.
Thank you for taking a look.

Following the arrangement in [#665](https://github.com/rive-app/rive-flutter/issues/665),
the suggested correction is offered on a copy of `rive_native 0.2.0-dev.3`
verbatim from pub.dev:
[branch](https://github.com/rydmike/rive_native/tree/fix-wasm-interop),
[two-commit comparison](https://github.com/rydmike/rive_native/compare/main...fix-wasm-interop),
[`.patch`](https://github.com/rydmike/rive_native/compare/main...fix-wasm-interop.patch).
The same patch is included [locally](patch/fix-wasm-interop.patch).

Related reports: [a comment on #628](https://github.com/rive-app/rive-flutter/issues/628#issuecomment-4322984209)
describes the identical detached-buffer error, and [#593](https://github.com/rive-app/rive-flutter/issues/593)
describes Wasm failures in the same view-model APIs, both without a root cause or
a reproduction. This report adds two source causes, a public reproduction and a
suggested correction.

## Issue form entries

The following subsections follow the upstream runtime issue form in order.

### Submission checklist

- [x] I have confirmed the issue is present in the latest version of the `rive` Flutter package
- [x] I have searched the documentation and forums and could not find an answer
- [x] I have searched existing issues and this is not a duplicate

### Description

With Flutter web compiled using `--wasm`, two independent interop failures occur
in `rive_native`:

1. Reading the elements of `file.enums` fails a Dart string type check.
2. After Rive's WebAssembly memory grows, short view-model path lookups write
   through a detached typed-array view and keep failing on subsequent reads.

Expected: enum values are Dart strings (`[Coin, Gem]`), and the number and enum
paths keep returning `1300` and `Gem` before and after memory growth.

Actual, with `rive 0.15.0-dev.3` / `rive_native 0.2.0-dev.3`:

```text
PASS before number(Coin/Item_Value): 1300.0
PASS before enumerator(Item_Selection/Item_Selection): Gem
FAIL before file.enums: Runtime type check failed (details omitted due to --omit-error-details)
PASS after large 9 number(Coin/Item_Value): 1300.0
FAIL after large 10 number(Coin/Item_Value): TypeError: Cannot perform DataView.prototype.setUint8 on a detached or out-of-bounds ArrayBuffer
```

The tenth retained large decode grows Rive's heap from 67,108,864 to 80,543,744
bytes and detaches its previous buffer. The path reads continue to fail after
decodes 11 and 12 and on the final retry. The stable pair (`rive 0.14.11` /
`rive_native 0.1.11`) behaves the same way. Both published pairs pass all 30
reads when compiled with dart2js. With both suggested corrections, all 30 reads
pass under both compilers, including after the same observed heap growth.

The existing report in #628 includes the identical detached-buffer error, and
#593 describes potentially related Wasm API failures. This reproduction isolates
two source causes; it does not establish whether those reports share a cause.

### Reproduction steps / code

The standalone project, public fixtures, scripts and captures are at
https://github.com/rydmike/rive_wasm_issue.

1. Use Flutter 3.47.7 stable / Dart 3.13.5. From `repro/`, run `flutter pub get`.
2. Run `flutter build web --wasm --profile --no-minify-wasm`.
3. From the repository root, run `python3 tool/serve.py repro/build/web --port 8123`.
4. Open http://127.0.0.1:8123 in Chrome. The app runs automatically and writes
   results to the page and console.
5. Compare a build using `flutter build web --profile --no-wasm-dry-run`.

The app decodes public `rewards.riv`, creates the default `Rewards` view-model
instance and reads these values:

```dart
instance.number('Coin/Item_Value')!.value; // 1300
instance.enumerator('Item_Selection/Item_Selection')!.value; // Gem
for (final e in file.enums) {
  print(List<String>.of(e.values)); // Forces element access.
}
```

It retains 12 decodes of public `semantics.riv`, repeating both path reads after
each decode and once more at the end. One large decode fits in the initial heap;
retaining multiple decodes triggers growth through normal allocation. The
capture harness observes `WebAssembly.Memory.grow`; it does not force growth or
change the initial heap. The full matrix and path-dependency instructions are
below.

### Upload your reproduction files / stack trace

Attach `repro.zip`, produced by running `sh tool/make-zip.sh` from a clean,
committed checkout. The script writes the ZIP to the folder above this repository.
It includes the README, project, lockfiles, fixtures, correction patch and full
console/stack captures in `evidence/`.

### Source `.riv` / `.rev` file

Attach the same `repro.zip`. It includes the unchanged public `rewards.riv` and
`semantics.riv` files, their pinned source URLs and SHA-256 hashes in
`repro/assets/provenance.json`, and the full upstream MIT license. No `.rev`
backup is included.

### Screenshots / video

No video. Optionally attach `evidence/newest-wasm.png` and
`evidence/fixed-wasm.png`, which show the console-style results on the page.
The complete text and stacks are in `evidence/newest-wasm.console.log` and
`evidence/fixed-wasm.console.log` in the ZIP.

### Rive Flutter package version

Latest published prereleases: `rive 0.15.0-dev.3` / `rive_native 0.2.0-dev.3`.
Latest stable: `rive 0.14.11` / `rive_native 0.1.11`.
Both pairs reproduce both failures with dart2wasm. Versions checked against
pub.dev on 2026-10-21; the correction is based on `rive_native 0.2.0-dev.3`.

### Flutter version

```text
Flutter 3.47.7 • channel stable • https://github.com/flutter/flutter.git
Framework • revision abaf9c5237 (13 days ago) • 2026-10-08 09:51:21 -0700
Engine • hash d8a2d6c768c334d53e16277f837970ffa1e2de81 (revision deb287481e) (13 days ago) • 2026-10-07 17:09:12.000Z
Tools • Dart 3.13.5 • DevTools 2.60.0
```

### Device

Desktop web, arm64 host; real headless Google Chrome 155.0.8059.85, controlled
with puppeteer-core 25.15.0. Fresh browser process/profile for each capture,
software WebGL enabled with `--enable-unsafe-swiftshader`.

### OS version

macOS 27.0.1, build 26A434, arm64.

### Additional context

`rive_native` does not offer a public repository for a pull request, so the
suggested two-commit correction follows the packaging used in #665: a verbatim
pub.dev baseline, one commit per source defect, and a downloadable patch.

- [Verbatim baseline](https://github.com/rydmike/rive_native/tree/0.2.0-dev.3-verbatim)
- [Correction branch](https://github.com/rydmike/rive_native/tree/fix-wasm-interop)
- [Compare main...fix-wasm-interop](https://github.com/rydmike/rive_native/compare/main...fix-wasm-interop)
- [Download .patch](https://github.com/rydmike/rive_native/compare/main...fix-wasm-interop.patch)
- [Existing identical error in #628](https://github.com/rive-app/rive-flutter/issues/628#issuecomment-4322984209)
- [Potentially related view-model failures in #593](https://github.com/rive-app/rive-flutter/issues/593)

The archive SHA-256 is
`0acff64554fc0973a6624daa0b0c0261ec00cde744df4b9e3daea2fa8a7b85a8`,
checked against pub.dev metadata. The change uses the existing interop helpers,
adds no dependency and retains the disposed-pointer guard. Its performance cost
was not measured. This reproduction covers decoding and data-binding reads;
Rive rendering/animation, native platforms and other browsers were not tested.

## How to run the reproduction

For a single interactive run, use the steps above with Flutter 3.47.7 on `PATH`.
For the exact automated matrix, set `FLUTTER_BIN` to that SDK's `flutter`
executable and `CHROME_PATH` to the installed Chrome executable. The matrix
script verifies Flutter 3.47.7 stable and Dart 3.13.5 before building.

Arrange the two repositories as siblings, with `rive_native` checked out on
`fix-wasm-interop`. From this repository's root:

```sh
npm ci --prefix tool --ignore-scripts --no-audit --no-fund
python3 tool/run-matrix.py build
python3 tool/run-matrix.py capture
python3 tool/summarize.py
```

`FLUTTER_BIN` and `CHROME_PATH` must be exported in the shell. The build stage
uses the sibling branch directly as a relative path dependency for `fixed`.
It makes ignored A-only and B-only copies from the committed Git objects under
`.work/`, rather than editing the pub cache. It restores the project's published
prerelease dependencies and lockfile afterward. The capture stage serves each
build on loopback with isolation headers and launches real headless Chrome.
Generated builds and temporary tooling state are under ignored `.work/`.

For a manual fixed build, select the branch as a path override from the root:

```sh
python3 tool/select-version.py newest --patched ../../rive_native
cd repro
"$FLUTTER_BIN" pub get
"$FLUTTER_BIN" build web --wasm --profile --no-minify-wasm
```

For the stable pair, run `python3 tool/select-version.py stable` from the root,
then `pub get` and rebuild. To restore the default, run
`python3 tool/select-version.py newest`, then `pub get`. Overrides are ignored
and are not part of the public project. The tracked lockfile resolves the
published prerelease pair on Flutter 3.47.7.

To capture any manually served build:

```sh
node tool/capture.mjs http://127.0.0.1:8123 capture.json
```

The separate [diagnostic](diagnostics/README.md) documents how to measure the
Dart conversion behavior directly. It is independent of the real Rive app.

## Evidence matrix

All ten cases used Flutter 3.47.7 / Dart 3.13.5 and Chrome 155.0.8059.85 on the
same macOS 27.0.1 arm64 host. These are profile builds. Each case performed 30
reads; failures below are repeated observations of the two defects.

| Packages / correction | dart2wasm | dart2js |
| --- | --- | --- |
| 0.15.0-dev.3 / 0.2.0-dev.3 | 20 pass, 10 fail: A + B | 30 pass |
| Newest + A and B | 30 pass | 30 pass |
| 0.14.11 / 0.1.11 | 20 pass, 10 fail: A + B | 30 pass |
| Newest + A only | 22 pass, 8 fail: B | 30 pass |
| Newest + B only | 28 pass, 2 fail: A | 30 pass |

Every case observed the tenth large decode grow Rive's non-shared memory from
67,108,864 to 80,543,744 bytes, detaching the old buffer. There were no fatal app
errors or uncaught page errors. `crossOriginIsolated` was true in all cases.
The Wasm captures report `compiler=dart2wasm`, request `main.dart.wasm` and
`main.dart.mjs`, and never request `main.dart.js`; they also load skwasm. The JS
captures report `compiler=dart2js` and request `main.dart.js`. The stable Rive
runtime is `flutter-native-wasm@44.0.0`; the prerelease is `@47.0.0`.

See [matrix.json](evidence/matrix.json), [verification.log](evidence/verification.log),
the [capture guide](evidence/README.md), and the full per-case JSON, console and
PNG captures in `evidence/`. Build logs and per-case dependency lockfiles are
included. No previous SDK's captures are counted in this matrix.

## Root causes

**A: enum element conversion.** `WebRiveFile.enums` uses
`.toDart.cast<String>()`. A JS array's `.toDart` converts the array wrapper, not
its elements. Under dart2wasm the elements remain JS values; a Dart cast cannot
convert them to strings. The cast is lazy, so reading only the list length
hides the error. The separate unminified Dart 3.13.5 diagnostic reports
`Type 'JSValue' is not a subtype of type 'String' in type cast`; the Flutter
profile app instead reports the shortened type-check error shown above.

**B: cached length on a detached heap view.** `WasmBuffer.data` uses
`_data.isEmpty` to decide when to refresh a view. Under dart2wasm the Dart typed
array wrapper caches its length. In the separate Dart 3.13.5 diagnostic, after
growth the old JS view's length is 0 while its Dart wrapper still reports length
1024 and `isEmpty == false`. Under dart2js both lengths become 0. Consequently,
`RiveWasm.toNativeString` can retain its detached 1024-byte scratch view, which
short path lookups use through `_findPointerByPath`. Repeated path failures in
the app begin at the observed Rive memory growth. The B-only correction restores
all of those reads while leaving A visible.

## What the correction changes

The first commit converts every enum element with `(e as js.JSString).toDart`
and materializes the Dart list. The second refreshes the heap view on each
non-disposed `WasmBuffer.data` access using the existing `RiveWasm.heap` helper.
The changes are confined to two Dart sources, with no new dependency or runtime
binary change. Each commit has a short explanatory comment and root-cause body.

Refreshing a view creates a typed-array/Dart wrapper without copying the
underlying Wasm bytes. The performance cost was not measured. The captures
verify these data-binding operations, not drawing, animation or native behavior.

## Existing-issue search

The public, unauthenticated GitHub issue search API was queried on 2026-10-21
without a state filter, covering open and closed issues: `wasm` (20), `dart2wasm`
(2), `WasmGC` (1), `skwasm` (3), `detached` (2), `enums` (0), `cast` (10), and
`JSValue` (0). Counts overlap. All returned results fit on one page per query;
none of the API results was marked incomplete. Exact queries, counts and issue
links are in [issue-search.json](evidence/issue-search.json).

[The #628 comment](https://github.com/rive-app/rive-flutter/issues/628#issuecomment-4322984209)
is an existing symptom match for B. [#593](https://github.com/rive-app/rive-flutter/issues/593)
is a possible overlap, but has no stack or reproduction to establish the cause.
No exact report for A was found in these results. [#615](https://github.com/rive-app/rive-flutter/issues/615)
concerns a non-Wasm null failure, [#391](https://github.com/rive-app/rive-flutter/issues/391)
an older compile failure, [#375](https://github.com/rive-app/rive-flutter/issues/375)
the earlier interop migration, and [#561](https://github.com/rive-app/rive-flutter/issues/561)
an initialization/export failure. Those do not establish these two source causes.

The Flutter documentation and community forum searches did not provide an
answer for these failures. Search cannot prove absence, so please point to any
existing report this one duplicates.
