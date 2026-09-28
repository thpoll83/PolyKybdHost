#!/usr/bin/env python3
"""Fetch + render the Visual Studio shortcut icons (reproducible source step).

Two kinds of icon live in `icons/`:

* RECLAIMED — the 11 debug/build icons and the ESC program mark of the
  previously shipped overlay, lifted pixel-for-pixel out of the old PNGs (72x40
  cells, white on transparent). The old set was hand-drawn and has no other
  source, so these are committed assets: never fetched, never clobbered, and to
  be restored from git if lost.
* Fetched — Microsoft Fluent UI System Icons (MIT) by folder name, or Google
  Material Symbols (Apache-2.0) for an `ms:` name. Deterministic, so a re-run
  may overwrite them freely.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/visualstudio/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RECLAIMED = {
    "visualstudio.png",
    "startdebug.png", "startnodebug.png", "togglebreakpoint.png",
    "stepover.png", "stepinto.png", "stepout.png", "compile.png",
    "buildsolution.png", "stepovercurrentprocess.png",
    "stepintocurrentprocess.png", "stepoutcurrentprocess.png",
}

FLUENT = {
    # --- debug ---
    "stopdebug": "Stop",
    "restart": "Arrow Clockwise",
    "runtocursor": "Arrow Step In Right",
    "setnextstatement": "Target Arrow",
    "deleteallbreakpoints": "Dismiss Circle",
    "quickwatch": "Glasses",
    "breakpoints": "Record",
    "attach": "Plug Connected",
    "hotreload": "Fire",
    # --- navigation ---
    "gotodefinition": "ms:jump_to_element",
    "gotodeclaration": "ms:data_object",
    "peekdefinition": "Eye",
    "findallreferences": "ms:manage_search",
    "gotoall": "ms:frame_inspect",
    "featuresearch": "Search Sparkle",
    "navback": "Arrow Left",
    "navforward": "Arrow Right",
    # --- search ---
    "findinfiles": "Folder Search",
    "replaceinfiles": "Folder Swap",
    # --- editing ---
    "quickactions": "Lightbulb",
    "duplicate": "Row Triple",
    "movelineup": "ms:move_up",
    "movelinedown": "ms:move_down",
    "lineopenabove": "ms:add_row_above",
    "lineopenbelow": "ms:add_row_below",
    "deleteline": "Delete Lines",
    "clipboardring": "Clipboard Multiple",
    # --- files / windows ---
    "newproject": "Folder Add",
    "saveall": "Save Multiple",
    "addnewitem": "ms:library_add",
    "nextdocument": "Tabs",
    "solutionexplorer": "ms:account_tree",
    "output": "Window Text",
    "properties": "Wrench",
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
