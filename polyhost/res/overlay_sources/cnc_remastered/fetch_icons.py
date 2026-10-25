#!/usr/bin/env python3
"""Fetch + render the Command & Conquer Remastered Collection icons (reproducible).

The icons are Material Design Icons (Pictogrammers, Apache-2.0): flat filled
silhouettes, which read better on the 1-bit keycap than the detailed drawings
of game-icons.net. The control-group icons reuse the Age of Empires II builder
(each unit twice with a 3 px seam, a plus for Ctrl). The ESC mark is a drawn
"C&C" word in Liberation Sans (SIL OFL 1.1), not the game's logo.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/cnc_remastered/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import cairosvg

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.icon_fetch import _get  # noqa: E402

MDI = "https://raw.githubusercontent.com/Templarian/MaterialDesign/master/svg/{}.svg"

ICONS = {
    # Sidebar tabs
    "tabstructures": "factory",
    "tabinfantry": "walk",
    "tabvehicles": "tank",
    "tabsuper": "nuke",
    # Orders and selection
    "stop": "hand-back-left",
    "scatter": "arrow-expand-all",
    "guard": "shield",
    "selectscreen": "select-group",
    "selectall": "earth",
    "queuedmove": "map-marker-path",
    # Camera
    "conyard": "crane",
    "lastevent": "radar",
    "bookmark": "bookmark",
    "bookmarkset": "bookmark-plus",
    # Display
    "graphics": "diamond-stone",
    "fullscreen": "fullscreen",
}

# Control groups 1..0: one unit each, drawn twice (aoe2.groups()).
GROUP_UNITS = {
    "1": "walk",                # infantry
    "2": "account-hard-hat",    # engineer
    "3": "car-estate",          # buggy, Humvee, jeep
    "4": "truck",               # APC, supply truck
    "5": "tank",
    "6": "rocket",              # rocket launcher, V2
    "7": "helicopter",          # Orca, Apache, Chinook
    "8": "airplane",            # A-10, MiG, Yak
    "9": "ferry",               # gunboat, destroyer
    "0": "tractor",             # harvester
}


def mdi(mapping: dict[str, str], out_dir: Path, render_px: int = 256) -> None:
    """Render `{filename_stem: mdi_name}` into `out_dir` as black-on-transparent PNGs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for stem, name in mapping.items():
        png = cairosvg.svg2png(bytestring=_get(MDI.format(name)),
                               output_width=render_px, output_height=render_px)
        (out_dir / f"{stem}.png").write_bytes(png)
        print(f"  {stem}.png  <- mdi:{name} (Apache-2.0)")


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
    mdi(ICONS, out)
    mdi({f"_unit{d}": n for d, n in GROUP_UNITS.items()}, out)
    for stem in ICONS:
        aoe2.trim(out, stem)
    aoe2.groups(out, GROUP_UNITS)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
