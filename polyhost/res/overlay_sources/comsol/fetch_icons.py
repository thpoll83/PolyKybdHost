#!/usr/bin/env python3
"""Fetch + render the COMSOL Multiphysics shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) for the `ms:` entries. Icons for the same action as a MATLAB or
LabVIEW key are byte copies of those sets' icons (BORROW). The ESC mark is a
32x32 1-bit trace of COMSOL's site icon (see SOURCES.md); it is traced only
when the PNG is missing, so a committed or hand-edited mark is never redrawn.

    pip install cairosvg
    python polyhost/res/overlay_sources/comsol/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.labview.fetch_icons import _crop_to_ink  # noqa: E402
from polyhost.res.overlay_sources.typingtests.fetch_icons import (  # noqa: E402
    _guarded, _load, trace_mark)

FLUENT = {
    "documentation": "ms:menu_book",
    "rename": "ms:drive_file_rename_outline",
    "disable": "ms:block",
    "enable": "ms:check_circle",
    "update": "ms:update",
    "buildprev": "ms:skip_previous",
    "buildsel": "ms:build",
    "buildall": "ms:build_circle",
    "checksyntax": "ms:rule",
    "contextmenu": "ms:menu_open",
    "moveup": "ms:arrow_upward",
    "movedown": "ms:arrow_downward",
    "expandtree": "ms:unfold_more",
    "collapsetree": "ms:unfold_less",
    "collapseothers": "ms:compress",
    "duplicate": "ms:control_point_duplicate",
    "group": "ms:folder_special",
    "ungroup": "ms:folder_off",
    "deselect": "ms:deselect",
    "findinmethod": "ms:manage_search",
    "quantities": "ms:functions",
    "openwindow": "ms:file_open",
    "saveas": "Save Edit",
    "revert": "ms:restore_page",
    "snapshot": "ms:photo_camera",
    "modelbuilder": "ms:left_panel_open",
    "settings": "ms:right_panel_open",
    "appbuilder": "ms:apps",
    "modelmanager": "ms:inventory_2",
    "modeltree": "ms:account_tree",
    "bpenable": "ms:toggle_on",
    "shortcut": "ms:arrow_outward",
    "record": "ms:code_blocks",
    "localvar": "ms:data_object",
    "fold": "ms:unfold_less_double",
    "zoomfit": "ms:fit_screen",
    "testapp": "ms:science",
}

# Same action as a MATLAB or LabVIEW key: byte copies of their icons.
BORROW = {f"{n}.png": "matlab" for n in (
    "stepout", "back", "forward", "replace", "breakpoint", "comment", "stop",
    "pause", "prevsection", "nextsection")}
BORROW.update({f"{n}.png": "labview" for n in (
    "help", "nextwindow", "prevwindow", "actualsize")})

# COMSOL's site icon (the COMSOL mark), from Google's favicon service, 64 px.
MARK_URL = "https://www.google.com/s2/favicons?domain=comsol.com&sz=256"
MARK_LUMA = 160
MARK_DARK_LIT = True


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.borrow(BORROW, out)
    _guarded(out / "comsol.png", lambda p: trace_mark(
        _crop_to_ink(_load(MARK_URL), MARK_LUMA), p, MARK_LUMA, MARK_DARK_LIT))
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
