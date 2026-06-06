#!/usr/bin/env bash
# Fetch the fonts the emoji-layer demo renders with.
#
#   * NotoEmoji        - monochrome (scalable) emoji, the primary glyph source
#   * NotoSansSymbols2 - extra symbols / dingbats / arrows fallback
#
# DejaVu Sans and NotoColorEmoji are used as further fallbacks if present on the
# system, so they are not downloaded here.
#
# Default target matches emoji_demo.py's --fontdir default (~/.cache/emojigif/fonts);
# pass a directory as $1 to override.
set -e

DEST="${1:-$HOME/.cache/emojigif/fonts}"
BASE="https://raw.githubusercontent.com/google/fonts/main/ofl"
mkdir -p "$DEST"

fetch() {
    local url="$1" out="$2"
    if [ -f "$out" ]; then echo "  skip  $out"; return; fi
    echo "  fetch $out"
    if command -v curl &>/dev/null; then curl -fsSL "$url" -o "$out"; else wget -q "$url" -O "$out"; fi
}

fetch "$BASE/notoemoji/NotoEmoji%5Bwght%5D.ttf"                 "$DEST/NotoEmoji.ttf"
fetch "$BASE/notosanssymbols2/NotoSansSymbols2-Regular.ttf"     "$DEST/NotoSansSymbols2.ttf"

echo "Fonts ready in $DEST"
