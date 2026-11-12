#!/usr/bin/env python3
"""Fetch + render the Microsoft Visio shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. The program icon (ESC) is
the Office-family drawn mark with a "V" (no Microsoft logo); a committed
`visio.png` is left as-is.

    pip install cairosvg Pillow numpy
    python polyhost/res/overlay_sources/visio/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RENDER_PX = 96

FLUENT = {
    # --- tools (Ctrl+1..9, Ctrl+Shift+1/2/4) ---
    "pointer": "Cursor",
    "texttool": "Text T",
    "connector": "ms:conversion_path",
    "pencil": "Edit",
    "freeform": "Draw Shape",
    "line": "Line",
    "arc": "ms:line_curve",
    "rectangle": "Rectangle Landscape",
    "ellipse": "Oval",
    "connpoint": "Target",
    "crop": "Crop",
    "textblock": "Text Box Settings",
    "formatpainter": "Paint Brush",
    # --- arrange ---
    "group": "Group",
    "ungroup": "Group Dismiss",
    "front": "ms:flip_to_front",
    "back": "ms:flip_to_back",
    "rotleft": "Arrow Rotate Counterclockwise",
    "rotright": "Arrow Rotate Clockwise",
    "fliph": "Flip Horizontal",
    "flipv": "Flip Vertical",
    "alignshapes": "Align Center Horizontal",
    "snapglue": "Grid Dots",
    # --- text ---
    "bold": "Text Bold",
    "italic": "Text Italic",
    "underline": "Text Underline",
    "dblunderline": "Text Underline Double",
    "allcaps": "Text Case Uppercase",
    "smallcaps": "Text Case Title",
    "superscript": "Text Superscript",
    "subscript": "Text Subscript",
    "fontinc": "Font Increase",
    "fontdec": "Font Decrease",
    "left": "Text Align Left",
    "center": "Text Align Center",
    "right": "Text Align Right",
    "justify": "Text Align Justify",
    "vtop": "Align Top",
    "vmiddle": "Align Center Vertical",
    "vbottom": "Align Bottom",
    "textdialog": "Text Font",
    "formatshape": "Paint Bucket",
    "edittext": "Text Edit Style",
    # --- view, windows, pages ---
    "fullscreen": "Full Screen Maximize",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "fitwindow": "Zoom Fit",
    "tilevert": "Split Vertical",
    "tilehoriz": "Split Horizontal",
    "cascade": "Window Multiple",
    "reorderpages": "Arrow Sort",
    "pagesetup": "Document Page Number",
    "nextdrawing": "Arrow Circle Right",
    "prevdrawing": "Arrow Circle Left",
    "nextpage": "Document Arrow Down",
    "prevpage": "Document Arrow Up",
    "insertmaster": "Shapes",
}


def _draw_visio_logo(path: Path) -> None:
    """Office-family program icon, drawn (no Microsoft logo): the rotated
    trapezoid on the left with a 'V' knocked out, plus a rounded rect on the
    right holding a small diagram (two boxes and a connector). Same geometry
    as Word's mark (`../word/fetch_icons.py`), so the family reads as one set.
    White on transparent; the bindings render it with `program_icon_mode: alpha`."""
    ss = 4
    u = RENDER_PX * ss
    px = lambda n: n * ss          # final px -> supersampled px

    right = Image.new("L", (u, u), 0)
    dr = ImageDraw.Draw(right)
    dr.rounded_rectangle([0.50 * u, 0.24 * u, 0.93 * u, 0.76 * u],
                         radius=0.10 * u, outline=255, width=px(3))
    dr.rectangle([0.64 * u, 0.33 * u, 0.84 * u, 0.43 * u], fill=255)
    dr.rectangle([0.64 * u, 0.57 * u, 0.84 * u, 0.67 * u], fill=255)
    dr.line([(0.74 * u, 0.43 * u), (0.74 * u, 0.57 * u)], fill=255, width=px(3))

    right_x = 0.58 * u
    trap = Image.new("L", (u, u), 0)
    ImageDraw.Draw(trap).polygon(
        [(0.10 * u, 0.20 * u), (right_x, 0.11 * u),
         (right_x, 0.89 * u), (0.10 * u, 0.80 * u)], fill=255)
    vmask = Image.new("L", (u, u), 0)
    dv = ImageDraw.Draw(vmask)
    font = None
    for cand in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(cand, int(u * 0.34))
            break
        except OSError:
            continue
    if font:
        bb = dv.textbbox((0, 0), "V", font=font)
        cx, cy = (0.10 * u + right_x) / 2, 0.50 * u
        dv.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
                "V", font=font, fill=255)
    knock = np.where(np.asarray(vmask) > 127, 0, np.asarray(trap)).astype(np.uint8)

    alpha = np.maximum(np.asarray(right), knock)
    rgba = np.zeros((u, u, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = alpha
    Image.fromarray(rgba, "RGBA").resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    if (out / "visio.png").exists():
        print("  visio.png  <- committed asset (left as-is)")
    else:
        _draw_visio_logo(out / "visio.png")
        print("  visio.png  <- drawn program mark")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
