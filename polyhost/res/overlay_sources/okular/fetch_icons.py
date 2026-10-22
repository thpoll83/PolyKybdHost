#!/usr/bin/env python3
"""Fetch + render the Okular shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). ESC is left to the generic
program mark (the app's own icon).

    pip install cairosvg
    python polyhost/res/overlay_sources/okular/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

FLUENT = {
    # --- file ---
    "saveas": "Save Edit",
    "close": "Document Dismiss",
    "quit": "Power",
    "properties": "Info",
    "reload": "Arrow Clockwise",
    "preferences": "Settings",
    "help": "ms:help",
    # --- navigation ---
    "gotopage": "ms:move_down",
    "firstpage": "ms:first_page",
    "lastpage": "ms:last_page",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "findnext": "ms:manage_search",
    "findprev": "ms:search_off",
    "bookmark": "Bookmark Add",
    "nexttab": "ms:tab",
    "prevtab": "ms:tab_move",
    "reopentab": "ms:tab_recent",
    # --- view ---
    "sidebar": "Panel Left",
    "annottoolbar": "ms:draw",
    "presentation": "ms:co_present",
    "fullscreen": "Full Screen Maximize",
    "menubar": "ms:menu",
    "zoom100": "ms:1x_mobiledata",
    "fitwindow": "ms:fit_page_width",
    # --- mouse modes ---
    "browse": "Hand Right",
    "zoomtool": "ms:zoom_in_map",
    "areaselect": "ms:select",
    "textselect": "ms:text_select_start",
    "tableselect": "Table",
    "magnifier": "ms:loupe",
    # --- annotation tools ---
    "highlighter": "Highlight",
    "underline": "Text Underline",
    "squiggle": "ms:format_underlined_squiggle",
    "strikeout": "Text Strikethrough",
    "typewriter": "Text T",
    "inlinenote": "Note",
    "popupnote": "Comment",
    "freehand": "ms:gesture",
    "arrow": "ms:north_east",
    "rectangle": "Rectangle Landscape",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
