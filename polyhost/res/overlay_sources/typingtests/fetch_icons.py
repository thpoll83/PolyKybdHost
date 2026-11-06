#!/usr/bin/env python3
"""Fetch + render the icons of the typing-test website overlays (Monkeytype and
keybr), the reproducible source step.

Key glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) for the `ms:` entry. The two ESC marks are each site's own logo
from its own repository, pinned to a commit, reduced to a 32x32 1-bit trace
(contain-fit, LANCZOS, then a luma threshold). Both marks are guarded: a re-run
leaves a committed PNG as it is. Delete the PNG to redraw it. See SOURCES.md.

    pip install cairosvg Pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/typingtests/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

FLUENT = {
    "restart": "Arrow Clockwise",          # Monkeytype: Tab, then Enter
    "commandline": "Apps List Detail",     # Monkeytype: Ctrl/Cmd+Shift+P
    "finish": "ms:sports_score",           # Monkeytype: Shift+Enter
    "reset": "Arrow Counterclockwise",     # keybr: Ctrl+Left
    "skip": "Next",                        # keybr: Ctrl+Right
    "focus": "Keyboard",                   # keybr: Enter
}

# Monkeytype's favicon (GPL-3.0, monkeytypegame/monkeytype): a dark rounded
# square with the letters "mt". Dark pixels lit, so the square is the lit badge
# and the letters are cut out of it.
MONKEYTYPE_LOGO_URL = ("https://raw.githubusercontent.com/monkeytypegame/monkeytype/"
                       "0e07023d4a7af1d0c2d8497afdff30eaff615279/"
                       "frontend/static/images/favicon/favicon.svg")
MONKEYTYPE_LUMA = 128
MONKEYTYPE_DARK_LIT = True

# keybr's favicon (AGPL-3.0, aradzie/keybr.com): a tilted photo of keycaps.
# At luma 128 neither polarity shows a key (one polarity is a blob, the other
# the gaps). Light pixels above 215 lit keeps only the white keycaps, so the
# mark reads as a row of tilted keys; 185 also lit the grey keys and their
# printed labels, which became noise at 32 px.
KEYBR_LOGO_URL = ("https://raw.githubusercontent.com/aradzie/keybr.com/"
                  "05a37bc5265f65ff538c59c613db29442f345d51/"
                  "packages/keybr-pages-server/assets/favicon-96x96.png")
KEYBR_LUMA = 215
KEYBR_DARK_LIT = False


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _load(url: str) -> Image.Image:
    data = _download(url)
    if url.endswith(".svg"):
        import cairosvg
        data = cairosvg.svg2png(bytestring=data, output_width=256, output_height=256)
    return Image.open(io.BytesIO(data)).convert("RGBA")


def trace_mark(icon: Image.Image, dest: Path, luma: int, dark_lit: bool,
               px: int = 32) -> None:
    """`icon` as a px*px 1-bit trace: contain-fit with LANCZOS, then the pixels
    at `luma` or darker lit (`dark_lit`) or the pixels brighter than `luma` lit.
    The transparent padding is composited so it stays unlit in both cases.
    Drawn at the keycap size so the generator copies it 1:1."""
    pad = "white" if dark_lit else "black"
    flat = Image.new("RGBA", icon.size, pad)
    flat.alpha_composite(icon)
    src = flat.convert("L")
    scale = px / max(src.size)
    fitted = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))),
                        Image.LANCZOS)
    square = Image.new("L", (px, px), 255 if dark_lit else 0)
    square.paste(fitted, ((px - fitted.width) // 2, (px - fitted.height) // 2))
    if dark_lit:
        a = square.point(lambda v: 255 if v <= luma else 0)
    else:
        a = square.point(lambda v: 255 if v > luma else 0)
    Image.merge("RGBA", (a, a, a, a)).save(dest)


def _guarded(path: Path, draw) -> None:
    """Draw a mark only when its PNG is missing; the committed PNG is the source
    of truth after that."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        draw(path)
        print(f"  {path.name}  <- traced (typingtests/fetch_icons.py)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    _guarded(out / "monkeytype.png", lambda p: trace_mark(
        _load(MONKEYTYPE_LOGO_URL), p, MONKEYTYPE_LUMA, MONKEYTYPE_DARK_LIT))
    _guarded(out / "keybr.png", lambda p: trace_mark(
        _load(KEYBR_LOGO_URL), p, KEYBR_LUMA, KEYBR_DARK_LIT))
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
