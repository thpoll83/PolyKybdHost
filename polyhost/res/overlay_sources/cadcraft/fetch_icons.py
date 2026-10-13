#!/usr/bin/env python3
"""Fetch + render the CADCraft shortcut icons (reproducible).

CADCraft (github.com/storytold/cadcraft) is an open-source, MIT OR Apache-2.0
AutoCAD-style drafting app. Its own UI icons are drawn in code
(crates/ui-egui/src/icons.rs), not shipped as files, so the glyphs here are:

* Microsoft Fluent UI System Icons (MIT) -- the house style;
* Material Symbols (Apache-2.0, `ms:`) where Fluent has no match;
* byte-identical copies of sibling apps' committed icons for the same action
  (`icon_fetch.borrow`), so the overlay library stores them once;
* the program mark (ESC): CADCraft's OWN app icon, MIT OR Apache-2.0 per the
  repo's ATTRIBUTION.md, taken from the 64 px frame of assets/app-icon/cadcraft.ico.

Borrowed icons and the program mark are guarded: a committed file is left as-is.

    PYTHONPATH=. python polyhost/res/overlay_sources/cadcraft/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, program_marks  # noqa: E402

# Pinned to the commit the shortcuts were read from (see SOURCES.md).
CADCRAFT_SHA = "e707ab4d7cc10102e550ad4c5bcecef1084a9baa"
APP_ICON = (f"https://raw.githubusercontent.com/storytold/cadcraft/{CADCRAFT_SHA}"
            "/assets/app-icon/cadcraft.ico")

FLUENT = {
    "commandref": "Book Question Mark",   # F1 Command Reference
    "history": "History",                 # F2 Command History
    "osnap": "Target",                    # F3 Object Snap
    "isoplane": "ms:deployed_code",       # F5 / Ctrl+E Isometric plane (isometric cube)
    "grid": "Grid Dots",                  # F7 Grid display
    "ortho": "Arrow Move",                # F8 Ortho (horizontal/vertical only)
    "polar": "ms:radar",                  # F10 Polar tracking
    "otrack": "Target Arrow",             # F11 Object snap tracking
    "dynmode": "Cursor Hover",            # F12 Dynamic input (box at the cursor)
    "properties": "Panel Right",          # Ctrl+1 Properties Inspector
    "toolsets": "Toolbox",                # Ctrl+3 Tool Sets
    "cmdline": "Window Console",          # Ctrl+9 Command Line
    "pickstyle": "Group",                 # Ctrl+Shift+A Group selection
    "copybase": "Copy Select",            # Ctrl+Shift+C Copy with base point
    "pasteblock": "ms:content_paste_go",  # Ctrl+Shift+V Paste as block
    "quickcalc": "Calculator",            # Cmd+8 QuickCalc (macOS)
    "repeatcmd": "Arrow Enter Left",      # Enter / Space: enter, or repeat last command
    "snapcycle": "Arrow Sync",            # Tab: cycle snaps / complete command
}

# Same action, same glyph as a sibling app (byte-identical copies).
BORROW = {
    "new.png": "illustrator",
    "open.png": "illustrator",
    "save.png": "illustrator",
    "saveas.png": "illustrator",
    "print.png": "illustrator",
    "undo.png": "illustrator",
    "copy.png": "illustrator",
    "cut.png": "illustrator",
    "paste.png": "illustrator",
    "selectall.png": "illustrator",
    "prefs.png": "illustrator",
    "snap.png": "resolve",      # drawn horseshoe magnet (nle_glyphs.snap), mode: alpha
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    program_marks.own_icon(out / "cadcraft.png", APP_ICON, frame=64,
                           credit="storytold/cadcraft assets/app-icon/cadcraft.ico (MIT OR Apache-2.0)")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
