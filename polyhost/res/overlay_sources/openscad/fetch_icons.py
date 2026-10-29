#!/usr/bin/env python3
"""Fetch + render the OpenSCAD shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. The view names, the
comment marks and the number step are text in DejaVu Sans Bold; the next and previous bookmark icons add a triangle to
the bookmark glyph. No program
icon: the host draws the ESC mark for the app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/openscad/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RENDER_PX = 96
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

FLUENT = {
    # --- file and edit ---
    "reload": "ms:refresh",
    "indent": "ms:format_indent_increase",
    "unindent": "ms:format_indent_decrease",
    "lineup": "ms:move_up",
    "linedown": "ms:move_down",
    "nexttab": "ms:keyboard_tab",
    "prevtab": "ms:keyboard_tab_rtl",
    "copyimage": "ms:screenshot_monitor",
    "copytranslation": "ms:open_with",
    "fontup": "ms:text_increase",
    "fontdown": "ms:text_decrease",
    "selfind": "ms:frame_inspect",
    "nexterror": "ms:error",
    "bookmark": "ms:bookmark",
    "findprev": "ms:youtube_searched_for",
    "template": "ms:note_add",
    "calltip": "ms:info",
    "autocomplete": "ms:arrow_selector_tool",
    # --- design ---
    "reloadpreview": "ms:autorenew",
    "preview": "ms:preview",
    "render": "ms:deployed_code",
    "export": "ms:file_export",
    "print3d": "ms:precision_manufacturing",
    # --- view ---
    "previewmode": "ms:visibility",
    "thrown": "ms:layers",
    "edges": "ms:polyline",
    "axes": "ms:3d_rotation",
    "crosshairs": "ms:center_focus_strong",
    "diagonal": "ms:view_in_ar",
    "viewall": "ms:fit_screen",
    # --- window ---
    "jumpto": "ms:jump_to_element",
    "nextwin": "ms:select_window",
    "prevwin": "ms:select_window_2",
}

# name -> (text, strike through)
TEXT = {
    "comment": ("//", False),
    "uncomment": ("//", True),
    "top": ("TOP", False),
    "bottom": ("BTM", False),
    "left": ("LFT", False),
    "right": ("RGT", False),
    "front": ("FRT", False),
    "back": ("BCK", False),
    "center": ("CTR", False),
    "numup": ("+1", False),
    "numdown": ("−1", False),
}


def _draw_text(path: Path, text: str, strike: bool) -> None:
    """Black text on transparent, like the fetched glyphs, scaled so its ink
    fills the icon; `strike` adds a horizontal bar through the middle."""
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    probe = ImageFont.truetype(FONT, 100)
    box = d.textbbox((0, 0), text, font=probe)
    scale = min(RENDER_PX * 0.95 / (box[2] - box[0]), RENDER_PX * 0.9 / (box[3] - box[1]))
    font = ImageFont.truetype(FONT, max(8, int(100 * scale)))
    box = d.textbbox((0, 0), text, font=font)
    x = (RENDER_PX - (box[2] - box[0])) / 2 - box[0]
    y = (RENDER_PX - (box[3] - box[1])) / 2 - box[1]
    d.text((x, y), text, font=font, fill=(0, 0, 0, 255))
    if strike:
        mid = RENDER_PX // 2
        d.rectangle((2, mid - 5, RENDER_PX - 3, mid + 5), fill=(0, 0, 0, 255))
    img.save(path)


def _bookmark_arrow(base: Path, path: Path, down: bool) -> None:
    """The bookmark glyph at 70 % on the left and a solid triangle on the
    right, pointing down for next and up for previous."""
    img = Image.new("RGBA", (RENDER_PX, RENDER_PX), (0, 0, 0, 0))
    mark = Image.open(base).convert("RGBA").resize((68, 68), Image.LANCZOS)
    img.alpha_composite(mark, (0, 14))
    d = ImageDraw.Draw(img)
    x0, x1, xm = 62, 94, 78
    if down:
        d.polygon([(x0, 36), (x1, 36), (xm, 62)], fill=(0, 0, 0, 255))
    else:
        d.polygon([(x0, 62), (x1, 62), (xm, 36)], fill=(0, 0, 0, 255))
    img.save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    for name, (text, strike) in TEXT.items():
        _draw_text(out / f"{name}.png", text, strike)
        n += 1
    _bookmark_arrow(out / "bookmark.png", out / "nextbookmark.png", down=True)
    _bookmark_arrow(out / "bookmark.png", out / "prevbookmark.png", down=False)
    n += 2
    print(f"Wrote {n} icons to {out} ({len(TEXT)} drawn as text)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
