#!/usr/bin/env python3
"""Fetch and render the Joplin shortcut icons (reproducible source step).

Shortcut icons: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0, `ms:` names) where Fluent has no match. `profile1..3.png` are the
Fluent person glyph with a digit drawn beside it (`profiles()`). The ESC
program mark is Joplin's monochrome mark from Simple Icons (artwork CC0-1.0),
through `../brand_marks.py`. A committed mark is left as it is.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/joplin/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks  # noqa: E402
import icon_fetch  # noqa: E402

ICONS = {
    # --- notes and windows ---
    "newnote": "Document Add",
    "newtodo": "Task List Add",
    "sync": "Arrow Sync",
    "newwindow": "Window New",
    "deletenote": "Delete Dismiss",
    "settags": "Tag",
    "linktonote": "Document Link",
    "externaledit": "Open",
    "closewindow": "Dismiss Square",
    "quit": "Power",
    "settings": "Settings",
    "help": "Question Circle",
    # --- search and focus ---
    "gotoanything": "Directions",
    "commandpalette": "Apps List Detail",
    "searchall": "Search",
    "searchnote": "Document Search",
    "focussidebar": "Panel Left",
    "focusnotelist": "Text Bullet List Square",
    "focustitle": "Text Header 1",
    "focusbody": "Document Text",
    "focustoolbar": "ms:toolbar",
    # --- view ---
    "togglesidebar": "Panel Left Contract",
    "togglenotelist": "ms:view_sidebar",
    "layout": "Split Vertical",
    "toggleeditors": "Arrow Swap",
    "editorplugin": "Puzzle Piece",
    "aichat": "Sparkle",
    "menubar": "Navigation",
    "zoomreset": "Ratio One To One",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "fullscreen": "Full Screen Maximize",
    "tabfocus": "Keyboard Tab",
    # --- edit ---
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "pasteastext": "Clipboard Letter",
    "pasteasmd": "Markdown",
    "selectall": "Select All On",
    "datetime": "Calendar Clock",
    # --- format ---
    "bold": "Text Bold",
    "italic": "Text Italic",
    "link": "Link",
    "code": "Code",
    "bulletlist": "Text Bullet List",
    # --- Markdown editor ---
    "deleteline": "Delete Lines",
    "duplicateline": "Row Triple",
    "indentless": "Text Indent Decrease",
    "indentmore": "Text Indent Increase",
    "togglecomment": "Comment",
    "sortlines": "Text Sort Ascending",
    "lineup": "Arrow Up",
    "linedown": "Arrow Down",
    # base glyph of the numbered set (not bound itself)
    "_profilebase": "Person",
}


BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def profiles(base: Path, out: Path) -> int:
    """`profile1..3.png`: the Fluent person glyph with the digit to its right.

    The person outline has no empty area for a digit, so the canvas is widened
    to 3:2 and the digit is drawn in the right third. The digit is dark on
    transparent, like the Fluent linework, so the spec's `luma` mode lights both.
    """
    person = Image.open(base).convert("RGBA")
    w, h = person.size
    font = ImageFont.truetype(BOLD, int(h * 0.62))
    for d in "123":
        img = Image.new("RGBA", (w * 3 // 2, h), (0, 0, 0, 0))
        img.paste(person, (0, 0), person)
        ImageDraw.Draw(img).text((w * 1.22, h * 0.56), d, fill=(0, 0, 0, 255),
                                 font=font, anchor="mm")
        img.save(out / f"profile{d}.png")
    print("  profile1..profile3.png  <- composite (_profilebase + digit beside it)")
    return 3


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(ICONS, out)
    n += profiles(out / "_profilebase.png", out)
    brand_marks.ensure(out / "joplin.png", "joplin")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
