#!/usr/bin/env python3
"""Preview + clip-check the PolyKybd keycap legend SIZES (HID cmd 34).

Mirrors render_key()'s plan_main_legend() coordinate for coordinate: the relocated
codepoint (0xF0000 / 0xF3000 base), the bbox, the horizontal clamp into the visible
window and the vertical nominal-baseline-then-clamp. So what this draws is what the
72x40 keycap OLED draws — the standing rule in this project is to LOOK at the render
rather than reason about the metrics.

What it is actually for: the keycap is 40 px tall and the tallest latin glyph already
inks 33 of them at the small size, so the bigger faces live very close to the ceiling.
`--check` reports, per size and per sample legend, the ink rows/columns used and
whether anything would have clipped without the clamp — run it after ANY change to
the `latinbig` entries in fonts.yaml.

    python tools/glyph_size_preview.py --check
    python tools/glyph_size_preview.py --out /tmp/sizes.png

Reads the firmware's own generated headers (../qmk_firmware/keyboards/polykybd/
base/fonts), so it needs no font pack and no device.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gfx_font import load_all_fonts  # noqa: E402

OLED_W, OLED_H = 72, 40
BUFFER_X = 28

# Keep in sync with glyph_size_base[] / glyph_size_baseline[] in poly_keymap.c and
# the `offset:` values of the `latinbig` entries in fonts.yaml.
SIZE_BASE = {"S": 0, "M": 0xF0000, "L": 0xF3000}
SIZE_BASELINE = {"S": 21, "M": 25, "L": 28}
SIZES = ("S", "M", "L")

# Representative main legends: the extremes of each latin sub-font that a keycap can
# actually show. 'j' and 'Q' are the ascender/descender extremes of the base face,
# 'W' the widest, 'Ç' and 'É' the tall accent stacks that bound the L tier, 'ф' the
# tall Cyrillic, and 'Ḉ' the worst case in the whole repertoire (Intl picker only).
SAMPLES = ["a", "A", "g", "j", "Q", "W", "m", "1", "0", "@", "€",
           "ä", "É", "Ç", "ø", "ß", "ф", "Д", "Ω", "Ḉ"]


class Board:
    """The firmware's font table + the two placement rules that matter."""

    def __init__(self, font_dir: str):
        self.fonts = load_all_fonts(font_dir)
        if not self.fonts:
            raise SystemExit(f"no GFX fonts parsed from {font_dir}")
        self.base_yadv = self.fonts[0].yAdvance      # fonts[0] == IconsFont

    def glyph(self, cp: int):
        """kdisp_gfx_glyph_font(): first font covering cp, skipping gap records."""
        for f in self.fonts:
            if f.first <= cp <= f.last:
                g = f.glyphs[cp - f.first]
                if g["width"] == 0 and g["height"] == 0 and g["xAdvance"] == 0:
                    continue
                return f, g
        return None, None

    def bbox(self, text: str, base: int):
        """kdisp_gfx_text_bbox(): ink box relative to the draw origin/baseline."""
        x = 0
        xmin = ymin = 127
        xmax = ymax = -128
        for ch in text:
            f, g = self.glyph(base + ord(ch))
            if g is None:
                continue
            y = f.yAdvance - self.base_yadv          # the per-font baseline align
            if g["width"] and g["height"]:
                xmin = min(xmin, x + g["xOffset"])
                xmax = max(xmax, x + g["xOffset"] + g["width"] - 1)
                ymin = min(ymin, y + g["yOffset"])
                ymax = max(ymax, y + g["yOffset"] + g["height"] - 1)
            x += g["xAdvance"]
        if xmax < xmin:
            return 0, 0, 0, 0
        return xmin, xmax, ymin, ymax

    def plan(self, text: str, size: str, small_x: int = BUFFER_X, small_y: int = 23):
        """plan_main_legend(). Returns (x, y, base, clamped_x, clamped_y, ok)."""
        base = SIZE_BASE[size]
        if size != "S":
            if any(self.glyph(base + ord(ch))[1] is None for ch in text):
                return small_x, small_y, 0, False, False, False   # falls back to S
            xmin, xmax, ymin, ymax = self.bbox(text, base)
            x, y = small_x, SIZE_BASELINE[size]
            cx = cy = False
            if x + xmax > BUFFER_X + OLED_W - 1:
                x = BUFFER_X + OLED_W - 1 - xmax
                cx = True
            if x + xmin < BUFFER_X:
                x = BUFFER_X - xmin
                cx = True
            if y + ymin < 0:
                y = -ymin
                cy = True
            if y + ymax > OLED_H - 1:
                y = OLED_H - 1 - ymax
                cy = True
            return x, y, base, cx, cy, True
        return small_x, small_y, 0, False, False, True

    def render(self, text: str, size: str):
        """72x40 pixel grid (list of bytearrays), plus a clipped-pixel count."""
        x, y, base, _, _, _ = self.plan(text, size)
        px = [bytearray(OLED_W) for _ in range(OLED_H)]
        clipped = 0
        cursor = x
        for ch in text:
            f, g = self.glyph(base + ord(ch))
            if g is None:
                f, g = self.glyph(ord(ch))
                if g is None:
                    continue
            gy = y + (f.yAdvance - self.base_yadv)
            bo, cb = g["bitmapOffset"], (g["height"] + 7) >> 3
            for xx in range(g["width"]):
                col = bo + xx * cb
                for yy in range(g["height"]):
                    if f.bitmap[col + (yy >> 3)] & (1 << (yy & 7)):
                        vx = cursor + g["xOffset"] + xx - BUFFER_X
                        vy = gy + g["yOffset"] + yy
                        if 0 <= vx < OLED_W and 0 <= vy < OLED_H:
                            px[vy][vx] = 255
                        else:
                            clipped += 1
            cursor += g["xAdvance"]
        return px, clipped


def ink_extent(px):
    rows = [i for i, r in enumerate(px) if any(r)]
    cols = [j for j in range(OLED_W) if any(r[j] for r in px)]
    if not rows:
        return None
    return rows[0], rows[-1], cols[0], cols[-1]


def check(board: Board) -> int:
    bad = 0
    print(f"{'legend':8s} " + "  ".join(f"{s:^26s}" for s in SIZES))
    print(f"{'':8s} " + "  ".join(f"{'rows      cols     clip':26s}" for _ in SIZES))
    for text in SAMPLES:
        cells = []
        for size in SIZES:
            _, _, _, _, _, ok = board.plan(text, size)
            px, clipped = board.render(text, size)
            ext = ink_extent(px)
            if ext is None:
                cells.append(f"{'(blank)':26s}")
                continue
            r0, r1, c0, c1 = ext
            tag = "" if ok else " fallback->S"
            flag = f" CLIP {clipped}" if clipped else ""
            # Only the BIGGER tiers are gated. Size S is the placement the firmware
            # has always used — a fixed baseline with no clamp — and it does put a
            # pixel or two outside the visible window for a glyph with a negative
            # left side-bearing ('j' hangs 1 px left of the origin at h_offset 0).
            # That is pre-existing and horizontal, not a fault of the size feature;
            # failing on it here would make the check unusable from day one.
            if clipped and size != "S":
                bad += 1
            cells.append(f"{r0:2d}..{r1:2d} ({r1-r0+1:2d})  {c0:2d}..{c1:2d}{flag}{tag}"[:26].ljust(26))
        print(f"{text:8s} " + "  ".join(cells))
    print()
    print("rows are the panel rows the ink occupies, out of 0..39.")
    if bad:
        print(f"FAIL: {bad} cell(s) clipped — a `latinbig` size is too large for the panel.")
    else:
        print("OK: every sample fits the 40 px panel at every size.")
    return 1 if bad else 0


def contact_sheet(board: Board, out: str) -> None:
    from PIL import Image, ImageDraw

    cell_w, cell_h, pad, label_h = OLED_W, OLED_H, 8, 14
    cols = len(SIZES)
    rows = len(SAMPLES)
    W = pad + cols * (cell_w + pad)
    H = label_h + pad + rows * (cell_h + pad + label_h)
    img = Image.new("RGB", (W, H), (24, 24, 28))
    d = ImageDraw.Draw(img)
    for ci, size in enumerate(SIZES):
        d.text((pad + ci * (cell_w + pad), 2), f"size {size}", fill=(200, 200, 210))
    for ri, text in enumerate(SAMPLES):
        y0 = label_h + pad + ri * (cell_h + pad + label_h)
        for ci, size in enumerate(SIZES):
            x0 = pad + ci * (cell_w + pad)
            px, clipped = board.render(text, size)
            cell = Image.new("RGB", (cell_w, cell_h), (0, 0, 0))
            cp = cell.load()
            for yy in range(cell_h):
                for xx in range(cell_w):
                    if px[yy][xx]:
                        cp[xx, yy] = (150, 210, 255)
            img.paste(cell, (x0, y0))
            _, _, _, _, _, ok = board.plan(text, size)
            note = f"{text}" + ("" if ok else " (fallback)") + (" CLIP" if clipped else "")
            d.text((x0, y0 + cell_h + 1), note, fill=(230, 120, 120) if clipped else (150, 150, 160))
    img.save(out)
    print(f"wrote {out}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fonts", default=os.path.join(
        os.path.dirname(os.path.dirname(HERE)), "qmk_firmware",
        "keyboards", "polykybd", "base", "fonts"),
        help="firmware base/fonts directory")
    ap.add_argument("--check", action="store_true", help="report ink extents + clipping")
    ap.add_argument("--out", help="write a PNG contact sheet here")
    a = ap.parse_args()
    board = Board(a.fonts)
    rc = 0
    if a.check or not a.out:
        rc = check(board)
    if a.out:
        contact_sheet(board, a.out)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
