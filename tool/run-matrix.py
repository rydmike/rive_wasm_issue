#!/usr/bin/env python3
"""Build/capture the ten cases, using only the explicitly supplied stable SDK."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPRO = ROOT / 'repro'
WORK = ROOT / '.work'
EVIDENCE = ROOT / 'evidence'
WORK.mkdir(exist_ok=True)
# The correction branch in the rive_native copy.
FIX = 'fix-wasm-interop-0.2.0-dev.4'
EVIDENCE.mkdir(exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument('stage', choices=['build', 'capture', 'all'])
parser.add_argument('--case', help='Run just one case')
a = parser.parse_args()
CASES = [(variant, compiler) for variant in ['newest', 'fixed', 'stable', 'a-only', 'b-only']
         for compiler in ['wasm', 'js']]
if a.case:
    CASES = [(v, c) for v, c in CASES if v+'-'+c == a.case]
    if not CASES:
        parser.error('Unknown case')
env = os.environ.copy()
env['XDG_CONFIG_HOME'] = str(WORK / 'config')
env['FLUTTER_SUPPRESS_ANALYTICS'] = 'true'

def clean(text):
    # Build tools can print absolute paths; evidence uses portable placeholders.
    for path, replacement in [(str(ROOT.parent), '<workspace>'),
                              (str(Path.home()), '<user-home>')]:
        text = text.replace(path, replacement)
    return text

def lock_text(path):
    lines = path.read_text().splitlines(keepends=True)
    if lines and lines[0].startswith('#') and lines[0].rstrip().endswith(' pub'):
        lines.pop(0)
    return ''.join(lines)

def run(cmd, cwd=REPRO, log=None):
    result = subprocess.run([str(x) for x in cmd], cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if log:
        (EVIDENCE / log).write_text(clean(result.stdout))
    if result.returncode:
        print(clean(result.stdout), flush=True)
        raise RuntimeError('Command failed: '+str(cmd[0]))
    return result.stdout

if a.stage in ['build', 'all']:
    flutter = os.environ.get('FLUTTER_BIN')
    if not flutter:
        parser.error('Set FLUTTER_BIN to the stable Flutter 3.47.9 executable')
    version = run([flutter, '--version'], log='flutter-version.txt')
    if 'Flutter 3.47.9 • channel stable' not in version or 'Dart 3.13.7' not in version:
        raise RuntimeError('Required Flutter 3.47.9 / Dart 3.13.7 was not found; stopped')
    # The sibling checkout by default; RIVE_NATIVE_DIR names another one,
    # such as a git worktree of the correction branch.
    native = Path(os.environ.get('RIVE_NATIVE_DIR', ROOT.parent / 'rive_native'))
    branch = run(['git', 'branch', '--show-current'], cwd=native).strip()
    if branch != FIX:
        raise RuntimeError('The rive_native checkout must be on '+FIX)
    if run(['git', 'diff', '--name-only', 'HEAD'], cwd=native).strip():
        raise RuntimeError('The sibling correction has tracked changes')
    refs = {name: run(['git','rev-parse',name],cwd=native).strip()
            for name in ['main', FIX, FIX+'~1']}
    # Isolate each correction using the actual committed objects, not the cache.
    for variant, ref in [('a-only', FIX+'~1'), ('b-only', 'main')]:
        dest = WORK / variant
        if dest.exists():
            shutil.rmtree(dest)
        if not dest.exists():
            archive = WORK / (variant+'.tar')
            subprocess.run(['git','archive','--format=tar','--output='+str(archive),ref],
                           cwd=native,check=True)
            dest.mkdir()
            with tarfile.open(archive) as t:
                t.extractall(dest)
            if variant == 'b-only':
                source = native / 'lib/src/rive_native_web.dart'
                shutil.copy2(source, dest / 'lib/src/rive_native_web.dart')
    (EVIDENCE/'correction-refs.json').write_text(json.dumps(refs,indent=2)+'\n')
    try:
        for variant, compiler in CASES:
            name = variant+'-'+compiler
            select = [sys.executable, ROOT/'tool/select-version.py',
                      'stable' if variant == 'stable' else 'newest']
            if variant == 'fixed':
                select += ['--patched', os.path.relpath(native, REPRO)]
            elif variant in ['a-only','b-only']:
                select += ['--patched', os.path.relpath(WORK/variant,REPRO)]
            run(select)
            run([flutter,'pub','get'],log=name+'.pub-get.log')
            lock = lock_text(REPRO/'pubspec.lock')
            (EVIDENCE/(name+'.pubspec.lock')).write_text(lock)
            cmd = [flutter,'build','web','--profile','--dart-define=RUN_LABEL='+variant,
                   '--output='+os.path.relpath(WORK/'builds'/name, REPRO)]
            cmd += ['--wasm','--no-minify-wasm'] if compiler == 'wasm' else ['--no-wasm-dry-run']
            print('Building '+name,flush=True)
            run(cmd,log=name+'.build.log')
            print('Built '+name,flush=True)
    finally:
        run([sys.executable,ROOT/'tool/select-version.py','newest'])
        run([flutter,'pub','get'],log='default.pub-get.log')
        lockfile = REPRO/'pubspec.lock'
        lockfile.write_text(lock_text(lockfile))

if a.stage in ['capture','all']:
    if not os.environ.get('CHROME_PATH'):
        parser.error('Set CHROME_PATH to the Chrome executable')
    for index,(variant,compiler) in enumerate(CASES):
        name = variant+'-'+compiler
        port = 8223+index
        server = subprocess.Popen([sys.executable,ROOT/'tool/serve.py',WORK/'builds'/name,
                                   '--port',str(port)],cwd=ROOT,env=env,
                                  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            url='http://127.0.0.1:'+str(port)
            for attempt in range(100):
                try:
                    urllib.request.urlopen(url,timeout=1).close()
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Server did not start')
            print('Capturing '+name,flush=True)
            run(['node',ROOT/'tool/capture.mjs',url,EVIDENCE/(name+'.json')],
                cwd=ROOT,log=name+'.console.log')
            f=EVIDENCE/(name+'.json');f.write_text(clean(f.read_text()))
            print('Captured '+name,flush=True)
        finally:
            server.terminate()
            server.wait(timeout=10)
    run([sys.executable,ROOT/'tool/summarize.py'],cwd=ROOT,log='verification.log')
    print((EVIDENCE/'verification.log').read_text(),flush=True)
