#!/usr/bin/env python3
"""Fetch + render the Autodesk Fusion shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. No program icon: the
host draws the ESC mark for the app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/fusion/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

FLUENT = {
    # --- file and layout ---
    "recoverysave": "ms:restore_page",
    "viewcube": "ms:view_in_ar",
    "browser": "ms:account_tree",
    "comments": "Comment",
    "textcmds": "ms:terminal",
    "navbar": "ms:toolbar",
    "datapanel": "ms:cloud",
    "resetlayout": "ms:restart_alt",
    "nexttab": "ms:tab",
    "prevws": "ms:navigate_before",
    "nextws": "ms:navigate_next",
    "assistant": "ms:support_agent",
    # --- design ---
    "extrude": "ms:vertical_align_top",
    "hole": "ms:adjust",
    "presspull": "ms:unfold_more",
    "fillet": "ms:rounded_corner",
    "move": "ms:open_with",
    "visibility": "Eye",
    "compcolors": "ms:palette",
    "toolbox": "ms:manage_search",
    "appearance": "ms:format_paint",
    "joint": "ms:link",
    "asbuilt": "ms:add_link",
    "measure": "ms:straighten",
    "scripts": "ms:code",
    "selwindow": "ms:select",
    "selfree": "ms:gesture",
    "selpaint": "ms:brush",
    "computeall": "ms:calculate",
    # --- sketch ---
    "line": "ms:diagonal_line",
    "rectangle": "ms:rectangle",
    "circle": "ms:circle",
    "trim": "ms:ink_eraser",
    "offset": "ms:fit_screen",
    "project": "ms:system_update_alt",
    "construction": "ms:line_style",
    "dimension": "ms:width",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
