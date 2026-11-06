#!/usr/bin/env python3
"""Fetch + render the Foundry Nuke shortcut icons (reproducible source step).

Glyphs are Google Material Symbols (Apache-2.0, ``ms:`` names) and Microsoft
Fluent UI System Icons (MIT), rendered through ``../icon_fetch.py``. Glyphs that
mean the same as in a sibling set are copied byte-identical from it
(``BORROW``).

The ESC mark is the Nuke logo from Simple Icons (``nuke``, artwork CC0-1.0)
reduced to a 32x32 1-bit trace. See SOURCES.md.

    pip install cairosvg Pillow numpy
    PYTHONPATH=. python polyhost/res/overlay_sources/nuke/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import dcc_glyphs as g  # noqa: E402
from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

ICONS = {
    # --- global
    "clearcache": "ms:clear_all",
    "fullscreen": "Full Screen Maximize",
    "new": "Document Add",
    "open": "Folder Open",
    "save": "Save",
    "saveas": "ms:save_as",
    "close": "Dismiss",
    "quit": "Power",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "copy": "Copy",
    "cut": "Cut",
    "paste": "Clipboard Paste",
    "selectall": "Select All On",
    "tab_cycle": "ms:tab",
    "tab_next": "ms:keyboard_tab",
    "tab_prev": "ms:keyboard_tab_rtl",
    "delete": "Delete",
    # --- node graph: insert a node
    "dot": "ms:fiber_manual_record",
    "blur": "ms:blur_on",
    "colorcorrect": "ms:tune",
    "grade": "ms:exposure",
    "copynode": "ms:input",
    "roto": "ms:shape_line",
    "rotopaint": "ms:brush",
    "read": "ms:file_open",
    "write": "ms:file_export",
    "addmix": "ms:join_full",
    # --- node graph: navigate and edit
    "zoomout": "Zoom Out",
    "snapall": "ms:grid_on",
    "snapsel": "ms:grid_guides",
    "info": "ms:info",
    "jumpbookmark": "ms:bookmark",
    "bookmark": "ms:bookmark_add",
    "autoplace": "ms:dashboard",
    "scriptinfo_named": "ms:label",
    "scriptinfo": "ms:analytics",
    "properties": "ms:list_alt",
    "projectsettings": "ms:settings",
    "nodesearch": "ms:manage_search",
    "command": "ms:terminal",
    "versiondown": "ms:arrow_circle_down",
    "versionup": "ms:arrow_circle_up",
    "versionlatest": "ms:keyboard_double_arrow_up",
    "hideinputs": "ms:visibility_off",
    "stickynote": "ms:sticky_note_2",
    "runscript": "ms:code",
    "buffer": "ms:memory",
    "disconnect": "ms:link_off",
    "downstream": "ms:move_down",
    "upstream": "ms:move_up",
    "livegroup": "ms:folder_special",
    "proxy": "ms:photo_size_select_small",
    "pasteknobs": "ms:content_paste_go",
    "searchreplace": "ms:find_replace",
    "nodecolor": "ms:palette",
    "gizmogroup": "ms:extension",
    "pastebranch": "ms:alt_route",
    "newsession": "ms:open_in_new",
    "precomp": "ms:library_books",
    "extract": "ms:eject",
    "copyclone": "ms:copy_all",
    "declone": "ms:sync_disabled",
    "forceclone": "ms:sync_lock",
    "rendersel": "ms:movie_edit",
}

# Same action as in a sibling set: a byte-identical copy.
BORROW = {
    "maximize.png": "blender",          # expand the focused panel
    "ed_graph.png": "blender",          # curve editor
    "ed_dopesheet.png": "blender",      # dope sheet
    "preferences.png": "blender",
    "deselect.png": "blender",          # select none
    "workspace_next.png": "blender",    # next pane
    "workspace_prev.png": "blender",    # previous pane
    "search.png": "blender",            # search by node name
    "fit_view.png": "blender",          # fit nodes to the panel
    "mute.png": "blender",              # disable / enable node
    "hier_child.png": "blender",        # next node in tree
    "hier_parent.png": "blender",       # previous node in tree
    "merge.png": "blender",             # Merge node
    "rename.png": "blender",
    "move.png": "blender",              # Transform node
    "swap.png": "blender",              # swap A/B inputs
    "render_anim.png": "blender",       # render all Write nodes
    "play_rendered.png": "blender",     # flipbook
    "duplicate.png": "blender",
    "duplicate_linked.png": "blender",  # clone
    "extrude_forked.png": "blender",    # duplicate and branch
    "link.png": "blender",              # expression links
    "node_preview.png": "blender",      # postage stamp
    "group.png": "blender",
    "ungroup.png": "blender",
    "group_enter.png": "blender",       # open a group's sub-graph
    "viewer.png": "blender",            # new compositing viewer
}

NUKE_ICON_URL = "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/nuke.svg"


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(ICONS, out)
    icon_fetch.borrow(BORROW, out)
    g.guarded(out / "nuke.png",
              lambda p: g.trace_mark(g.svg_icon(NUKE_ICON_URL), p, lit="dark"),
              "simple-icons/nuke (CC0), 32x32 trace")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
