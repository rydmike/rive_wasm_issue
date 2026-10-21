#!/bin/sh
# Export only committed files, with no Git metadata, dependency cache or builds.
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -n "$(git -C "$repo_dir" status --porcelain --untracked-files=normal)" ]; then
  echo 'Commit the intended repository changes before making the reproduction ZIP.' >&2
  exit 1
fi
git -C "$repo_dir" archive --format=zip --prefix=rive_wasm_issue/ \
  --output="$repo_dir/../repro.zip" HEAD
printf '%s\n' 'Wrote ../repro.zip from committed files.'
