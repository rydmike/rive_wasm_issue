#!/usr/bin/env python3
"""Select exact published versions; optionally override a local patched package."""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('version', choices=['stable', 'newest'])
parser.add_argument('--patched', help='Path to a copy of rive_native 0.2.0-dev.3')
a = parser.parse_args()
project = Path(__file__).resolve().parents[1] / "repro"
spec = project / 'pubspec.yaml'
text = spec.read_text()
rive, native = ('0.14.11', '0.1.11') if a.version == 'stable' else ('0.15.0-dev.3', '0.2.0-dev.3')
import re
text = re.sub(r'^  rive: .+$', '  rive: '+rive, text, flags=re.M)
text = re.sub(r'^  rive_native: .+$', '  rive_native: '+native, text, flags=re.M)
spec.write_text(text)
overrides = project / 'pubspec_overrides.yaml'
if a.patched:
    if a.version != 'newest':
        parser.error('--patched requires newest')
    import json
    overrides.write_text('dependency_overrides:\n  rive_native:\n    path: '+json.dumps(a.patched)+'\n')
elif overrides.exists():
    overrides.unlink()
print(f'Selected rive {rive} / rive_native {native}' + (' with local override' if a.patched else ''))
