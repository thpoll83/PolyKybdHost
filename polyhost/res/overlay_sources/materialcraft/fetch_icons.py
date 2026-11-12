#!/usr/bin/env python3
"""Fetch + render the MaterialCraft shortcut icons (reproducible source step).

MaterialCraft (github.com/storytold/materialcraft, MIT OR Apache-2.0) is the
ArtCraft suite's open-source node-based procedural material editor, a Substance
3D Designer work-alike. Its keymap is the app's OWN (the menu catalog in
`crates/ui-egui/src/menus.rs`, the engine command registry and the graph
canvas keys); SOURCES.md lists every chord with file:line.

Style: Microsoft Fluent UI System Icons (MIT) via `icon_fetch`, the house
style, with Material Symbols (Apache-2.0, `ms:`) for the gaps. The node-search
glyph is the Nuke/Houdini overlays' (same action: add a node from a searchable
menu), the frame glyph the Substance 3D Painter overlay's; both are copied
byte-identically with `icon_fetch.borrow`.

The ESC program mark is MaterialCraft's OWN icon (the engraved rhino,
`assets/app-icon/materialcraft.ico`, MIT OR Apache-2.0, 128 px frame), guarded
so a re-run never clobbers a committed `materialcraft.png`.

    PYTHONPATH=. python polyhost/res/overlay_sources/materialcraft/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import program_marks  # noqa: E402

# Pinned to the commit the shortcut table was read from (SOURCES.md).
MATERIALCRAFT_SHA = "b73facdc7b8b5ce102cd9e14d964058a15182dc0"
MATERIALCRAFT_ICO = ("https://raw.githubusercontent.com/storytold/materialcraft/"
                     f"{MATERIALCRAFT_SHA}/assets/app-icon/materialcraft.ico")

BORROWED = {"nodesearch.png": "nuke", "frame_all.png": "substancepainter"}

FLUENT = {
    # file
    "newgraph": "Flowchart",
    "open": "Folder Open",
    "save": "Save",
    "saveas": "Save Edit",
    "export": "Arrow Export",
    "quit": "Sign Out",
    # edit
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "copy": "Copy",
    "cut": "Cut",
    "paste": "Clipboard Paste",
    "pastenolinks": "ms:content_paste_off",
    "duplicate": "Copy Add",
    "dupnolinks": "ms:control_point_duplicate",
    "delete": "Delete",
    "deleterelink": "ms:call_merge",
    "selectall": "Select All On",
    "editgraph": "ms:account_tree",
    "parentgraph": "ms:arrow_back",
    # graph tools
    "disable": "Prohibited",
    "nextpin": "ms:switch_right",
    "prevpin": "ms:switch_left",
    "clearthumbs": "ms:hide_image",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROWED, out)
    program_marks.own_icon(out / "materialcraft.png", MATERIALCRAFT_ICO, 128,
                           credit="storytold/materialcraft assets/app-icon/materialcraft.ico (MIT OR Apache-2.0)")
    # The ESC mark: the icon's animal as one solid shape at keycap size, with its
    # darkest lines cut back out (program_marks.silhouette_mark).
    program_marks.silhouette_mark(out / "materialcraft_mark.png", out / "materialcraft.png", cut=95, crop=(40, 0, 128, 112))
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
