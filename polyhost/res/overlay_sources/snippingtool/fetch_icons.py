#!/usr/bin/env python3
"""Fetch + render the Snipping Tool shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** via `icon_fetch`. The
ESC **program mark** is the shared license-clean letter tile
(`../program_marks.py`) -- Snipping Tool's own icon is Microsoft trademark art.

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
import program_marks  # noqa: E402

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
    program_marks.ensure(out / "snippingtool.png", "S", motif="screen")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
