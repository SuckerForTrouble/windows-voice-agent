#!/usr/bin/env bash
# Ship a new version to everyone:   ./release.sh          (0.1.0 -> 0.1.1)
#                                   ./release.sh minor    (0.1.3 -> 0.2.0)
# Runs the tests, bumps the version, tags it and pushes. GitHub then builds the
# Windows installer (~15 min the first time, ~6 after) and every installed copy
# updates itself the next time it starts (or from the tray: Check for updates).
set -euo pipefail
cd "$(dirname "$0")"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Commit (or stash) your changes first."; exit 1
fi
python3 tests/test_routing.py

cur=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' wva/__init__.py)
IFS=. read -r major minor patch <<< "$cur"
case "${1:-patch}" in
  major) major=$((major + 1)); minor=0; patch=0 ;;
  minor) minor=$((minor + 1)); patch=0 ;;
  patch) patch=$((patch + 1)) ;;
  *) echo "usage: ./release.sh [patch|minor|major]"; exit 1 ;;
esac
new="$major.$minor.$patch"

sed -i "s/^__version__ = .*/__version__ = \"$new\"/" wva/__init__.py
git commit -qam "Release v$new"
git tag "v$new"
git push -q
git push -q origin "v$new"
echo "v$new is on its way. Watch the build:  gh run watch"
echo "Installer link for new people: https://github.com/SuckerForTrouble/windows-voice-agent/releases/latest/download/WindowsVoiceAgent-Setup.exe"
