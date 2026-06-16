#!/usr/bin/env python3
"""Fetch + render the Microsoft Word shortcut icons (reproducible).

All glyphs are Microsoft Fluent UI System Icons (MIT) — native style for a MS app,
license-clean (host is GPL-3.0-or-later). Rendered to 96x96 RGBA PNG; the generator's
`luma` mode keeps the linework at 1-bit. The program icon (ESC) is a Fluent
document glyph placeholder — drop a real Word logo as icons/word.png to override
(committed assets are left untouched).

    pip install cairosvg
    python polyhost/res/overlay_sources/word/fetch_icons.py
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
    "copy": "Copy/SVG/ic_fluent_copy_24_regular.svg",
    "cut": "Cut/SVG/ic_fluent_cut_24_regular.svg",
    "paste": "Clipboard Paste/SVG/ic_fluent_clipboard_paste_24_regular.svg",
    "undo": "Arrow Undo/SVG/ic_fluent_arrow_undo_24_regular.svg",
    "redo": "Arrow Redo/SVG/ic_fluent_arrow_redo_24_regular.svg",
    "selectall": "Select All On/SVG/ic_fluent_select_all_on_24_regular.svg",
    "bold": "Text Bold/SVG/ic_fluent_text_bold_24_regular.svg",
    "italic": "Text Italic/SVG/ic_fluent_text_italic_24_regular.svg",
    "underline": "Text Underline/SVG/ic_fluent_text_underline_24_regular.svg",
    "font": "Text Font/SVG/ic_fluent_text_font_24_regular.svg",
    "indent": "Text Indent Increase/SVG/ic_fluent_text_indent_increase_24_regular.svg",
    "close": "Document Dismiss/SVG/ic_fluent_document_dismiss_24_regular.svg",
    "fontdec": "Font Decrease/SVG/ic_fluent_font_decrease_24_regular.svg",
    "fontinc": "Font Increase/SVG/ic_fluent_font_increase_24_regular.svg",
    "subscript": "Text Subscript/SVG/ic_fluent_text_subscript_24_regular.svg",
    "hyphen": "Subtract/SVG/ic_fluent_subtract_24_regular.svg",
    "clearfmt": "Text Clear Formatting/SVG/ic_fluent_text_clear_formatting_24_regular.svg",
    "linespacing": "Text Line Spacing/SVG/ic_fluent_text_line_spacing_24_regular.svg",
    "center": "Text Align Center/SVG/ic_fluent_text_align_center_24_regular.svg",
    "left": "Text Align Left/SVG/ic_fluent_text_align_left_24_regular.svg",
    "right": "Text Align Right/SVG/ic_fluent_text_align_right_24_regular.svg",
    "justify": "Text Align Justify/SVG/ic_fluent_text_align_justify_24_regular.svg",
    "bullets": "Text Bullet List/SVG/ic_fluent_text_bullet_list_24_regular.svg",
    "find": "Search/SVG/ic_fluent_search_24_regular.svg",
    "replace": "Arrow Swap/SVG/ic_fluent_arrow_swap_24_regular.svg",
    "goto": "Arrow Down/SVG/ic_fluent_arrow_down_24_regular.svg",
    "hyperlink": "Link/SVG/ic_fluent_link_24_regular.svg",
    "changecase": "Text Change Case/SVG/ic_fluent_text_change_case_24_regular.svg",
    "copyformat": "Paint Brush/SVG/ic_fluent_paint_brush_24_regular.svg",
    "spelling": "Text Grammar Checkmark/SVG/ic_fluent_text_grammar_checkmark_24_regular.svg",
}


def _draw_word_logo(path: Path) -> None:
    """Generic, license-clean 'Word' program icon (no Microsoft logo): a
    90deg-rotated trapezoid on the left with a 'W' stamped out (negative space),
    plus a few text lines on the right. White shape on transparent (alpha = the
    lit shape), rendered with `program_icon_mode: alpha`."""
    ss = 4
    u = RENDER_PX * ss
    px = lambda n: n * ss          # final px -> supersampled px

    # rounded rectangle around the text lines (right), with the lines inside
    right = Image.new("L", (u, u), 0)
    dr = ImageDraw.Draw(right)
    dr.rounded_rectangle([0.50 * u, 0.24 * u, 0.93 * u, 0.76 * u],
                         radius=0.10 * u, outline=255, width=px(3))
    for y in (0.36, 0.50, 0.64):
        dr.line([(0.58 * u, y * u), (0.86 * u, y * u)], fill=255, width=int(u * 0.05))

    # left trapezoid (parallel vertical sides, right side taller -> looks rotated),
    # extended right so it overlaps well into the rounded rect and hides its left edge
    right_x = 0.58 * u
    trap = Image.new("L", (u, u), 0)
    ImageDraw.Draw(trap).polygon(
        [(0.10 * u, 0.20 * u), (right_x, 0.11 * u),
         (right_x, 0.89 * u), (0.10 * u, 0.80 * u)], fill=255)
    # 'W' to knock out of the trapezoid
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
        bb = dw.textbbox((0, 0), "W", font=font)
        cx, cy = (0.10 * u + right_x) / 2, 0.50 * u
        dw.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
                "W", font=font, fill=255)
    knock = np.where(np.asarray(wmask) > 127, 0, np.asarray(trap)).astype(np.uint8)

    # trapezoid drawn on top of the rounded rect -> its solid fill swallows the
    # rect's left edge (max() merges the overlap into one lit shape)
    alpha = np.maximum(np.asarray(right), knock)
    rgba = np.zeros((u, u, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = alpha
    Image.fromarray(rgba, "RGBA").resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def _draw_hangindent(path: Path) -> None:
    """Hanging-indent glyph (distinct from plain indent): first line flush left,
    following lines indented to the right. White on transparent (mode: alpha)."""
    ss = 4
    u = RENDER_PX * ss
    w = int(u * 0.06)
    white = (255, 255, 255, 255)
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(0.14 * u, 0.24 * u), (0.86 * u, 0.24 * u)], fill=white, width=w)   # first line flush
    for y in (0.44, 0.62, 0.80):                                                # rest indented right
        d.line([(0.40 * u, y * u), (0.86 * u, y * u)], fill=white, width=w)
    img.resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def _compose_linespacing(out: Path) -> None:
    """Compose 3 line-spacing icons: the value (1 / 1½ / 2) in a fixed font size,
    placed statically 1px below the top, with the line-spacing glyph beneath it.
    White on transparent (mode: alpha)."""
    p = RENDER_PX
    base = Image.open(out / "linespacing.png").convert("RGBA").split()[3]
    glyph = base.crop(base.getbbox())                    # crop the icon's own padding

    SIZE = int(p * 0.46)                                  # fixed font size
    font = None  # Arial (proprietary) -> Liberation Sans, a metric-compatible drop-in
    for cand in ("Arial.ttf", "LiberationSans-Regular.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        try:
            font = ImageFont.truetype(cand, SIZE)
            break
        except OSError:
            continue

    num_baseline = 30                                     # FIXED: keeps the numbers put
    glyph_top = 28                                         # lower start -> bigger glyph
    gw, ghh = glyph.size
    s = min(p / gw, (p - glyph_top) / ghh)
    g = glyph.resize((max(1, int(gw * s)), max(1, int(ghh * s))), Image.LANCZOS)

    # common left edge (centred on the widest value) so the leading digit is in
    # the exact same spot in every icon -> the "1" is identical in "1" and "1½"
    x_left = (p - ImageDraw.Draw(Image.new("L", (1, 1))).textlength("1½", font=font)) / 2

    for fname, num in (("linespacing1.png", "1"), ("linespacing15.png", "1½"),
                       ("linespacing2.png", "2")):
        mask = Image.new("L", (p, p), 0)
        d = ImageDraw.Draw(mask)
        d.text((x_left, num_baseline), num, font=font, fill=255, anchor="ls")  # left+baseline, fixed
        mask.paste(g, ((p - g.size[0]) // 2, glyph_top))
        rgba = np.zeros((p, p, 4), np.uint8)
        rgba[..., :3] = 255
        rgba[..., 3] = np.asarray(mask)
        Image.fromarray(rgba, "RGBA").save(out / fname)
        print(f"  {fname}  <- composed ({num} + line-spacing glyph)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for fname, asset in MS_ICONS.items():
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        png = cairosvg.svg2png(bytestring=_get(MS.format(enc)),
                               output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- ms-fluent/{asset.split('/')[0]}")
    _draw_word_logo(out / "word.png") if not (out / "word.png").exists() else \
        print("  word.png  <- committed asset (left as-is)")
    _draw_hangindent(out / "hangindent.png") if not (out / "hangindent.png").exists() else \
        print("  hangindent.png  <- committed asset (left as-is)")
    if (out / "linespacing1.png").exists():
        print("  linespacing*.png  <- committed assets (left as-is)")
    else:
        _compose_linespacing(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
