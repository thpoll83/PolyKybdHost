#!/usr/bin/env bash
# Zip the add-on for installation.
#
#   ./build.sh   -> dist/polykybd_context_reporter-<version>.zip
#
# Blender 4.2+: Edit > Preferences > Get Extensions > (menu) Install from Disk.
# Blender 3.6-4.1: Edit > Preferences > Add-ons > Install... (the zip's bl_info).
# The zip holds the package FOLDER, which both install paths accept. See README.md.
set -euo pipefail
cd "$(dirname "$0")"

PKG=polykybd_context_reporter
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' "${PKG}/blender_manifest.toml")
OUT="dist/${PKG}-${VERSION}.zip"
mkdir -p dist
# `zip` UPDATES an existing archive in place, so a deleted file would linger.
rm -f "${OUT}"
if command -v zip >/dev/null 2>&1; then
  zip -qr -X "${OUT}" "${PKG}" -x '*/__pycache__/*' '*.pyc'
else
  python3 - "${OUT}" "${PKG}" <<'PY'
import sys, zipfile, pathlib
out, pkg = sys.argv[1], pathlib.Path(sys.argv[2])
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(pkg.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
            z.write(p, p.as_posix())
PY
fi
echo "built ${OUT}"
