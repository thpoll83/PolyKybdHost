#!/usr/bin/env python3
"""Fetch + render the Mathematica / Wolfram shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. No program icon: the host
draws the ESC mark for the app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/mathematica/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RENDER_PX = 96
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Typeset as text: no icon set has a radical sign, and a percent sign reads as
# percent, not as a fraction.
TEXT_GLYPHS = {"radical": "\u221ax", "fraction": "x/y"}

FLUENT = {
    # --- file and edit ---
    "printsel": "Print Add",
    "close": "Dismiss Square",
    "clear": "Eraser",
    "copytext": "ms:text_snippet",
    "extendsel": "ms:expand_content",
    "balance": "ms:data_array",
    "iconize": "ms:compress",
    "comment": "Comment",
    "complete": "ms:auto_fix_high",
    "template": "ms:data_object",
    "spelling": "Text Grammar Checkmark",
    "entersel": "ms:manage_search",
    "findprev": "Arrow Previous",
    # --- insert and typesetting ---
    "inputabove": "ms:file_upload",
    "outputabove": "ms:output",
    "samestyle": "ms:add_row_below",
    "freeform": "ms:chat_bubble",
    "hyperlink": "Link",
    "superscript": "Text Superscript",
    "subscript": "Text Subscript",
    "above": "ms:keyboard_double_arrow_up",
    "opposite": "ms:swap_vert",
    "endsub": "ms:arrow_right_alt",
    "addrow": "Table Insert Row",
    "addcol": "Table Insert Column",
    "newcanvas": "ms:draw",
    "canvas": "ms:edit_square",
    # --- format ---
    "clearfmt": "Text Clear Formatting",
    "optinspector": "ms:tune",
    "title": "ms:title",
    "chapter": "ms:book",
    "subchapter": "ms:auto_stories",
    "section": "Text Header 1",
    "subsection": "Text Header 2",
    "subsubsection": "Text Header 3",
    "text": "ms:notes",
    "code": "Code",
    "input": "ms:input",
    "bold": "Text Bold",
    "italic": "Text Italic",
    "underline": "Text Underline",
    "larger": "Font Increase",
    "smaller": "Font Decrease",
    # --- cell ---
    "divide": "ms:call_split",
    "merge": "ms:merge",
    "showexpr": "ms:code_blocks",
    "inputform": "ms:keyboard_alt",
    "rawinputform": "ms:raw_on",
    "standardform": "ms:functions",
    "traditionalform": "Math Formula",
    "celltags": "Tag",
    "group": "ms:stack",
    "ungroup": "ms:stack_off",
    "openall": "ms:unfold_more",
    "closeall": "ms:unfold_less",
    "openclose": "ms:expand",
    # --- evaluation, window, help ---
    "evaluate": "Play",
    "evalinplace": "ms:resume",
    "subsession": "ms:subdirectory_arrow_right",
    "abort": "Stop",
    "removequeue": "ms:playlist_remove",
    "fullscreen": "Full Screen Maximize",
    "findfunction": "Book Question Mark",
    # --- navigation ---
    "notebookstart": "ms:vertical_align_top",
    "notebookend": "ms:vertical_align_bottom",
    "nextexpr": "ms:keyboard_tab",
    "prevexpr": "ms:keyboard_tab_rtl",
    "delprev": "ms:backspace",
}


def _draw_text(path: Path, text: str) -> None:
    """Black text on transparent, like the fetched glyphs."""
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(RENDER_PX * 0.55))
    box = d.textbbox((0, 0), text, font=font)
    x = (RENDER_PX - (box[2] - box[0])) / 2 - box[0]
    y = (RENDER_PX - (box[3] - box[1])) / 2 - box[1]
    d.text((x, y), text, font=font, fill=(0, 0, 0, 255))
    img.save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    for name, text in TEXT_GLYPHS.items():
        _draw_text(out / f"{name}.png", text)
        print(f"  {name}.png  <- text {text!r} (DejaVu Sans Bold)")
        n += 1
    # Delete Next Expression: the backspace glyph, pointing forward.
    ImageOps.mirror(Image.open(out / "delprev.png")).save(out / "delnext.png")
    print("  delnext.png  <- delprev.png mirrored")
    n += 1
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
