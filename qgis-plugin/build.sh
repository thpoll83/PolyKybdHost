#!/usr/bin/env bash
# Zip the plugin for "Plugins > Manage and Install Plugins > Install from ZIP".
#
#   ./build.sh   -> dist/polykybd_context_reporter-<version>.zip
#
# The zip holds the package FOLDER, which is what QGIS expects. See README.md.
set -euo pipefail
cd "$(dirname "$0")"

PKG=polykybd_context_reporter
VERSION=$(sed -n 's/^version=\(.*\)$/\1/p' "${PKG}/metadata.txt")
if [ -z "${VERSION}" ]; then
  echo "no version= line in ${PKG}/metadata.txt" >&2
  exit 1
fi
OUT="dist/${PKG}-${VERSION}.zip"
mkdir -p dist
rm -f "${OUT}"
python3 - "${OUT}" "${PKG}" <<'PY'
import sys, zipfile, pathlib
out, pkg = sys.argv[1], pathlib.Path(sys.argv[2])
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(pkg.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
            z.write(p, p.as_posix())
PY
echo "built ${OUT}"
