#!/usr/bin/env python3
"""Fetch + render the Adobe After Effects shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** throughout — unlike the
two NLE sets, After Effects' shortcuts are layer *properties* and tools that map
cleanly onto generic UI glyphs (anchor/position/scale/rotation/opacity/effects),
so nothing needed custom drawing. The ESC **program mark** is a drawn,
license-clean substitute (`../rect_mark.py`): a framed "Ae", set at the size the
whole Adobe family shares.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/aftereffects/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import rect_mark  # noqa: E402

FLUENT = {
    # layer properties (the single-letter row -- After Effects' signature)
    "anchorpoint": "Target",
    "position": "Arrow Move",
    "scale": "Resize",
    "rotation": "Arrow Rotate Clockwise",
    "opacity": "Circle Half Fill",
    "feather": "Blur",
    "effects": "Wand",
    "keyframes": "Diamond",
    # tools
    "select": "Cursor",
    "hand": "Hand Right",
    "zoom": "Zoom In",
    "pen": "Pen",
    "shape": "Shapes",
    "panbehind": "Drag",
    "type": "Text T",
    # file / project
    "newcomp": "Add Square",
    "open": "Folder Open",
    "save": "Save",
    "import": "Arrow Import",
    "renderqueue": "List",
    "compsettings": "Settings",
    "solid": "Square",
    # edit
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "selectall": "Select All On",
    "duplicate": "Square Multiple",
    "splitlayer": "Split Vertical",
    "precompose": "Layer",
    # timeline
    "gotoin": "Arrow Import",
    "gotoout": "Arrow Export",
    "preview": "Play",
}


# --- One icon per action (maintainer, 2026-11-15) ----------------------------
# Two keys of this app share an image only when they do the same thing. The
# glyphs below give the other keys their own image. The older files stay, because
# other sets may copy them (icon_fetch.borrow).
ACTION_FLUENT = {
    "rotationtool": "ms:rotate_right",
    "gotolayerin": "Arrow Previous",
}
# file -> (base, badge): the base reduced to the upper left, the badge in the
# lower right (dcc_glyphs.with_badge).
ACTION_BADGED = {
}


def action_icons(out: Path) -> None:
    """Draw the ACTION_* icons; a committed composite is left as it is."""
    from polyhost.res.overlay_sources import dcc_glyphs, icon_fetch as fetch
    if ACTION_FLUENT:
        fetch.fluent(ACTION_FLUENT, out)
    for name, (base, badge) in ACTION_BADGED.items():
        dcc_glyphs.guarded(out / name, lambda p, b=base, g=badge: dcc_glyphs.with_badge(
            out / b, out / g, p), f"{base} + {badge}")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    # One size across the whole family (see rect_mark.shared_size).
    rect_mark.ensure(out / "aftereffects.png", "Ae",
                     size=rect_mark.shared_size(["Ps", "Ai", "Pr", "Ae"]))
    action_icons(out)
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
