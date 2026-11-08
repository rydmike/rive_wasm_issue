# Flutter 3.47.9 evidence

All application and diagnostic captures here were collected on 2026-11-08 UTC using Flutter 3.47.9 stable / Dart 3.13.7, Chrome 156.0.8078.81 and macOS 27.0.1 arm64. The first run, on Flutter 3.47.7 with `rive_native 0.2.0-dev.3` on 2026-10-21, gave the same results. `flutter-version.txt` is the verbatim SDK output. Other tool versions are in `environment.json`.

Each of the ten matrix cases has:

- `CASE.json`: console messages/stacks, request URLs, local response headers, browser version, UTC capture time, isolation flag and observed memory growth.
- `CASE.console.log`: text console capture, including caught error stacks.
- `CASE.png`: page results from the same completed browser run.
- `CASE.build.log` and `CASE.pub-get.log`: build and dependency-resolution output.
- `CASE.pubspec.lock`: the dependencies used for that build; corrected cases contain portable relative paths to the tested local package.

`matrix.json` is derived from the JSON captures by `tool/summarize.py`. `verification.log` records validation of all ten captures, including correct returned values for successful checks, 30 total reads, compiler selection, absence of JS fallback in the Wasm runs, isolation and real Rive memory growth. It summarizes observed failures without imposing historical failure counts.

All cases loaded Rive's version-pinned CDN runtime, and every case observed its heap grow from 67,108,864 to 80,543,744 bytes at the tenth retained large decode, with the old buffer detached. No fatal application or uncaught page errors occurred. Some Flutter resource requests were cancelled during initialization; the checked operations completed. The screenshots include the complete result list; the JSON/text files retain full exception stacks.

`interop-probe-wasm` and `interop-probe-js` are separate diagnostics, not matrix rows. Their source is in `diagnostics/`. They deliberately grow a tiny memory to expose Dart's wrapper behavior. Their missing favicon produced a harmless 404 in each diagnostic; it did not affect the diagnostic. The real app uses natural allocation pressure from fixture decoding and has an inline favicon.

Other provenance:

- `source-verification.json`: both published native archive SHA-256 checks, affected source hashes/patterns and complete cached-library byte comparisons.
- `rive-source-verification.json`: equivalent archive and cached-library checks for both published `rive` versions.
- `package-verification.json`: every regular archive file and executable bit compared with Git `main`; tag/history checks; two-commit `git am` validation on a fresh baseline.
- `correction-refs.json`: exact committed objects used for corrected builds.
- `pub-version-summary.json`: latest stable and last published versions from the public pub.dev API at verification time.
- `issue-search.json`: public GitHub API searches of open and closed issues, returned titles/states/links, and review of the existing symptom overlap.
- `runtime-issue-template.yml`: upstream issue-form snapshot used for the README.
- `checks.txt`: static analysis, formatting, provenance and packaging checks.

`tool/verify-provenance.py` writes the four provenance records above (pub versions, both source checks and the package check) from the pub.dev API, the published archives, the local pub cache and the `rive_native` copy.

Build-tool output has portable placeholders in place of private absolute paths. The standard pub generator comment is omitted from lockfiles; resolutions are unchanged. No browser profiles, dependency directories or generated application binaries are included. The source lockfile defaults to the published prerelease pair; `default.pub-get.log` records its restoration after the matrix builds.
