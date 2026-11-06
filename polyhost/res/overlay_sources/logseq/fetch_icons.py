#!/usr/bin/env python3
"""Fetch and render the Logseq shortcut icons (reproducible source step).

Shortcut icons: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0, `ms:` names) where Fluent has no match. The ESC program mark is
Logseq's own app icon (three ovals on a square tile) reduced to 1 bit at the
32x32 keycap size: the tile is lit and the ovals are cut out. A committed mark
is left as it is.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/logseq/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

# Logseq's app icon (logseq.com's favicon) through Google's favicon service.
LOGSEQ_ICON_URL = "https://www.google.com/s2/favicons?domain=logseq.com&sz=256"
LOGSEQ_DARK_LUMA = 128  # pixels at or below this are the dark tile


def _logseq_mark(dest: Path, px: int = 32) -> None:
    """Logseq's square app icon as a px*px 1-bit tile with the ovals cut out.

    Drawn at the keycap size so the generator copies it 1:1.
    """
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    import io
    import urllib.request
    with urllib.request.urlopen(LOGSEQ_ICON_URL, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    a = white.convert("L").resize((px, px), Image.LANCZOS).point(
        lambda v: 255 if v <= LOGSEQ_DARK_LUMA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(dest)
    print(f"  {dest.name}  <- Logseq app icon, 1-bit tile with the ovals cut out")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(ICONS, out)
    # Delete to line end: the backspace glyph turned to point right.
    Image.open(out / "killafter.png").transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(
        out / "killafter.png")
    print("  killafter.png  <- ms:backspace, mirrored")
    _logseq_mark(out / "logseq.png")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
