#!/usr/bin/env python3
"""Fetch + render the DaVinci Resolve shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** for everything generic,
plus the shared custom-drawn NLE glyphs (`../nle_glyphs.py`) for the timeline
operations no UI icon set has — blade, mark in/out, overwrite, append, ripple
delete, trim, snapping. The ESC **program mark** is a drawn, license-clean
substitute (`../program_marks.py`): Blackmagic's Resolve logo is a trademark we
may not redistribute.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/resolve/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import nle_glyphs  # noqa: E402
import program_marks  # noqa: E402

# action filename -> Fluent folder name (icon_fetch resolves the asset + size).
FLUENT = {
    # file / project
    "newtimeline": "Add Square",
    "save": "Save",
    "import": "Arrow Import",
    "render": "Arrow Export",
    "renderqueue": "List",
    # edit
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "selectall": "Select All On",
    "group": "Group",
    "ungroup": "Group Dismiss",
    "link": "Link",
    "addedit": "Split Vertical",
    # view / timeline
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "select": "Cursor",
    "marker": "Flag",
    "dyntrim": "Arrow Autofit Width",
    "insert": "Arrow Between Down",
    # transport
    "play": "Play",
    "stop": "Stop",
    "fwd": "Fast Forward",
    "rev": "Rewind",
    # the six pages (Shift+3..8)
    "pagecut": "Filmstrip",
    "pageedit": "Timeline",
    "pagefusion": "Branch",
    "pagecolor": "Color",
    "pagefairlight": "Music Note 2",
    "pagedeliver": "Cloud Arrow Up",
}

DRAWN = ["blade", "markin", "markout", "overwrite", "append", "rippledelete", "trim", "snap"]


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    n += nle_glyphs.draw_all(out, DRAWN)
    program_marks.ensure(out / "resolve.png", "R", motif="sprockets")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
