#!/usr/bin/env python3
"""Fetch + render the Visual Studio Code shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** — the house style, and a
natural fit here since VS Code is a Microsoft product drawn in the same idiom.

This folder serves BOTH VS Code artwork sets. `bindings.yaml` uses the
`CMDCTRL` token, so ONE spec generates `vscode_template.*` (Ctrl) and
`vscode_mac_template.*` (Cmd) from these same icons — same app, same actions,
same artwork, only the chord differs. See SOURCES.md for the per-platform
sourcing and for the shortcuts deliberately left out.

The ESC **program mark** is a **committed asset**, not a download: it is the mark
already shipped in `vscode_template.mods.png`, lifted pixel-for-pixel so this
re-authoring does not change what users see. Simple Icons has *removed* its
`visualstudiocode` entry (404 on every branch, while e.g. `sublimetext` still
resolves), so re-fetching it is not an option and would be the wrong call anyway
— the ribbon is a Microsoft trademark. See SOURCES.md.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/vscode/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

FLUENT = {
    # --- navigation / "go to" family ---
    "quickopen": "Document Search",
    "symbols": "Code",
    "gotosymbol": "Text Bullet List Tree",
    "gotoline": "Number Symbol",
    "definition": "Target",
    "rename": "Rename",
    # --- search ---
    "findinfiles": "Folder Search",
    "replaceinfiles": "Arrow Swap",
    "selectall": "Select All On",
    # --- editing ---
    "comment": "Comment",
    "newfile": "Document Add",
    # --- view / panels ---
    "settings": "Settings",
    "sidebar": "Panel Left",
    "split": "Split Horizontal",
    "closeeditor": "Dismiss",
    "explorer": "Folder",
    "extensions": "Puzzle Piece",
    "debugview": "Bug",
    "problems": "Warning",
    "output": "Document Text",
    "terminal": "Window Console",
    "mdpreview": "Eye",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    # --- debug ---
    "run": "Play",
    "runnodebug": "Play Circle",
    "stopdebug": "Stop",
    "breakpoint": "Record",
    "stepover": "Arrow Step Over",
    "stepinto": "Arrow Step In",
    "stepout": "Arrow Step Out",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    # The program mark is committed, never fetched — see the module docstring.
    # Three committed assets: the program mark plus two glyphs reclaimed
    # pixel-for-pixel from the previously shipped artwork, where the old drawing
    # said the thing better than any stock glyph did (a palette *window*; an
    # arrow *into* braces). Never fetched, never clobbered.
    for name in ("vscode.png", "palette.png", "matchbracket.png"):
        f = out / name
        print(f"  {name}  <- committed asset (left as-is)" if f.exists()
              else f"  !! {name} MISSING — restore it from git, it is not fetchable")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
