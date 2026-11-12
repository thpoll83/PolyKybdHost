#!/usr/bin/env python3
"""Fetch and render the Evernote shortcut icons (reproducible source step).

Shortcut icons: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0, `ms:` names) where Fluent has no match. `shortcut1..9.png` are the
Fluent star with the digit in it (`../number_badge.py`): Evernote's shortcuts
are its starred items, and Ctrl/Cmd+1..9 opens the Nth one. The ESC program
mark is Evernote's monochrome mark from Simple Icons (artwork CC0-1.0), through
`../brand_marks.py`. A committed mark is left as it is.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/evernote/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks  # noqa: E402
import icon_fetch  # noqa: E402
import number_badge  # noqa: E402

ICONS = {
    # --- general ---
    "newnote": "Note Add",
    "newnotebook": "Notebook Add",
    "newspace": "People Team Add",
    "newtask": "Task List Add",
    "newtag": "Tag",
    "newevent": "Calendar Add",
    "search": "Search",
    "scratchpad": "Note Edit",
    "trash": "Delete",
    "selectall": "Select All On",
    "closewindow": "Dismiss Square",
    "shortcuts": "Keyboard",
    "settings": "Settings",
    # --- navigation ---
    "switchto": "Directions",
    "home": "Home",
    "notes": "Note",
    "tasks": "Checkbox Checked",
    "files": "Attach",
    "calendar": "Calendar",
    "notebooks": "Notebook",
    "tags": "Tag Multiple",
    "shared": "People",
    "templates": "ms:dashboard_customize",
    "snippetview": "Text Bullet List Square",
    "cardview": "Grid",
    "toplist": "Split Horizontal",
    "sidelist": "Split Vertical",
    "listview": "Arrow Sync",
    "tagfilter": "Filter",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "focuslist": "Text Bullet List",
    "focusformat": "Text Font",
    "listprev": "Panel Left Contract",
    "listnext": "Panel Left Expand",
    # --- view ---
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "zoomreset": "Ratio One To One",
    "sidebar": "Panel Left",
    "fullscreen": "Full Screen Maximize",
    # --- note actions ---
    "newwindow": "Window New",
    "liteeditor": "Document Edit",
    "share": "Share",
    "move": "Folder Arrow Right",
    "addtag": "Tag Add",
    "edittags": "Tag Edit",
    "copylink": "Link",
    "internallink": "Document Link",
    "noteinfo": "Info",
    "print": "Print",
    "rename": "Rename",
    # --- editing ---
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "copy": "Copy",
    "cut": "Cut",
    "paste": "Clipboard Paste",
    "pastematch": "Clipboard Letter",
    "find": "Document Search",
    "replace": "ms:find_replace",
    "notelink": "Link Add",
    "divider": "Line Horizontal 1",
    "codeblock": "Code Block",
    "insertdate": "Calendar Today",
    "inserttime": "Clock",
    "comment": "Comment Add",
    # --- text formatting ---
    "fontup": "Font Increase",
    "fontdown": "Font Decrease",
    "bold": "Text Bold",
    "italic": "Text Italic",
    "underline": "Text Underline",
    "highlight": "Highlight",
    "bullets": "Text Bullet List",
    "numbered": "ms:format_list_numbered",
    "checklist": "ms:checklist",
    "alignleft": "Text Align Left",
    "aligncenter": "Text Align Center",
    "alignright": "Text Align Right",
    "justify": "Text Align Justify",
    "indent": "Text Indent Increase",
    "outdent": "Text Indent Decrease",
    "strike": "Text Strikethrough",
    "superscript": "Text Superscript",
    "subscript": "Text Subscript",
    "simplify": "Text Clear Formatting",
    "removeformat": "ms:format_clear",
    "encrypt": "Lock Closed",
    # --- AI Assistant ---
    "ai": "Sparkle",
    "aiexpand": "Arrow Maximize",
    "aichat": "Chat Add",
    # base glyph of the numbered set (not bound itself)
    "_shortcutbase": "Star",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(ICONS, out)
    n += number_badge.numbered(out / "_shortcutbase.png", "123456789", out, "shortcut",
                               size=0.36, centre=(0.50, 0.57))
    brand_marks.ensure(out / "evernote.png", "evernote")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
