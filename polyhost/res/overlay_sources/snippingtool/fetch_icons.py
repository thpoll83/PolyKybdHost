#!/usr/bin/env python3
"""Fetch + render the Snipping Tool shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** via `icon_fetch`. The
ESC **program mark** is NOT baked here -- it comes from the curated generic
`mdi:scissors-cutting` (`polyhost/res/app_icons.yaml`), which beats an "S" tile.

⚠️ This is a SMALL overlay by nature: the shortcut everyone knows,
`Win+Shift+S`, is a GUI/Win-key combination and the overlay format has no
channel for it, so it cannot be drawn at all. What is here is the set that works
INSIDE the app window once it is open. See SOURCES.md.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/snippingtool/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

FLUENT = {
    "newsnip":   "Cut",                 # scissors -- the app's own metaphor
    "save":      "Save",
    "copy":      "Copy",
    "print":     "Print",
    "undo":      "Arrow Undo",
    "redo":      "Arrow Redo",
    "selectall": "Select All On",
    "mode":      "Crop Interim",        # the mode picker: rect / freeform / window / full
    "samemode":  "Arrow Sync Circle",   # new snip, same mode as last
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
