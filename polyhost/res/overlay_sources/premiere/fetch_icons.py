#!/usr/bin/env python3
"""Fetch + render the Adobe Premiere Pro shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** plus the shared
custom-drawn NLE glyphs (`../nle_glyphs.py`) — including four drawn specifically
for Premiere's tool row (ripple / rolling / slip / slide), whose whole point is
*which* clip edge moves and by how much. No generic icon set expresses that.
The ESC **program mark** is a drawn, license-clean substitute
(`../rect_mark.py`): Adobe's Pr logo is a trademark we may not redistribute, so
the cell carries a framed "Pr" — the app's own naming, not its logo styling.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/premiere/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import rect_mark  # noqa: E402
import nle_glyphs  # noqa: E402

FLUENT = {
    # tools
    "select": "Cursor",
    "ratestretch": "Top Speed",
    "pen": "Pen",
    "hand": "Hand Right",
    "zoom": "Zoom In",
    # file / project
    "newproject": "Document Add",
    "newsequence": "Add Square",
    "open": "Folder Open",
    "save": "Save",
    "saveas": "Save Multiple",
    "import": "Arrow Import",
    "export": "Arrow Export",
    # edit
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "pasteinsert": "Arrow Between Down",
    "selectall": "Select All On",
    "group": "Group",
    "ungroup": "Group Dismiss",
    "link": "Link",
    "addedit": "Split Vertical",
    "speed": "Arrow Autofit Width",
    # view / transport
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "zoomfit": "Arrow Expand",
    "play": "Play",
    "stop": "Stop",
    "fwd": "Fast Forward",
    "rev": "Rewind",
    # panels (Shift+1..7)
    "panelproject": "Folder Open",
    "panelsource": "Video Clip",
    "paneltimeline": "Timeline",
    "panelprogram": "Play Circle",
    "paneleffectctl": "Options",
    "panelaudio": "Music Note 2",
    "paneleffects": "Wand",
}

DRAWN = ["blade", "markin", "markout", "rippledelete",
         "rippleedit", "rolledit", "slip", "slide", "trackselect"]


# --- One icon per action (maintainer, 2026-11-15) ----------------------------
# Two keys of this app share an image only when they do the same thing. The
# glyphs below give the other keys their own image. The older files stay, because
# other sets may copy them (icon_fetch.borrow).
ACTION_FLUENT = {
    "zoomtool": "Search",
    "panelproj": "Folder List",
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
    n += nle_glyphs.draw_all(out, DRAWN)
    # One size across the whole family (see rect_mark.shared_size).
    rect_mark.ensure(out / "premiere.png", "Pr",
                     size=rect_mark.shared_size(["Ps", "Ai", "Pr", "Ae"]))
    action_icons(out)
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
