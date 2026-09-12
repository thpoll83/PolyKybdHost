#!/usr/bin/env python3
"""Fetch + render the Task Manager shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** via `icon_fetch`. The
ESC **program mark** is NOT baked here -- it comes from the curated generic
`mdi:monitor-dashboard` (`polyhost/res/app_icons.yaml`), which beats a "T" tile.

⚠️ This is the THINNEST overlay in the set, and that is the app, not a gap in
the research: Windows 11 Task Manager has five documented in-app shortcuts. The
famous `Ctrl+Shift+Esc` OPENS it and does nothing once you are in it, so it is
not drawn. See SOURCES.md.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/taskmgr/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

FLUENT = {
    "endtask":    "Dismiss Square",
    "newtask":    "Add Square",
    "efficiency": "Leaf One",       # efficiency mode = throttle a process
    "nextpage":   "Arrow Right",
    "prevpage":   "Arrow Left",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
