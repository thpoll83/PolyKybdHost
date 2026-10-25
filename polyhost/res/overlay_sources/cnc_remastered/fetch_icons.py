#!/usr/bin/env python3
"""Fetch + render the Command & Conquer Remastered Collection icons (reproducible).

The shortcut icons are from game-icons.net (CC BY 3.0); each author is
credited in SOURCES.md. The control-group icons reuse the Age of Empires II
builder (each unit twice with a 3 px seam, a plus for Ctrl). The ESC mark is a
drawn "C&C" word in Liberation Sans (SIL OFL 1.1), not the game's logo.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/cnc_remastered/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_icons  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402

ICONS = {
    # Sidebar tabs
    "tabstructures": "delapouite/factory",
    "tabinfantry": "skoll/brodie-helmet",
    "tabvehicles": "lorc/tank",
    "tabsuper": "lorc/mushroom-cloud",
    # Orders and selection
    "stop": "delapouite/stop-sign",
    "scatter": "delapouite/expand",
    "guard": "lorc/static-guard",
    "selectscreen": "sbed/select",
    "selectall": "lorc/globe",
    "queuedmove": "delapouite/path-distance",
    # Camera
    "conyard": "delapouite/crane",
    "lastevent": "lorc/radar-sweep",
    "bookmark": "lorc/bookmark",
    # Display
    "graphics": "lorc/crystal-growth",
    "fullscreen": "delapouite/resize",
}

# Control groups 1..0: one unit each, drawn twice (aoe2.groups()).
GROUP_UNITS = {
    "1": "skoll/brodie-helmet",
    "2": "lorc/gas-mask",
    "3": "skoll/jeep",
    "4": "skoll/apc",
    "5": "lorc/tank",
    "6": "delapouite/missile-launcher",
    "7": "delapouite/helicopter",
    "8": "delapouite/stealth-bomber",
    "9": "delapouite/submarine",
    "0": "delapouite/mine-truck",
}


def bookmark_set(out: Path) -> None:
    """bookmarkset.png: the bookmark with the control groups' plus (Ctrl+F1..F4)."""
    import numpy as np
    from PIL import Image
    src = Image.open(out / "bookmark.png").convert("RGBA").getchannel("A")
    src = src.crop(src.getbbox()).resize((30, 40), Image.LANCZOS)
    m = aoe2._with_plus(np.array(src) > 150)
    canvas = np.zeros((40, 30, 4), np.uint8)
    canvas[..., 3] = np.where(m, 255, 0)
    Image.fromarray(canvas, "RGBA").save(out / "bookmarkset.png")
    print("  bookmarkset.png  <- bookmark.png + plus")


def program(out: Path) -> None:
    """program.png: "C&C" in bold over the whole 72x40 cell. Kept when committed."""
    dest = out / "program.png"
    if dest.exists():
        print("  program.png  <- committed asset (left as-is)")
        return
    import numpy as np
    from PIL import Image
    for px in range(48, 10, -1):     # the largest size that leaves 1 px all round
        word = program_mark.text("C&C", "LiberationSans-Bold.ttf", px)
        if word.shape[1] <= program_mark.W - 2 and word.shape[0] <= program_mark.H - 2:
            break
    canvas = np.zeros((program_mark.H, program_mark.W), bool)
    program_mark.place(canvas, word, program_mark.W // 2,
                       (program_mark.H - word.shape[0]) // 2)
    rgba = np.zeros((program_mark.H, program_mark.W, 4), np.uint8)
    rgba[..., 3] = np.where(canvas, 255, 0)
    Image.fromarray(rgba, "RGBA").save(dest)
    print("  program.png  <- drawn \"C&C\" (Liberation Sans Bold)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_icons.render(ICONS, out)
    game_icons.render({f"_unit{d}": n for d, n in GROUP_UNITS.items()}, out, render_px=256)
    for stem in ("selectscreen", "queuedmove"):
        aoe2.trim(out, stem)
    aoe2.groups(out, GROUP_UNITS)
    bookmark_set(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
