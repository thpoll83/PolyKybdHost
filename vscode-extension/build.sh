#!/usr/bin/env bash
# Build the extension package.
#
#   ./build.sh   -> dist/polykybd-mode-reporter-<version>.vsix
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
