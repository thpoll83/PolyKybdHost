#!/usr/bin/env python3
"""Fetch + render the Obsidian shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)**. The ESC **program
mark** is a drawn, license-clean substitute (`../geo_marks.py`) — the Obsidian
gem logo is a trademark we may not redistribute, so the cell carries a generic
irregular faceted stone instead.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/obsidian/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import geo_marks  # noqa: E402
import icon_fetch  # noqa: E402

FLUENT = {
    "newnote": "Document Add",
    "quickswitcher": "Directions",
    "commandpalette": "Apps List Detail",
    "graph": "Branch Fork",
    "editpreview": "Eye",
    "find": "Search",
    "findreplace": "Arrow Swap",
    "searchall": "Document Search",
    "bold": "Text Bold",
    "italic": "Text Italic",
    "link": "Link",
    "strikethrough": "Text Strikethrough",
    "pasteplain": "Clipboard Paste",
    "closetab": "Dismiss",
    "settings": "Settings",
    "leftsidebar": "Panel Left",
    "rightsidebar": "Panel Right",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    # Per-view sets (gen_obsidian_modes.py): canvas and graph view keys.
    "zoomfit": "Zoom Fit",
    "zoomselection": "Select Object",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "removecard": "Delete",
    # Graph view: the arrow keys move the graph (a chevron), Shift moves it
    # faster (a double chevron). The arrows of back/forward stay with
    # Navigate back/forward, a different action.
    "panleft": "ms:keyboard_arrow_left",
    "panright": "ms:keyboard_arrow_right",
    "panup": "ms:keyboard_arrow_up",
    "pandown": "ms:keyboard_arrow_down",
    "fastleft": "ms:keyboard_double_arrow_left",
    "fastright": "ms:keyboard_double_arrow_right",
    "fastup": "ms:keyboard_double_arrow_up",
    "fastdown": "ms:keyboard_double_arrow_down",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    geo_marks.ensure_obsidian(out / "obsidian.png")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
