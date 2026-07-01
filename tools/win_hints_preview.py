#!/usr/bin/env python3
"""Render a labelled contact sheet of the proposed Windows Win+<key> shortcut
hints, exactly the way the firmware draws them (N leading spaces + glyph,
starting at BUFFER_X, baseline-aligned per font), straight from the generated
GFX headers. Run from the PolyKybdHost repo root.

    .venv/bin/python tools/win_hints_preview.py --out /tmp/win_hints.png
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))  # tools/
from gfx_font import GfxGlyphRenderer, OLED_W, OLED_H, BUFFER_X  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

FONTDIR = os.environ.get("POLYKYBD_FONTS", os.path.abspath(os.path.join(
    os.path.dirname(__file__), "../../qmk_firmware/keyboards/polykybd/base/fonts")))
R = GfxGlyphRenderer(FONTDIR)
SP = 0x20

# (shortcut label, action, [codepoints], frame?)  -- codepoints are ints
HINTS = [
    ("Win+A",            "Action Center / Quick Settings", [0x1F514], False),
    ("Win+E",            "File Explorer",                  [0x1F4C1], False),
    ("Win+R",            "Run dialog",                     [0x9A, 0x9B], True),
    ("Win+U",            "Accessibility settings",         [0x267F], False),
    ("Win+Home",         "Minimize all but active",        [0x2750], False),
    ("Win+Left",         "Snap window left",               [0x83], False),
    ("Win+Right",        "Snap window right",              [0x84], False),
    ("Win+Ctrl+D",       "New virtual desktop",            [0x271A], False),
    ("Win+Ctrl+Left",    "Prev virtual desktop",           [0x276E], False),
    ("Win+Ctrl+Right",   "Next virtual desktop",           [0x276F], False),
    ("Win+Ctrl+F4",      "Close virtual desktop",          [0x22A0], False),
    ("Win+;",            "GIF / emoji panel",              [0x1F4FD], False),
    ("Win+Shift+S",      "Snipping tool",                  [0x2704], False),
    ("Win+Alt+R",        "Screen recording",               [0x1F4F9], False),
    ("Win+1..9",         "Taskbar app N",                  [0x1F4CC], False),
    ("Win+B",            "Focus system tray",              [0x81], False),
    ("Win+Ctrl+Shift+B", "Restart graphics driver",        [0x1F5D8], False),
    ("Win+Pause",        "System properties",              [0x1F4BB], False),
    ("Win+Plus/Minus",   "Magnifier zoom",                 [0x1F50D], False),
    ("Win+PrtScn",       "Screenshot to folder",           [0x1F4F7], False),
    ("Win+Ctrl+F",       "Search network computers",       [0x1F310], False),
]


def render_cell(cps):
    """Pick the largest leading-space count (0..6) that keeps the glyph inside
    the visible window, render it, and return (PIL 'L' image, nsp, (min_x,max_x))."""
    best = None
    fallback = None
    for nsp in range(0, 7):
        img = Image.new("L", (OLED_W, OLED_H), 0)
        px = img.load()
        x = BUFFER_X
        for cp in [SP] * nsp + cps:
            x = R._blit(px, cp, x)
        pts = [(xx, yy) for yy in range(OLED_H) for xx in range(OLED_W) if px[xx, yy]]
        if not pts:
            continue
        xs = [p[0] for p in pts]
        mn, mx = min(xs), max(xs)
        clip = mx >= 71 or mn <= 0
        if not clip:
            best = (img, nsp, (mn, mx))
        if fallback is None or mx < fallback[2][1]:
            fallback = (img, nsp, (mn, mx))
    # Degenerate case: every candidate rendered empty (e.g. a hint that resolves
    # only to gap glyphs) -> return a blank cell with a neutral box, don't crash.
    return best or fallback or (Image.new("L", (OLED_W, OLED_H), 0), 0, (0, 0))


def add_frame(img, box):
    """Draw a 2px rounded-rect outline hugging the glyph bbox (preview of the
    proposed Win+R frame)."""
    mn, mx = box
    d = ImageDraw.Draw(img)
    x0, x1 = mn - 3, mx + 3
    y0, y1 = 4, OLED_H - 5
    for t in range(2):                       # 2px thick
        d.rounded_rectangle([x0 - t, y0 - t, x1 + t, y1 + t], radius=4, outline=255)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/win_hints.png")
    ap.add_argument("--scale", type=int, default=5)
    a = ap.parse_args()

    scale = a.scale
    cell_w, cell_h = OLED_W * scale, OLED_H * scale
    label_h = 30
    cols = 3
    rows = (len(HINTS) + cols - 1) // cols
    pad = 10
    sheet_w = cols * (cell_w + pad) + pad
    sheet_h = rows * (cell_h + label_h + pad) + pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
        sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        font = sub = ImageFont.load_default()

    for i, (label, action, cps, frame) in enumerate(HINTS):
        r, c = divmod(i, cols)
        ox = pad + c * (cell_w + pad)
        oy = pad + r * (cell_h + label_h + pad)
        cell, nsp, box = render_cell(cps)
        if frame:
            cell = add_frame(cell.copy(), box)
        # white-on-black, as the OLED shows it
        big = cell.convert("RGB").resize((cell_w, cell_h), Image.NEAREST)
        sheet.paste(big, (ox, oy))
        draw.rectangle([ox, oy, ox + cell_w - 1, oy + cell_h - 1], outline=(80, 80, 80))
        draw.text((ox + 2, oy + cell_h + 1), label, fill=(255, 230, 120), font=font)
        draw.text((ox + 2, oy + cell_h + 16), action, fill=(170, 170, 170), font=sub)

    sheet.save(a.out)
    print(f"wrote {a.out}  ({sheet_w}x{sheet_h}, {len(HINTS)} hints)")


if __name__ == "__main__":
    main()
