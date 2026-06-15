#!/usr/bin/env python3
"""Fetch + render the Microsoft PowerPoint shortcut icons (reproducible).

All glyphs are Microsoft Fluent UI System Icons (MIT) — native style for a MS app,
license-clean (host is GPL-2.0). Rendered to 96x96 RGBA PNG; the generator's
`luma` mode keeps the linework at 1-bit. The program icon (ESC) is a generic mark
drawn in code (no Microsoft logo): the Word-style trapezoid + knocked-out 'P' +
rounded rect with text lines. Intended to be hand-tuned.

    pip install cairosvg
    python polyhost/res/overlay_sources/powerpoint/fetch_icons.py
"""
from __future__ import annotations

import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RENDER_PX = 96
MS = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/{}"

MS_ICONS = {
    "new": "Document Add/SVG/ic_fluent_document_add_24_regular.svg",
    "open": "Folder Open/SVG/ic_fluent_folder_open_24_regular.svg",
    "save": "Save/SVG/ic_fluent_save_24_regular.svg",
    "saveas": "Save Edit/SVG/ic_fluent_save_edit_24_regular.svg",
    "print": "Print/SVG/ic_fluent_print_24_regular.svg",
    "newslide": "Slide Add/SVG/ic_fluent_slide_add_24_regular.svg",
    "duplicate": "Square Multiple/SVG/ic_fluent_square_multiple_24_regular.svg",
    "copy": "Copy/SVG/ic_fluent_copy_24_regular.svg",
    "cut": "Cut/SVG/ic_fluent_cut_24_regular.svg",
    "paste": "Clipboard Paste/SVG/ic_fluent_clipboard_paste_24_regular.svg",
    "undo": "Arrow Undo/SVG/ic_fluent_arrow_undo_24_regular.svg",
    "redo": "Arrow Redo/SVG/ic_fluent_arrow_redo_24_regular.svg",
    "selectall": "Select All On/SVG/ic_fluent_select_all_on_24_regular.svg",
    "bold": "Text Bold/SVG/ic_fluent_text_bold_24_regular.svg",
    "italic": "Text Italic/SVG/ic_fluent_text_italic_24_regular.svg",
    "underline": "Text Underline/SVG/ic_fluent_text_underline_24_regular.svg",
    "hyperlink": "Link/SVG/ic_fluent_link_24_regular.svg",
    "group": "Group/SVG/ic_fluent_group_24_regular.svg",
    "ungroup": "Group Dismiss/SVG/ic_fluent_group_dismiss_24_regular.svg",
    "find": "Search/SVG/ic_fluent_search_24_regular.svg",
    "slideshow": "Play/SVG/ic_fluent_play_24_regular.svg",
    "fromcurrent": "Play Circle/SVG/ic_fluent_play_circle_24_regular.svg",
    "spelling": "Text Grammar Checkmark/SVG/ic_fluent_text_grammar_checkmark_24_regular.svg",
    "copyformat": "Paint Brush/SVG/ic_fluent_paint_brush_24_regular.svg",
    "left": "Text Align Left/SVG/ic_fluent_text_align_left_24_regular.svg",
    "center": "Text Align Center/SVG/ic_fluent_text_align_center_24_regular.svg",
    "right": "Text Align Right/SVG/ic_fluent_text_align_right_24_regular.svg",
    "justify": "Text Align Justify/SVG/ic_fluent_text_align_justify_24_regular.svg",
    "replace": "Arrow Swap/SVG/ic_fluent_arrow_swap_24_regular.svg",
    "fontinc": "Font Increase/SVG/ic_fluent_font_increase_24_regular.svg",
    "fontdec": "Font Decrease/SVG/ic_fluent_font_decrease_24_regular.svg",
    "subscript": "Text Subscript/SVG/ic_fluent_text_subscript_24_regular.svg",
    "font": "Text Font/SVG/ic_fluent_text_font_24_regular.svg",
    "close": "Document Dismiss/SVG/ic_fluent_document_dismiss_24_regular.svg",
}


def _draw_powerpoint_logo(path: Path) -> None:
    """Generic, license-clean 'PowerPoint' program icon (no Microsoft logo): the
    Word-style mark (trapezoid + knocked-out letter + rounded rect with text
    lines) with the letter 'P'. White shape on transparent (alpha = lit shape)
    -> `program_icon_mode: alpha`."""
    ss = 4
    u = RENDER_PX * ss
    px = lambda n: n * ss

    right = Image.new("L", (u, u), 0)
    dr = ImageDraw.Draw(right)
    dr.rounded_rectangle([0.50 * u, 0.24 * u, 0.93 * u, 0.76 * u],
                         radius=0.10 * u, outline=255, width=px(3))
    for y in (0.36, 0.50, 0.64):
        dr.line([(0.58 * u, y * u), (0.86 * u, y * u)], fill=255, width=int(u * 0.05))

    right_x = 0.58 * u
    trap = Image.new("L", (u, u), 0)
    ImageDraw.Draw(trap).polygon(
        [(0.10 * u, 0.20 * u), (right_x, 0.11 * u),
         (right_x, 0.89 * u), (0.10 * u, 0.80 * u)], fill=255)
    wmask = Image.new("L", (u, u), 0)
    dw = ImageDraw.Draw(wmask)
    font = None
    for cand in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(cand, int(u * 0.34))
            break
        except OSError:
            continue
    if font:
        bb = dw.textbbox((0, 0), "P", font=font)
        cx, cy = (0.10 * u + right_x) / 2, 0.50 * u
        dw.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
                "P", font=font, fill=255)
    knock = np.where(np.asarray(wmask) > 127, 0, np.asarray(trap)).astype(np.uint8)

    alpha = np.maximum(np.asarray(right), knock)
    rgba = np.zeros((u, u, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = alpha
    Image.fromarray(rgba, "RGBA").resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for fname, asset in MS_ICONS.items():
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        png = cairosvg.svg2png(bytestring=_get(MS.format(enc)),
                               output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- ms-fluent/{asset.split('/')[0]}")
    if (out / "powerpoint.png").exists():
        print("  powerpoint.png  <- committed asset (left as-is)")
    else:
        _draw_powerpoint_logo(out / "powerpoint.png")
        print("  powerpoint.png  <- generic drawn (trapezoid + knocked-out P + text lines)")
    print(f"Wrote {len(MS_ICONS) + 1} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
