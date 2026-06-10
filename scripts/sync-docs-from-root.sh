#!/usr/bin/env bash
# Copy root-level CHANGELOG / CONTRIBUTING / LICENSE into the docs tree as the
# directory index VitePress expects. Run before `pnpm run docs:build`.
set -e
root="$(cd "$(dirname "$0")/.." && pwd)"
cp "$root/CHANGELOG.md"     "$root/docs/Changelog/index.md"
cp "$root/CONTRIBUTING.md"  "$root/docs/Contribute/index.md"
cp "$root/LICENSE"          "$root/docs/License/index.md"
echo "Synced CHANGELOG / CONTRIBUTING / LICENSE into docs/."
