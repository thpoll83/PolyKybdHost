#!/usr/bin/env bash
# Build the extension package.
#
#   ./build.sh   -> dist/polykybd-mode-reporter-<version>.vsix          (UI part)
#                   dist/polykybd-mode-reporter-remote-<version>.vsix   (workspace part)
#
# The workspace part is a second extension (remote/package.json) because an
# extension runs in one extension host only. Both are compiled from src/ by
# one tsc run; remote/out/ gets the two files it needs.
#
# Install it with `code --install-extension dist/<file>.vsix` (or `cursor`,
# `windsurf`), or from the Extensions view: "..." > Install from VSIX.
# The same .vsix is published to the VS Code Marketplace and to Open VSX
# (Cursor and Windsurf install from Open VSX). See README.md.
set -euo pipefail
cd "$(dirname "$0")"
npm ci --no-audit --no-fund
npm test
npx tsc -p .
VERSION=$(node -p 'require("./package.json").version')
mkdir -p dist
npx vsce package --skip-license --out "dist/polykybd-mode-reporter-${VERSION}.vsix"
mkdir -p remote/out
cp out/core.js out/remote.js remote/out/
REMOTE_VERSION=$(node -p 'require("./remote/package.json").version')
(cd remote && ../node_modules/.bin/vsce package --no-dependencies --skip-license --out "../dist/polykybd-mode-reporter-remote-${REMOTE_VERSION}.vsix")
