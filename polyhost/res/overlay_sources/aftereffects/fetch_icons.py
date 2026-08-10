#!/usr/bin/env python3
"""Fetch + render the Adobe After Effects shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** throughout — unlike the
two NLE sets, After Effects' shortcuts are layer *properties* and tools that map
cleanly onto generic UI glyphs (anchor/position/scale/rotation/opacity/effects),
so nothing needed custom drawing. The ESC **program mark** is a drawn,
license-clean substitute (`../program_marks.py`).

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/aftereffects/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import rect_mark  # noqa: E402
import program_marks  # noqa: E402

FLUENT = {
    # layer properties (the single-letter row -- After Effects' signature)
    "anchorpoint": "Target",
    "position": "Arrow Move",
    "scale": "Resize",
    "rotation": "Arrow Rotate Clockwise",
    "opacity": "Circle Half Fill",
    "feather": "Blur",
    "effects": "Wand",
    "keyframes": "Diamond",
    # tools
    "select": "Cursor",
    "hand": "Hand Right",
    "zoom": "Zoom In",
    "pen": "Pen",
    "shape": "Shapes",
    "panbehind": "Drag",
    "type": "Text T",
    # file / project
    "newcomp": "Add Square",
    "open": "Folder Open",
    "save": "Save",
    "import": "Arrow Import",
    "renderqueue": "List",
    "compsettings": "Settings",
    "solid": "Square",
    # edit
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "selectall": "Select All On",
    "duplicate": "Square Multiple",
    "splitlayer": "Split Vertical",
    "precompose": "Layer",
    # timeline
    "gotoin": "Arrow Import",
    "gotoout": "Arrow Export",
    "preview": "Play",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    rect_mark.ensure(out / "aftereffects.png", "Ae")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
