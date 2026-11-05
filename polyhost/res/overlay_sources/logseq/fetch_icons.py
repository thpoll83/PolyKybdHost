#!/usr/bin/env python3
"""Fetch and render the Logseq shortcut icons (reproducible source step).

Shortcut icons: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0, `ms:` names) where Fluent has no match. The ESC program mark is
Logseq's monochrome mark from Simple Icons (artwork CC0-1.0), through
`../brand_marks.py`. A committed mark is left as it is.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/logseq/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks  # noqa: E402
import icon_fetch  # noqa: E402

ICONS = {
    # --- while editing a block ---
    "followlink": "Open",
    "linksidebar": "Panel Right",
    "bold": "Text Bold",
    "italic": "Text Italic",
    "highlight": "Highlight",
    "strike": "Text Strikethrough",
    "clearblock": "Text Clear Formatting",
    "killbefore": "ms:backspace",
    "killafter": "ms:backspace",  # mirrored in main(): deletes to the right
    "blockstart": "ms:text_select_jump_to_beginning",
    "blockend": "ms:text_select_jump_to_end",
    "wordnext": "ms:text_select_move_forward_word",
    "wordprev": "ms:text_select_move_back_word",
    "killwordnext": "ms:keyboard_tab",
    "killwordprev": "ms:keyboard_tab_rtl",
    "copyembed": "Code Block",
    "pasteoneblock": "Clipboard Paste",
    "ytstamp": "Video Clip",
    "comment": "Comment Add",
    "zoomblock": "Arrow Maximize",
    "unzoomblock": "Arrow Minimize",
    # --- blocks ---
    "cycletodo": "Checkbox Checked",
    "moveup": "Arrow Up",
    "movedown": "Arrow Down",
    "moveblocks": "Arrow Move",
    "selectup": "Arrow Circle Up",
    "selectdown": "Arrow Circle Down",
    "expand": "Chevron Down",
    "collapse": "Chevron Up",
    "togglechildren": "Text Bullet List Tree",
    "selectparent": "ms:account_tree",
    "selectall": "Select All On",
    "copy": "Copy",
    "copytext": "Clipboard Letter",
    "cut": "Cut",
    "paste": "Clipboard Paste",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "insertlink": "Link",
    "addproperty": "Tag",
    "quickadd": "Add Circle",
    "favorite": "Star",
    "jump": "ms:jump_to_element",
    # --- search and navigation ---
    "search": "Search",
    "searchpage": "Document Search",
    "find": "ms:find_in_page",
    "findnext": "ms:keyboard_double_arrow_down",
    "findprev": "ms:keyboard_double_arrow_up",
    "commandpalette": "Apps List Detail",
    "searchthemes": "Color",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "today": "Calendar Today",
    "contents": "Text Bullet List Square",
    "opengraph": "Folder Open",
    "save": "Save",
    "shell": "Window Console",
    "closewindow": "Dismiss Square",
    # --- key sequences ---
    "goto": "Directions",
    "toggle": "Toggle Left",
    "property": "Tag Multiple",
    "help": "Keyboard",
    # --- Electron menu ---
    "newwindow": "Window New",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "zoomreset": "Ratio One To One",
    "fullscreen": "Full Screen Maximize",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(ICONS, out)
    # Delete to line end: the backspace glyph turned to point right.
    Image.open(out / "killafter.png").transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(
        out / "killafter.png")
    print("  killafter.png  <- ms:backspace, mirrored")
    brand_marks.ensure(out / "logseq.png", "logseq")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
