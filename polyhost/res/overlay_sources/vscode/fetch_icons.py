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

# Committed assets: the ESC program mark plus every icon inherited from the
# previously shipped overlay, lifted pixel-for-pixel so the Windows/Linux set
# keeps exactly the drawings it always had. None of these is fetchable — the old
# set had no source spec, and the mark's Simple Icons entry has been removed —
# so they are guarded here and must be restored from git if lost.
RECLAIMED = {
    "vscode.png", "gotoline.png", "newfile.png", "symbols.png", "runnodebug.png",
    "pause.png", "zoomout.png", "zoomin.png", "settings.png", "history.png",
    "stopdebug.png", "stepout.png", "run.png", "breakpoint.png", "stepover.png",
    "stepinto.png", "palette.png", "goforward.png", "matchbracket.png", "goback.png",
}

FLUENT = {
    # --- navigation / "go to" family ---
    "quickopen": "Document Search",
    "gotosymbol": "Text Bullet List Tree",
    "definition": "Target",
    "rename": "Rename",
    # --- search ---
    "findinfiles": "Folder Search",
    "replaceinfiles": "Arrow Swap",
    "selectall": "Select All On",
    # --- editing ---
    "comment": "Comment",
    # --- view / panels ---
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
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    # Never fetched, never clobbered — see RECLAIMED above.
    for name in sorted(RECLAIMED):
        f = out / name
        print(f"  {name}  <- committed asset (left as-is)" if f.exists()
              else f"  !! {name} MISSING — restore it from git, it is not fetchable")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
