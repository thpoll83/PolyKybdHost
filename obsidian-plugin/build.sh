#!/usr/bin/env bash
# Build the plugin folder for installation.
#
#   ./build.sh   -> dist/polykybd-mode-reporter/{main.js,manifest.json}
#                   dist/polykybd-mode-reporter-<version>.zip
#
# Needs Node.js and npm. Copy dist/polykybd-mode-reporter/ into
# <vault>/.obsidian/plugins/ (see README.md).
set -euo pipefail
cd "$(dirname "$0")"

ID=polykybd-mode-reporter
VERSION=$(sed -n 's/^ *"version": "\(.*\)",$/\1/p' manifest.json)
# Exact versions are pinned in package.json.
[ -d node_modules ] || npm install --no-audit --no-fund --no-package-lock
npx --no-install tsc --noEmit -p .
OUT="dist/${ID}"
rm -rf "${OUT}" "dist/${ID}-${VERSION}.zip"
mkdir -p "${OUT}"
# `obsidian` and Electron are provided by the app at run time.
npx --no-install esbuild src/main.ts --bundle --format=cjs --target=es2020 \
  --platform=browser --external:obsidian --external:electron \
  --outfile="${OUT}/main.js"
cp manifest.json "${OUT}/"
(cd dist && python3 -c "
import sys, zipfile, pathlib
with zipfile.ZipFile(sys.argv[1], 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(pathlib.Path(sys.argv[2]).rglob('*')):
        z.write(p, p.as_posix())
" "${ID}-${VERSION}.zip" "${ID}")
echo "built ${OUT}/ and dist/${ID}-${VERSION}.zip"
