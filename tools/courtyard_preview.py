#!/usr/bin/env python3
"""Prototype / comparison harness for the per-keycap "courtyard" clear that runs
behind a glyph drawn over an overlay icon (firmware:
base/disp_array.c kdisp_clear_bitmap_courtyard).

The OLED preview (oled_preview.py) draws glyphs on a black background, so the
courtyard clear is invisible there. This tool lays each glyph over a hatched
stand-in "overlay" and shows what each clearing strategy erases, side by side:

    no-clear | current (per-row span + top taper) | per-column extents | dilation

so the relative over/under-clearing is obvious. Glyph rendering reuses
gfx_font.load_all_fonts() — the same pixel-exact GFX renderer the firmware and
oled_preview use — so the shapes match the hardware.

Usage:
    python tools/courtyard_preview.py                      # default sample set
    python tools/courtyard_preview.py --chars '"M W % = ü @ A 5'
    python tools/courtyard_preview.py --scale 6 --out /tmp/cy.png
"""
from __future__ import annotations
import argparse, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from gfx_font import load_all_fonts, OLED_W, OLED_H, BUFFER_X, BASELINE
from oled_preview import Renderer

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.dirname(os.path.dirname(HERE))


# ---- glyph -> centered 72x40 boolean mask --------------------------------
def glyph_mask(R: Renderer, cps: list[int]) -> np.ndarray:
    img = Image.new('L', (OLED_W, OLED_H), 0)
    px = img.load()
    mn, mx = R.bounds(cps)
    xc = BUFFER_X + (OLED_W - (mx - mn)) // 2 - mn      # horizontal centering
    R.draw(px, cps, xc, BASELINE)
    return np.array(img, dtype=bool)


# ---- strategy A: current firmware algorithm (faithful port) ---------------
def courtyard_current(mask: np.ndarray) -> np.ndarray:
    """Port of kdisp_clear_bitmap_courtyard as it currently stands (per-row
    [first,last] span with +/-3 horizontal margin, a continuous top-edge taper
    16/12/8/4/2/0, and the exponential outer/bottom fade)."""
    H, W = mask.shape
    cleared = np.zeros_like(mask)

    def clear_line(fr, to, row):
        if 0 <= row < H:
            a, b = max(0, fr), min(W, to)
            if a < b:
                cleared[row, a:b] = True

    first, last, num_empty = 127, 0, 0
    prev_empty, top_count = True, 0
    for by in range(H):
        num_empty += 1
        for bx in range(W):
            if mask[by, bx]:
                first = min(bx - 3, first)
                last = max(bx + 3, last)
                num_empty = 0
        if first != 127:
            if num_empty == 0:
                top_count = 0 if prev_empty else (top_count + 1 if top_count < 3 else 3)
                if top_count == 0:
                    clear_line(first + 16, last - 16, by - 2)
                    clear_line(first + 12, last - 12, by - 1)
                inset = (8, 4, 2, 0)[top_count]
                clear_line(first + inset, last - inset, by)
                prev_empty = False
            else:
                num_empty = min(num_empty, 6)
                clear_line(first, last, by)
                prev_empty = True
            dist = 2 ** (num_empty + 1)
            first += dist
            last -= dist
            if first >= last:
                first, last, num_empty = 127, 0, 0
    return cleared


# ---- strategy B: per-column vertical extents (+ horizontal margin) --------
def courtyard_column(mask: np.ndarray, mh: int = 3, mv: int = 2) -> np.ndarray:
    """For each column, clear from the topmost to the bottommost glyph pixel
    (+/- mv rows), dilated +/- mh columns. Never bridges horizontally-separated
    strokes the way a single per-row span does."""
    H, W = mask.shape
    band = np.zeros_like(mask)
    for bx in range(W):
        col = np.flatnonzero(mask[:, bx])
        if col.size == 0:
            continue
        y0, y1 = max(0, col.min() - mv), min(H, col.max() + 1 + mv)
        band[y0:y1, bx] = True
    # horizontal dilation by mh
    out = band.copy()
    for dx in range(1, mh + 1):
        out[:, dx:] |= band[:, :-dx]
        out[:, :-dx] |= band[:, dx:]
    return out


# ---- strategy C: morphological dilation (square structuring element) ------
def courtyard_dilate(mask: np.ndarray, r: int = 3) -> np.ndarray:
    img = Image.fromarray((mask * 255).astype('uint8'))
    out = img.filter(ImageFilter.MaxFilter(2 * r + 1))
    return np.array(out, dtype=bool)


# ---- compositing ----------------------------------------------------------
def hatch_overlay(shape) -> np.ndarray:
    """Mid-gray diagonal hatch standing in for an overlay icon."""
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W]
    bg = np.where(((xx + yy) % 4) < 2, 130, 60).astype('uint8')
    return bg


def composite(mask, cleared, scale):
    bg = hatch_overlay(mask.shape)
    out = bg.copy()
    if cleared is not None:
        out[cleared] = 0          # courtyard cleared to black
    out[mask] = 255               # glyph on top
    img = Image.fromarray(out, 'L').resize(
        (OLED_W * scale, OLED_H * scale), Image.NEAREST)
    return img.convert('RGB')


PANELS = [
    ("no clear", lambda m: None),
    ("current (per-row + taper)", courtyard_current),
    ("per-column extents", courtyard_column),
    ("dilation r=3", courtyard_dilate),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chars', default='" M W % = ü @ A 5 j',
                    help='space-separated characters to render')
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'))
    ap.add_argument('--scale', type=int, default=6)
    ap.add_argument('--out', default=os.path.join(HERE, 'out', 'courtyard_compare.png'))
    a = ap.parse_args()

    pk = os.path.join(a.qmk, 'keyboards', 'handwired', 'polykybd')
    R = Renderer(load_all_fonts(os.path.join(pk, 'base', 'fonts')))
    chars = [c for c in a.chars.split(' ') if c != '']

    s = a.scale
    cw, chh = OLED_W * s, OLED_H * s
    pad, lab_h, hdr = 6, 14, 20
    ncol = len(PANELS)
    W = pad + ncol * (cw + pad)
    H = hdr + len(chars) * (chh + lab_h + pad) + pad
    sheet = Image.new('RGB', (W, H), (32, 32, 32))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 11)
    except Exception:
        font = ImageFont.load_default()

    for ci, (name, _) in enumerate(PANELS):
        d.text((pad + ci * (cw + pad), 4), name, font=font, fill=(255, 255, 0))

    for ri, ch in enumerate(chars):
        mask = glyph_mask(R, [ord(c) for c in ch])
        y = hdr + ri * (chh + lab_h + pad)
        for ci, (name, fn) in enumerate(PANELS):
            x = pad + ci * (cw + pad)
            cleared = fn(mask) if fn(mask) is not None else None
            panel = composite(mask, cleared, s)
            sheet.paste(panel, (x, y + lab_h))
            d.rectangle([x, y + lab_h, x + cw - 1, y + lab_h + chh - 1],
                        outline=(70, 70, 70))
        d.text((pad, y), f"U+{ord(ch[0]):04X} {ch!r}", font=font, fill=(180, 180, 180))

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    sheet.save(a.out)
    print("wrote", a.out)


if __name__ == '__main__':
    main()
