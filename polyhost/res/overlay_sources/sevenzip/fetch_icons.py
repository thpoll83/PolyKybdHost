#!/usr/bin/env python3
"""Fetch + render the 7-Zip File Manager shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** via `icon_fetch`. The
ESC **program mark** is NOT baked here -- it comes from the curated generic
`mdi:folder-zip` (`polyhost/res/app_icons.yaml`).

Shortcuts come from 7-Zip's OWN manual (Menu Items and Shortcut Keys), so this
is the documented set rather than a third-party summary. See SOURCES.md.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/sevenzip/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

FLUENT = {
    # file operations
    "view":      "Eye",
    "edit":      "Text Edit Style",
    "rename":    "Rename",
    "copyto":    "Copy",
    "moveto":    "Arrow Forward",
    "newfolder": "Folder Add",
    "newfile":   "Document Add",
    "props":     "Info",
    "comment":   "Comment Note",
    "copyname":  "Clipboard Letter",
    # view
    "largeicons": "Grid",
    "smallicons": "Apps List",
    "listview":   "Text Bullet List Square",
    "details":    "Document Table",
    "twopanel":   "Split Vertical",
    "refresh":    "Arrow Sync",
    "parent":     "Folder Arrow Up",
    "root":       "Home",
    "history":    "History",
    # ⚠️ NOT the Eye: "open as folder" descends INTO the archive, which is a
    # different act from F3's read-only view and had been sharing its glyph.
    "openfolder": "Folder Zip",
    # sorting  (Ctrl+F3..F7)
    "sortname": "Text Sort Ascending",
    "sorttype": "Filter",
    "sortdate": "Calendar",
    "sortsize": "Data Bar Vertical",
    "unsorted": "Arrow Sort",
    # panels
    "switchpanel": "Arrow Swap",
    "otherpanel":  "Arrow Export Up",
    "addrleft":    "Panel Left",
    "addrright":   "Panel Right",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
