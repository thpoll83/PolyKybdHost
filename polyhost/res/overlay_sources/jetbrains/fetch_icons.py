#!/usr/bin/env python3
"""Fetch + render the JetBrains IDE shortcut icons (reproducible source step).

This folder serves all FIVE JetBrains artwork sets — Windows, macOS, and Linux
as GNOME, KDE and every other desktop. `bindings.yaml` scopes each chord to the
platforms whose keymap binds it, so one spec generates every set from these same
icons. See SOURCES.md.

Two kinds of icon live in `icons/`:

* RECLAIMED — the 36 shortcut icons and the ESC program mark of the previously
  shipped overlay, lifted pixel-for-pixel out of the old PNGs (72x40 cells,
  white on transparent). The old set was hand-drawn in GIMP and has no other
  source, so these are committed assets: never fetched, never clobbered, and to
  be restored from git if lost.
* Fetched — Microsoft Fluent UI System Icons (MIT) by folder name, or Google
  Material Symbols (Apache-2.0) for an `ms:` name. Deterministic, so a re-run
  may overwrite them freely.

Run from the repo root with the project venv:

    .venv/bin/pip install cairosvg Pillow
    .venv/bin/python polyhost/res/overlay_sources/jetbrains/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RECLAIMED = {
    "jetbrains.png",
    "gotodeclaration.png", "find.png", "gotosuper.png", "stop.png", "selectin.png",
    "navbar.png", "rename.png", "smartstepinto.png", "stepout.png", "debug.png",
    "run.png", "stepinto.png", "stepover.png", "resume.png", "gototypedecl.png",
    "findinpath.png", "gotofile.png", "viewbreakpoints.png", "gotoimpl.png",
    "reformat.png", "settings.png", "synchronize.png", "gotorelated.png",
    "findusages.png", "fontsmaller.png", "fontlarger.png", "forcestepinto.png",
    "forcestepover.png", "choosedebug.png", "forward.png", "back.png",
    "copyreference.png", "selectalloccurrences.png", "gotosymbol.png",
    "pastesimple.png", "scratchfile.png",
}

FLUENT = {
    # --- tool windows (Alt+1..0 / Cmd+1..0, Alt+F12) ---
    "win_project": "Folder",
    "win_bookmarks": "Bookmark",
    "win_find": "Search",
    "win_run": "Window Play",
    "win_debug": "Bug",
    "win_problems": "Warning",
    "win_structure": "Text Bullet List Tree",
    "win_services": "Server",
    "win_git": "Branch",
    "win_commit": "ms:commit",
    "terminal": "Window Console",
    # --- navigation ---
    "gotoclass": "Cube",
    "recentfiles": "History",
    "recentlocations": "Location",
    "gotoline": "Number Symbol",
    "findaction": "Flash",
    "gototest": "Beaker",
    # --- search ---
    "replaceinpath": "Folder Swap",
    # --- editing ---
    "comment": "Comment",
    "blockcomment": "Comment Multiple",
    "duplicateline": "Row Triple",
    "deleteline": "Delete Lines",
    "extendselection": "Arrow Expand",
    "shrinkselection": "Arrow Minimize",
    "movedown": "ms:move_down",
    "moveup": "ms:move_up",
    "intentions": "Lightbulb",
    "completion": "Sparkle",
    "surroundwith": "Braces",
    "livetemplate": "ms:code_blocks",
    "generate": "Add Circle",
    "optimizeimports": "Broom",
    "quickdoc": "Info",
    "paraminfo": "Braces Variable",
    "typehierarchy": "Organization",
    "callhierarchy": "ms:account_tree",
    # --- refactoring ---
    "refactorthis": "Wrench",
    "extractmethod": "ms:function",
    "introducevariable": "ms:variable_add",
    "inline": "ms:compress",
    "safedelete": "Delete",
    # --- run / debug / build ---
    "togglebreakpoint": "Record",
    "evaluate": "Calculator",
    "runtocursor": "Arrow Step In Right",
    "executionpoint": "Target Arrow",
    "rerun": "Arrow Clockwise",
    "build": "Toolbox",
    # --- version control ---
    "push": "Arrow Upload",
    "update": "Arrow Download",
    # --- files / tabs / bookmarks ---
    "closetab": "Dismiss",
    "pastehistory": "Clipboard Multiple",
    "togglebookmark": "Bookmark Add",
    "showbookmarks": "Bookmark Multiple",
    "projectstructure": "Folder Open",
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
