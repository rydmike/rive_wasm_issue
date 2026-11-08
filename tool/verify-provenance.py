#!/usr/bin/env python3
"""Writes the provenance records in evidence/ for the tested package versions.

- pub-version-summary.json: latest stable and last published versions from the pub.dev API.
- source-verification.json: each tested rive_native archive checked against pub.dev, the two affected sources
  and whether they still hold the old patterns, and the cached library files compared with the archive.
- rive-source-verification.json: the same archive and cached-library checks for each tested rive version.
- package-verification.json: the rive_native copy's baseline compared file by file (and executable bit) with
  the archive, its tag, the correction's changed files, and the correction's format-patch applied with git am to
  a fresh baseline, compared with the tested branch.

Needs RIVE_NATIVE_DIR, a checkout of the correction branch (default: the sibling rive_native).
"""
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence'
WORK = ROOT / '.work'
NATIVE = Path(os.environ.get('RIVE_NATIVE_DIR', ROOT.parent / 'rive_native'))
FIX = 'fix-wasm-interop-0.2.0-dev.4'
BASELINE_TAG = '0.2.0-dev.4-verbatim'
NATIVE_VERSIONS = ['0.2.0-dev.4', '0.1.11']
RIVE_VERSIONS = ['0.15.0-dev.4', '0.14.11']
OLD_PATTERNS = {
    'lib/src/web/rive_web.dart': '.cast<String>()',
    'lib/src/rive_native_web.dart': '_data.isEmpty && _pointer != 0.toJS',
}
PUB_CACHE = Path(os.environ.get('PUB_CACHE', Path.home() / '.pub-cache')) / 'hosted' / 'pub.dev'


def get_json(url: str):
    with urllib.request.urlopen(url) as response:
        return json.load(response)


def archive(package: str, version: str) -> tuple[bytes, dict]:
    url = f'https://pub.dev/api/archives/{package}-{version}.tar.gz'
    with urllib.request.urlopen(url) as response:
        data = response.read()
    meta = get_json(f'https://pub.dev/api/packages/{package}/versions/{version}')
    return data, {'archive_url': url, 'archive_sha256': hashlib.sha256(data).hexdigest(),
                  'matches_pub_dev': hashlib.sha256(data).hexdigest() == meta['archive_sha256']}


def files_of(data: bytes) -> dict[str, tuple[bytes, int]]:
    """Every regular file of an archive, read once: its bytes and mode."""
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        return {m.name.removeprefix('./'): (tar.extractfile(m).read(), m.mode) for m in tar.getmembers() if m.isfile()}


def cached_libraries_match(package: str, version: str, files: dict[str, tuple[bytes, int]]) -> tuple[int, bool]:
    cached = PUB_CACHE / f'{package}-{version}' / 'lib'
    names = sorted(n for n in files if n.startswith('lib/'))
    same = all((cached.parent / n).is_file() and (cached.parent / n).read_bytes() == files[n][0] for n in names)
    extra = {str(p.relative_to(cached.parent)) for p in cached.rglob('*') if p.is_file()} - set(names)
    return len(names), same and not extra


def git(*args: str, cwd: Path = NATIVE) -> str:
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def blob_sha(content: bytes) -> str:
    return hashlib.sha1(b'blob %d\0' % len(content) + content).hexdigest()


now = datetime.datetime.now(datetime.timezone.utc).isoformat()
summary = {'checked_at_utc': now, 'packages': []}
for package in ['rive', 'rive_native']:
    info = get_json(f'https://pub.dev/api/packages/{package}')
    last = info['versions'][-1]
    summary['packages'].append({'package': package, 'api_url': f'https://pub.dev/api/packages/{package}',
                                'latest_stable': info['latest']['version'], 'last_published': last['version'],
                                'last_published_at': last['published']})

native_records, native_archives = [], {}
for version in NATIVE_VERSIONS:
    data, record = archive('rive_native', version)
    files = files_of(data)
    native_archives[version] = (data, files)
    sources = {}
    for name, pattern in OLD_PATTERNS.items():
        content = files[name][0]
        sources[name] = {'sha256': hashlib.sha256(content).hexdigest(), 'old_pattern_present': pattern.encode() in content}
    count, same = cached_libraries_match('rive_native', version, files)
    native_records.append({'package': 'rive_native', 'version': version, **record, 'sources': sources,
                           'unpatched_cached_library_file_count': count,
                           'unpatched_cached_libraries_match_archive': same})

rive_records = []
for version in RIVE_VERSIONS:
    data, record = archive('rive', version)
    count, same = cached_libraries_match('rive', version, files_of(data))
    rive_records.append({'version': version, **record, 'cached_library_file_count': count,
                         'cached_libraries_match_archive': same})

# The copy's baseline against the newest archive, blob by blob and bit by bit.
newest, members = native_archives[NATIVE_VERSIONS[0]]
tree = {}
for line in git('ls-tree', '-r', 'main').splitlines():
    meta, path = line.split('\t', 1)
    mode, _, sha = meta.split()
    tree[path] = (mode, sha)
matches = set(tree) == set(members) and all(tree[n][1] == blob_sha(content) for n, (content, _) in members.items())
exec_bits = all((tree[n][0] == '100755') == bool(mode & 0o100) for n, (_, mode) in members.items())
corrections = git('rev-list', '--reverse', f'main..{FIX}').splitlines()
changed = git('diff', '--name-only', f'main...{FIX}').splitlines()

# git am of the format-patch on a fresh baseline must give the tested branch's tree.
check = WORK / 'am-check'
patch = git('format-patch', '--stdout', f'main..{FIX}')
git('worktree', 'add', '--detach', str(check), 'main')
try:
    subprocess.run(['git', '-c', 'user.name=check', '-c', 'user.email=check@localhost', 'am', '--quiet'],
                   cwd=check, input=patch, text=True, check=True, capture_output=True)
    am_ok = True
    am_matches = git('rev-parse', 'HEAD^{tree}', cwd=check) == git('rev-parse', f'{FIX}^{{tree}}')
finally:
    git('worktree', 'remove', '--force', str(check))

package = {'package': 'rive_native', 'version': NATIVE_VERSIONS[0],
           'archive_sha256': hashlib.sha256(newest).hexdigest(), 'archive_file_count': len(members),
           'main_matches_every_archive_file': matches, 'executable_bits_match': exec_bits,
           'main_history': git('log', '--format=%H %s', 'main').splitlines(),
           'correction_commit_count': len(corrections), 'tag': BASELINE_TAG,
           'tag_points_to_main': git('rev-parse', f'{BASELINE_TAG}^{{commit}}') == git('rev-parse', 'main'),
           'changed_files': changed, 'format_patch_git_am_verified': am_ok,
           'git_am_result_matches_tested_branch': am_matches, 'main_commit': git('rev-parse', 'main'),
           'correction_branch': FIX, 'correction_commits': corrections}

for name, value in [('pub-version-summary', summary), ('source-verification', native_records),
                    ('rive-source-verification', rive_records), ('package-verification', package)]:
    (EVIDENCE / f'{name}.json').write_text(json.dumps(value, indent=2) + '\n')
print(json.dumps({'native': [(r['version'], r['matches_pub_dev'], r['unpatched_cached_libraries_match_archive'],
                              [s['old_pattern_present'] for s in r['sources'].values()]) for r in native_records],
                  'rive': [(r['version'], r['matches_pub_dev'], r['cached_libraries_match_archive']) for r in rive_records],
                  'package': {k: package[k] for k in ('archive_file_count', 'main_matches_every_archive_file',
                                                       'executable_bits_match', 'tag_points_to_main',
                                                       'format_patch_git_am_verified',
                                                       'git_am_result_matches_tested_branch', 'changed_files')}},
                 indent=1))
