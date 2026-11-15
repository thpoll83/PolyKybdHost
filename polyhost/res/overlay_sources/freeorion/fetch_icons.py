#!/usr/bin/env python3
"""Fetch + render the FreeOrion icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0)
and game-icons.net (CC BY 3.0). SOURCES.md credits each icon. Each icon is
drawn at exactly its key area, so the generator places it 1:1.

The "previous" and "next" keys (system, owned system, fleet, idle fleet) are
the icon of the thing with an arrow to the left or to the right above it.

The ESC mark is "FREE" over "ORION" set in Orbitron Bold (SIL OFL 1.1). The
game's logo art is not used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/freeorion/fetch_icons.py

The key icons are re-rendered on every run; the output does not change between
runs. The ESC mark is written only when its PNG is missing.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.freeciv import fetch_icons as fc  # noqa: E402
from polyhost.res.overlay_sources.wesnoth import fetch_icons as wesnoth  # noqa: E402

ICONS = {
    # Windows of the map screen
    "endturn": "fa:hourglass-end",
    "sitrep": "fa:clipboard-list",
    "research": "fa:flask",
    "production": "fa:industry",
    "government": "fa:landmark",
    "design": "fa:pen-ruler",
    "objects": "fa:list-ul",
    "empires": "fa:flag",
    "messages": "fa:comments",
    "pedia": "fa:book-open",
    "menu": "fa:bars",
    # Map view
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "homesystem": "fa:house",
    "panup": "fa:arrow-up",
    "pandown": "fa:arrow-down",
    "panleft": "fa:arrow-left",
    "panright": "fa:arrow-right",
    "scaleline": "fa:ruler-horizontal",
    "scalecircle": "fa:compass-drafting",
    "fullscreen": "fa:expand",
    # Text fields
    "copy": "fa:copy",
    "paste": "fa:paste",
    "selectall": "fa:check-double",
}
# Previous and next: stem prefix -> icon. Each gives <prefix>_prev.png and
# <prefix>_next.png, drawn by arrow_icons().
ARROW_ICONS = {
    "system": "fa:sun",
    "ownedsystem": "gi:lorc/ringed-planet",
    "fleet": "fa:rocket",
    "idlefleet": "fa:anchor",
}
ARROWS = {"prev": "fa:arrow-left", "next": "fa:arrow-right"}

# Key area (w, h) of each icon; the default is 40 x 40. F1 uses the width the
# AoE2 set measured to keep its legend whole.
SIZES = {"pedia": (34, 40)}
# The box (w, h) the ink of single icons fills, where it is not the default.
INK = {"menu": (30, 30), "zoomin": (32, 32), "zoomout": (32, 32),
       "panup": (28, 30), "pandown": (28, 30), "panleft": (30, 28), "panright": (30, 28),
       "pedia": (32, 30), "fullscreen": (30, 30), "scaleline": (36, 22),
       "copy": (30, 32), "paste": (30, 32), "sitrep": (28, 34)}

MARK_FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
                 "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/orbitron/Orbitron%5Bwght%5D.ttf")
MARK_WEIGHT = 700                          # the Bold instance of the variable font
MARK_LINES = ("FREE", "ORION")


def arrow_icons(icons: dict, arrows: dict, raw: Path, out: Path) -> None:
    """<prefix>_<direction>.png for every icon and arrow: the icon in a 30 x 26
    box in the bottom-right corner of a 40 x 40 area and the arrow, 16 x 11,
    in the top-right corner with 2 px cleared around it."""
    for prefix in icons:
        for direction in arrows:
            m = fc._corner(fc._fit(raw / f"{prefix}.png", (30, 26)), (40, 40))
            a = fc._fit(raw / f"_{direction}.png", (16, 11))
            fc._clear(m, a, 40 - a.shape[1], 0)
            cnc._save_mask(m, out / f"{prefix}_{direction}.png")
    print(f"  {len(icons) * len(arrows)} icons with an arrow drawn")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    wesnoth.build(out, ICONS, sizes=SIZES, ink=INK)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        cnc.render({**ARROW_ICONS, **{f"_{d}": spec for d, spec in ARROWS.items()}}, raw)
        arrow_icons(ARROW_ICONS, ARROWS, raw, out)
    wesnoth.wordmark(out / "program.png", MARK_LINES, MARK_FONT_URL, weight=MARK_WEIGHT)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
