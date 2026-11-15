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

import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dcc_glyphs as g  # noqa: E402
import icon_fetch  # noqa: E402

RECLAIMED = {
    "jetbrains.png",
    "gotodeclaration.png", "find.png", "gotosuper.png", "stop.png", "selectin.png",
    "navbar.png", "rename.png", "smartstepinto.png", "stepout.png", "debug.png",
    "run.png", "stepinto.png", "stepover.png", "resume.png", "gototypedecl.png",
    "findinpath.png", "gotofile.png", "viewbreakpoints.png", "gotoimpl.png",
    "breakpoint.png",  # VS Code's breakpoint, shared pixel-for-pixel
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
    # --- mode sets (bindings_debug/project/terminal.yaml, gen_mode_specs.py) ---
    "quickevaluate": "Eye",
    "forceruntocursor": "Fast Forward",
    "tempbreakpoint": "Timer",
    "copyfile": "Document Copy",
    "movefile": "Folder Arrow Right",
    "deletefile": "ms:delete_forever",
    "editsource": "Document Edit",
    "opensplit": "Split Vertical",
    "compare": "ms:compare",
    "collapseall": "Arrow Collapse All",
    "expandall": "Arrow Expand All",
    "copypath": "Clipboard Link",
    "revealin": "Open",
    "hidewindow": "Eye Off",
    "newtab": "Tab Add",
    "nexttab": "Arrow Next",
    "prevtab": "Arrow Previous",
    "clearbuffer": "Eraser",
    "pageup": "Chevron Double Up",
    "pagedown": "Chevron Double Down",
    "interrupt": "Prohibited",
    "closesession": "Plug Disconnected",
    "historysearch": "ms:manage_search",
    "deleteword": "Backspace",
    # --- tool window sets (gen_mode_specs.py TOOL_WINDOWS), fetched 2026-11-14 ---
    "commitpush": "Cloud Arrow Up",
    "amend": "Edit Arrow Back",
    "messagehistory": "Chat History",
    "commitoptions": "Options",
    "rollback": "Arrow Reset",
    "activechangelist": "Star",
    "addtovcs": "Add Square",
    "shelve": "Archive",
    "unshelve": "Archive Arrow Back",
    "vcspopup": "Apps List",
    "branches": "Branch Compare",
    "newbranch": "Branch Fork",
    "affectedfiles": "Document Multiple",
    "filter": "Filter",
    "refresh": "Arrow Sync",
    "nextoccurrence": "Arrow Circle Down",
    "prevoccurrence": "Arrow Circle Up",
    "editconfig": "Edit Settings",
    "groupbytype": "Group List",
    "groupbydirectory": "Folder List",
    "exclude": "Subtract Circle",
    "include": "Checkmark Circle",
    "readaccess": "Book Open",
    "writeaccess": "Pen",
    "imports": "Arrow Import",
    "export": "Document Arrow Down",
    "mnemonic": "Tag",
    "deletebookmark": "Bookmark Off",
    # --- one icon per action (2026-11-15) ---
    "filestructure": "Document Bullet List",
    "newelement": "Add",
    "changelistmove": "ms:move_group",
    # parts of the composites below, not drawn on their own
    "part_check": "Checkmark",
    "part_checkbox": "Checkbox Checked",
    "part_list": "List",
    "part_lines": "Text Align Left",
    "part_settings": "Settings",
}

# Composites: (output, base, badge). The base is reduced to the upper left and
# the badge drawn at the lower right (dcc_glyphs.with_badge). A base named
# "cell:<file>" is a RECLAIMED white 72x40 cell, turned into dark ink first.
BADGES = [
    ("commit.png", "win_commit.png", "part_check.png"),          # Commit (not the window)
    ("viewbreakpoints_list.png", "cell:breakpoint.png", "part_list.png"),
    ("run_selected.png", "cell:run.png", "part_checkbox.png"),   # Services: Run selected
    ("debug_selected.png", "cell:debug.png", "part_checkbox.png"),
    ("copyconfig.png", "copyfile.png", "part_settings.png"),     # Services: Copy configuration
]

# Composites: (output, base, up). The base on the right, a heavy arrow on the left.
VERTICAL = [
    ("moveline_up.png", "part_lines.png", True),
    ("moveline_down.png", "part_lines.png", False),
    ("movestatement_up.png", "surroundwith.png", True),
    ("movestatement_down.png", "surroundwith.png", False),
]


def _cell_ink(src: Path, dst: Path) -> None:
    """A reclaimed white-on-transparent cell as black ink on transparent,
    cropped to its ink and centred in a square, so dcc_glyphs can compose it."""
    a = np.asarray(Image.open(src).convert("RGBA"))[..., 3]
    ys, xs = np.nonzero(a)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    s = max(a.shape)
    sq = np.zeros((s, s), np.uint8)
    y0, x0 = (s - a.shape[0]) // 2, (s - a.shape[1]) // 2
    sq[y0:y0 + a.shape[0], x0:x0 + a.shape[1]] = a
    rgba = np.zeros((s, s, 4), np.uint8)
    rgba[..., 3] = sq
    Image.fromarray(rgba, "RGBA").save(dst)


def composites(out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        for name, base, badge in BADGES:
            if base.startswith("cell:"):
                src = Path(tmp) / base[5:]
                _cell_ink(out / base[5:], src)
            else:
                src = out / base
            g.guarded(out / name, lambda p, b=src, s=out / badge: g.with_badge(b, s, p),
                      f"composite ({base} + {badge})")
    for name, base, up in VERTICAL:
        g.guarded(out / name, lambda p, b=out / base, u=up: g.with_vertical_arrow(b, p, u),
                  f"composite ({base} + {'up' if up else 'down'} arrow)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    composites(out)
    # Never fetched, never clobbered — see RECLAIMED above.
    for name in sorted(RECLAIMED):
        f = out / name
        print(f"  {name}  <- committed asset (left as-is)" if f.exists()
              else f"  !! {name} MISSING — restore it from git, it is not fetchable")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
