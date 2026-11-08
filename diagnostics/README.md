This separate diagnostic measures Dart/JS conversion directly. It deliberately grows a tiny WebAssembly memory; the application in `repro/` instead observes natural Rive heap growth from ordinary file decoding. Do not confuse the two.

With `FLUTTER_BIN` set to the same verified Flutter 3.47.9 executable used for the app, run from the repository root:

```sh
mkdir -p .work/diagnostics
cp diagnostics/main.dart diagnostics/index.html .work/diagnostics/
"$(dirname "$FLUTTER_BIN")/dart" compile wasm --no-minify -O0 \
  .work/diagnostics/main.dart -o .work/diagnostics/probe.wasm
"$(dirname "$FLUTTER_BIN")/dart" compile js -O1 \
  .work/diagnostics/main.dart -o .work/diagnostics/probe.js
python3 tool/serve.py .work/diagnostics --port 8240
```

In a second terminal, with `CHROME_PATH` set to the Chrome executable:

```sh
node tool/capture.mjs http://127.0.0.1:8240 evidence/interop-probe-wasm.json
node tool/capture.mjs 'http://127.0.0.1:8240/?js' evidence/interop-probe-js.json
```

Both captures use the same Dart 3.13.7 SDK. The Wasm capture is unminified and retains full type-error details, unlike the app's optimized profile build.
