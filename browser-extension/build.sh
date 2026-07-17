#!/usr/bin/env bash
# Assemble loadable/packagable extension folders for each target from the shared
# sources. Chromium and Firefox share background.js + options.*; only the
# manifest differs (service_worker vs background.scripts + gecko settings).
#
#   ./build.sh            -> dist/chromium/ and dist/firefox/
#
# Load unpacked:
#   Chromium: chrome://extensions -> Developer mode -> Load unpacked -> dist/chromium
#   Firefox:  about:debugging#/runtime/this-firefox -> Load Temporary Add-on -> dist/firefox/manifest.json
# See README.md for permanent install + enterprise force-install.
set -euo pipefail
cd "$(dirname "$0")"

SHARED=(background.js options.html options.js)

build() {
  local target="$1" manifest="$2"
  local out="dist/${target}"
  rm -rf "${out}"
  mkdir -p "${out}"
  cp "${SHARED[@]}" "${out}/"
  cp "${manifest}" "${out}/manifest.json"
  echo "built ${out}"
}

build chromium manifest.chromium.json
build firefox  manifest.firefox.json

# Optional zips (Firefox AMO / Chrome Web Store uploads) when `zip` is present.
if command -v zip >/dev/null 2>&1; then
  ( cd dist/chromium && zip -qr ../polykybd-website-reporter-chromium.zip . )
  ( cd dist/firefox  && zip -qr ../polykybd-website-reporter-firefox.zip . )
  echo "zipped dist/*.zip"
fi
