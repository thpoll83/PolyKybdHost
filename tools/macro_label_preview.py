#!/usr/bin/env python3
"""Render a macro keycap the way the firmware draws it, and check it does not clip.

Mirrors ``render_macro_key()`` in keyboards/polykybd/poly_keymap.c coordinate for
coordinate: the macro index in the _Mid_ 19 px face centred in whatever the caption
leaves, the label in the _Nano_ 10 px face pinned so its lowest lit pixel lands on the
last screen row, and the label truncated by measured width.

Same caveat as oled_preview.py and glyph_size_preview.py: this is a Python model of the
C, so it validates the LAYOUT and can drift from the compiled behaviour. What it is for
is the check the C cannot do for itself -- counting pixels that fall outside the 72x40
window, which must be zero.

    python3 tools/macro_label_preview.py --check
    python3 tools/macro_label_preview.py "work mail" "git push" --id 3
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polyhost.services.macro_label import (  # noqa: E402
    PANEL_H, PANEL_W, default_font_dir, fit, load_nano_font,
)
from tools.gfx_font import GfxFont, _parse_header  # noqa: E402

MID_FONT_SYMBOL = "NotoSans_Regular_Mid_19px7b"


def _load(font_dir: str, filename: str, symbol: str) -> GfxFont:
    bitmaps: dict = {}
    glyph_arrays: dict = {}
    fonts: dict = {}
    with open(os.path.join(font_dir, filename), encoding="utf-8", errors="replace") as fh:
        _parse_header(fh.read(), bitmaps, glyph_arrays, fonts)
    raw = fonts[symbol]
    return GfxFont(name=symbol, bitmap=bitmaps[raw["bmp"]], glyphs=glyph_arrays[raw["gly"]],
                   first=raw["first"], last=raw["last"], yAdvance=raw["yAdvance"])


def _glyph(font: GfxFont, cp: int):
    if not (font.first <= cp <= font.last):
        return None
    g = font.glyphs[cp - font.first]
    if g["width"] == 0 and g["height"] == 0 and g["xAdvance"] == 0:
        return None
    return g


def bbox(text: str, font: GfxFont):
    """(xmin, xmax, ymin, ymax) relative to the draw origin, baseline at y = 0."""
    x = 0
    xmn = xmx = ymn = ymx = None
    for ch in text:
        g = _glyph(font, ord(ch))
        if g is None:
            continue
        if g["width"] > 0 and g["height"] > 0:
            l, r = x + g["xOffset"], x + g["xOffset"] + g["width"] - 1
            t, b = g["yOffset"], g["yOffset"] + g["height"] - 1
            xmn = l if xmn is None else min(xmn, l)
            xmx = r if xmx is None else max(xmx, r)
            ymn = t if ymn is None else min(ymn, t)
            ymx = b if ymx is None else max(ymx, b)
        x += g["xAdvance"]
    if xmn is None:
        return 0, -1, 0, -1
    return xmn, xmx, ymn, ymx


def draw(px, text: str, font: GfxFont, x0: int, baseline: int) -> int:
    """Plot `text`; returns the number of lit pixels that fell outside the panel."""
    x = x0
    clipped = 0
    for ch in text:
        g = _glyph(font, ord(ch))
        if g is None:
            continue
        bo, cb = g["bitmapOffset"], (g["height"] + 7) >> 3   # column-native
        for xx in range(g["width"]):
            col = bo + xx * cb
            for yy in range(g["height"]):
                if font.bitmap[col + (yy >> 3)] & (1 << (yy & 7)):
                    vx = x + g["xOffset"] + xx
                    vy = baseline + g["yOffset"] + yy
                    if 0 <= vx < PANEL_W and 0 <= vy < PANEL_H:
                        px[vy][vx] = 1
                    else:
                        clipped += 1
        x += g["xAdvance"]
    return clipped


def render(label: str, macro_id: int, nano: GfxFont, mid: GfxFont):
    """Returns (pixel grid, clipped count, the label text actually drawn)."""
    px = [[0] * PANEL_W for _ in range(PANEL_H)]
    index_text = f"M{macro_id}"
    clipped = 0

    if not label:
        ixmin, ixmax, iymin, iymax = bbox(index_text, mid)
        clipped += draw(px, index_text, mid,
                        (PANEL_W - (ixmax - ixmin + 1)) // 2 - ixmin,
                        (PANEL_H - (iymax - iymin + 1)) // 2 - iymin)
        return px, clipped, ""

    kept = fit(label, nano).text
    if not kept:
        return px, 0, ""

    lxmin, lxmax, lymin, lymax = bbox(kept, nano)
    cap_base = PANEL_H - 1 - lymax
    free_rows = cap_base + lymin
    clipped += draw(px, kept, nano,
                    (PANEL_W - (lxmax - lxmin + 1)) // 2 - lxmin, cap_base)

    ixmin, ixmax, iymin, iymax = bbox(index_text, mid)
    ih = iymax - iymin + 1
    if ih < free_rows:
        clipped += draw(px, index_text, mid,
                        (PANEL_W - (ixmax - ixmin + 1)) // 2 - ixmin,
                        (free_rows - ih) // 2 - iymin)
    return px, clipped, kept


def show(px) -> str:
    top = "    +" + "-" * PANEL_W + "+"
    rows = [f"{y:3d} |" + "".join("#" if v else "." for v in px[y]) + "|"
            for y in range(PANEL_H)]
    return "\n".join([top] + rows + [top])


CHECK_LABELS = [
    "", "M", "push", "email", "gmail", "sign off", "git push", "work mail",
    "cons.log", "password", "Hello World!", "WWWWWWWW", "WWWWWWWWW",
    "mmmmmmmmmmmm", "iiiiiiiiiiii", "gjpqy,;", "|||||||||||", "~~~~~~~~~~~~",
    "  spaced  ", "AaBbCcDdEeFf",
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("labels", nargs="*", help="labels to render (default: a sample)")
    ap.add_argument("--id", type=int, default=3, help="macro index to draw")
    ap.add_argument("--font-dir", default=default_font_dir())
    ap.add_argument("--check", action="store_true",
                    help="sweep every id x a worst-case label set; fail on any clipped pixel")
    args = ap.parse_args()

    nano = load_nano_font(args.font_dir)
    mid = _load(args.font_dir, "util_font.h", MID_FONT_SYMBOL)

    if args.check:
        bad = 0
        for macro_id in range(16):
            for label in CHECK_LABELS:
                px, clipped, kept = render(label, macro_id, nano, mid)
                if clipped:
                    bad += 1
                    print(f"CLIPPED {clipped:3d}px  M{macro_id} {label!r} -> {kept!r}")
                # A non-empty label must leave SOMETHING lit, or the keycap is blank
                # while the editor says it is labelled.
                if label.strip() and not any(any(r) for r in px):
                    bad += 1
                    print(f"BLANK           M{macro_id} {label!r}")
        total = 16 * len(CHECK_LABELS)
        print(f"\n{total - bad}/{total} cells clean" if bad else
              f"\nOK: {total} cells, 0 clipped pixels")
        return 1 if bad else 0

    for label in (args.labels or ["work mail"]):
        px, clipped, kept = render(label, args.id, nano, mid)
        print(f"\nM{args.id}  {label!r}" +
              (f"  (truncated to {kept!r})" if kept != label else "") +
              (f"  CLIPPED {clipped}px" if clipped else ""))
        print(show(px))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
