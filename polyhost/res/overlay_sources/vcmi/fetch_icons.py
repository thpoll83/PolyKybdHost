#!/usr/bin/env python3
"""Fetch + render the VCMI icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0),
game-icons.net (CC BY 3.0) and Material Design Icons (Apache-2.0). Where VCMI
has the same action as fheroes2, the icon is the one the fheroes2 set uses.
SOURCES.md credits each icon. Each icon is drawn at exactly its key area, so
the generator places it 1:1.

F8 and F9 (quick save, quick load) are the save and load icons with a bolt, as
F2 in the fheroes2 set. The ESC mark is "VCMI" set in Cinzel Bold (SIL OFL
1.1). The project's logo art is not used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/vcmi/fetch_icons.py

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
    # Adventure map: heroes and towns (the fheroes2 icons)
    "endturn": "fa:hourglass-end",
    "nexthero": "gi:lorc/visored-helm",
    "nexttown": "gi:delapouite/castle",
    "movehero": "fa:person-walking-arrow-right",
    "sleephero": "fa:bed",
    "castspell": "fa:wand-magic-sparkles",
    "dig": "gi:lorc/spade",
    "visitobject": "fa:circle-play",
    "openselected": "fa:up-right-from-square",
    # Adventure map: heroes and towns (VCMI only)
    "wakehero": "fa:bell",
    "nextobject": "fa:forward-step",
    "trackhero": "fa:crosshairs",
    "moveNW": "mdi:arrow-top-left-thick",
    "moveNE": "mdi:arrow-top-right-thick",
    "moveSW": "mdi:arrow-bottom-left-thick",
    "moveSE": "mdi:arrow-bottom-right-thick",
    "listup": "fa:arrow-up",
    "listdown": "fa:arrow-down",
    "listtop": "fa:arrows-up-to-line",
    "listbottom": "fa:arrows-down-to-line",
    "dismiss": "fa:user-xmark",
    # Adventure map: views and dialogs (the fheroes2 icons)
    "viewworld": "gi:lorc/treasure-map",
    "kingdom": "fa:crown",
    "puzzle": "fa:puzzle-piece",
    "scenarioinfo": "fa:circle-info",
    "options": "fa:gear",
    "newgame": "fa:file-circle-plus",
    "save": "fa:floppy-disk",
    "load": "fa:folder-open",
    "quit": "fa:power-off",
    "fullscreen": "fa:expand",
    # Adventure map: views and dialogs (VCMI only)
    "marketplace": "fa:store",
    "questlog": "fa:scroll",
    "thievesguild": "fa:user-secret",
    "statistics": "fa:chart-column",
    "maplevel": "fa:stairs",
    "grid": "fa:table-cells",
    "restart": "fa:rotate",
    "mainmenu": "fa:bars",
    "lobby": "fa:globe",
    "search": "fa:magnifying-glass",
    "searchnext": "fa:magnifying-glass-arrow-right",
    "wiki": "fa:book-open",
    "console": "fa:terminal",
    "screenshot": "fa:camera",
    # Battle, town and exchange screens
    "autocombat": "fa:robot",
    "fort": "fa:chess-rook",
    "garrisonhero": "fa:person-shelter",
    "swaparmies": "fa:right-left",
    "swapartifacts": "fa:gem",
    "swapbackpack": "fa:suitcase",
    "swapequipped": "fa:shirt",
}
# An icon with a short text above it: stem -> (icon, text).
TEXT_ICONS = {
    "firsthero": ("gi:lorc/visored-helm", "1st"),
    "firsttown": ("gi:delapouite/castle", "1st"),
    "world1": ("fa:map", "x1"),
    "world2": ("fa:map", "x2"),
    "world4": ("fa:map", "x4"),
    "zoomreset": ("fa:magnifying-glass", "1:1"),
}
# Quick save and quick load: stem -> (icon, key area). Drawn by bolt_icons().
BOLT_ICONS = {"quicksave": ("fa:floppy-disk", (34, 40)), "quickload": ("fa:folder-open", (40, 40))}
BOLT = "fa:bolt"

# Key area (w, h) of each icon; the default is 40 x 40. The function keys use
# the legend widths that the AoE2 and OpenTTD sets measured: F1 to F3 and F8
# 34 x 40, F4 to F7 30 x 40, F9 to F12 40 x 40.
SIZES = {"wiki": (34, 40), "screenshot": (34, 40), "fullscreen": (30, 40),
         "trackhero": (30, 40), "grid": (30, 40)}
# The box (w, h) the ink of single icons fills, where it is not the default.
INK = {"save": (30, 30), "options": (30, 30), "nextobject": (28, 30),
       "quit": (32, 32), "search": (32, 32), "searchnext": (32, 32),
       "scenarioinfo": (32, 32), "visitobject": (32, 32), "listup": (28, 30),
       "listdown": (28, 30), "moveNW": (30, 30), "moveNE": (30, 30),
       "moveSW": (30, 30), "moveSE": (30, 30), "fullscreen": (28, 28),
       "trackhero": (28, 28), "grid": (28, 28), "screenshot": (32, 30),
       "wiki": (32, 30), "lobby": (32, 32), "mainmenu": (30, 30)}

MARK_FONT_URL = fc.MARK_FONT_URL        # Cinzel (SIL OFL 1.1), a variable font
MARK_LINES = ("VCMI",)


def bolt_icons(icons: dict, raw: Path, out: Path, bolt: str = "_bolt") -> None:
    """Each icon of `icons` (stem -> (spec, key area)) at 26 px in the
    bottom-right corner of its key area, with a bolt above its left edge, cut
    out of the icon by a 2 px gap. `raw/<stem>.png` is the rendered icon and
    `raw/<bolt>.png` the rendered bolt."""
    import numpy as np
    for stem, (_spec, size) in icons.items():
        m = fc._corner(fc._fit(raw / f"{stem}.png", (26, 26)), size)
        b = fc._fit(raw / f"{bolt}.png", (14, 20))
        fc._clear(m, b, size[0] - 34, 0)
        cnc._save_mask(np.asarray(m), out / f"{stem}.png")
    print(f"  {len(icons)} icons with a bolt drawn")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    wesnoth.build(out, ICONS, sizes=SIZES, ink=INK, with_text=TEXT_ICONS)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        cnc.render({**{s: spec for s, (spec, _) in BOLT_ICONS.items()}, "_bolt": BOLT}, raw)
        bolt_icons(BOLT_ICONS, raw, out)
    wesnoth.wordmark(out / "program.png", MARK_LINES, MARK_FONT_URL, weight=fc.MARK_WEIGHT,
                     max_h=30)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
