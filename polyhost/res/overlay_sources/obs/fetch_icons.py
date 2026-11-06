#!/usr/bin/env python3
"""Fetch + render the OBS Studio shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The ESC mark is the OBS
Studio logo from Simple Icons (CC0 artwork; nominative use, see
`../brand_marks.py`).

    pip install cairosvg
    PYTHONPATH=. python polyhost/res/overlay_sources/obs/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    # --- edit ---
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "copysource": "Copy",
    "pasteref": "Clipboard Link",
    "remove": "Delete",
    "rename": "Rename",
    # --- transform ---
    "edittransform": "ms:transform",
    "copytransform": "Copy Arrow Right",
    "pastetransform": "Clipboard Arrow Right",
    "resettransform": "Arrow Reset",
    "fitscreen": "ms:fit_screen",
    "stretchscreen": "Scale Fill",
    "centerscreen": "ms:filter_center_focus",
    # --- order ---
    "moveup": "Position Forward",
    "movedown": "Position Backward",
    "movetop": "Position To Front",
    "movebottom": "Position To Back",
    # --- nudge in the preview ---
    "nudgeleft": "ms:keyboard_double_arrow_left",
    "nudgeright": "ms:keyboard_double_arrow_right",
    "nudgeup": "ms:keyboard_double_arrow_up",
    "nudgedown": "ms:keyboard_double_arrow_down",
    # --- view and application ---
    "fullscreen": "Full Screen Maximize",
    "settings": "Settings",
    "quit": "Power",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    brand_marks.ensure(out / "obs.png", "obsstudio")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
