#!/usr/bin/env python3
"""Fetch + render the Adobe Premiere Pro shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** plus the shared
custom-drawn NLE glyphs (`../nle_glyphs.py`) — including four drawn specifically
for Premiere's tool row (ripple / rolling / slip / slide), whose whole point is
*which* clip edge moves and by how much. No generic icon set expresses that.
The ESC **program mark** is a drawn, license-clean substitute
(`../program_marks.py`): Adobe's Pr logo is a trademark we may not redistribute.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/premiere/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import rect_mark  # noqa: E402
import nle_glyphs  # noqa: E402
import program_marks  # noqa: E402

FLUENT = {
    # tools
    "select": "Cursor",
    "ratestretch": "Top Speed",
    "pen": "Pen",
    "hand": "Hand Right",
    "zoom": "Zoom In",
    # file / project
    "newproject": "Document Add",
    "newsequence": "Add Square",
    "open": "Folder Open",
    "save": "Save",
    "saveas": "Save Multiple",
    "import": "Arrow Import",
    "export": "Arrow Export",
    # edit
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "pasteinsert": "Arrow Between Down",
    "selectall": "Select All On",
    "group": "Group",
    "ungroup": "Group Dismiss",
    "link": "Link",
    "addedit": "Split Vertical",
    "speed": "Arrow Autofit Width",
    # view / transport
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "zoomfit": "Arrow Expand",
    "play": "Play",
    "stop": "Stop",
    "fwd": "Fast Forward",
    "rev": "Rewind",
    # panels (Shift+1..7)
    "panelproject": "Folder Open",
    "panelsource": "Video Clip",
    "paneltimeline": "Timeline",
    "panelprogram": "Play Circle",
    "paneleffectctl": "Options",
    "panelaudio": "Music Note 2",
    "paneleffects": "Wand",
}

DRAWN = ["blade", "markin", "markout", "rippledelete",
         "rippleedit", "rolledit", "slip", "slide", "trackselect"]


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    n += nle_glyphs.draw_all(out, DRAWN)
    # One size across the whole family (see rect_mark.shared_size).
    rect_mark.ensure(out / "premiere.png", "Pr",
                     size=rect_mark.shared_size(["Ps", "Ai", "Pr", "Ae"]))
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
