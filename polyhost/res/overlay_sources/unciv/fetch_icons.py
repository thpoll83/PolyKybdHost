#!/usr/bin/env python3
"""Fetch + render the Unciv icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0)
and game-icons.net (CC BY 3.0). Where Unciv has the same action as
Civilization IV or Freeciv, the icon is the one those sets use. SOURCES.md
credits each icon. Each icon is drawn at exactly its key area, so the
generator places it 1:1.

F11 and F12 (quick save, quick load) are the save and load icons with a bolt,
as in the VCMI set. The ESC mark is "UNCIV" set in Cinzel Bold (SIL OFL 1.1).
The game's icon art is not used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/unciv/fetch_icons.py

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
from polyhost.res.overlay_sources.vcmi import fetch_icons as vcmi  # noqa: E402
from polyhost.res.overlay_sources.wesnoth import fetch_icons as wesnoth  # noqa: E402

ICONS = {
    # World screen
    "nextturn": "fa:hourglass-end",
    "menu": "fa:bars",
    "empire": "fa:city",
    "console": "fa:terminal",
    "idleprev": "fa:backward-step",
    "idlenext": "fa:forward-step",
    "capital": "fa:star",
    "panup": "fa:arrow-up",
    "panleft": "fa:arrow-left",
    "pandown": "fa:arrow-down",
    "panright": "fa:arrow-right",
    # World screen: function keys
    "civilopedia": "fa:book-open",
    "trades": "fa:handshake",
    "units": "gi:lorc/crossed-swords",
    "politics": "fa:flag",
    "policies": "fa:landmark",
    "technology": "fa:flask",
    "notifications": "fa:bell",
    "victory": "fa:trophy",
    "stats": "fa:chart-column",
    "resources": "fa:cubes",
    # World screen: Ctrl
    "autoplay": "fa:circle-play",
    "music": "fa:music",
    "options": "fa:gear",
    "save": "fa:floppy-disk",
    "load": "fa:folder-open",
    "resourceicons": "fa:gem",
    "yieldicons": "fa:wheat-awn",
    "quit": "fa:power-off",
    "newgame": "fa:file-circle-plus",
    "undo": "fa:rotate-left",
    "toggleui": "fa:eye-slash",
    # Unit actions
    "foundcity": "fa:building-flag",
    "automate": "fa:robot",
    "fortify": "fa:shield-halved",
    "heal": "fa:shield-heart",
    "explore": "fa:compass",
    "promote": "fa:medal",
    "upgrade": "fa:circle-up",
    "transform": "fa:shuffle",
    "pillage": "fa:fire",
    "setup": "gi:lorc/cannon",
    "improve": "fa:person-digging",
    "repair": "fa:screwdriver-wrench",
    "greatperson": "fa:user-graduate",
    "disband": "fa:trash-can",
    "skip": "fa:forward",
    "destination": "fa:location-dot",
    "swapunits": "fa:right-left",
    "moreactions": "fa:ellipsis",
    "lessactions": "fa:reply",
}
# Quick save and quick load: stem -> (icon, key area). Drawn by vcmi.bolt_icons().
BOLT_ICONS = {"quicksave": ("fa:floppy-disk", (40, 40)), "quickload": ("fa:folder-open", (40, 40))}

# Key area (w, h) of each icon; the default is 40 x 40. The function keys use
# the legend widths that the AoE2 and OpenTTD sets measured: F1 to F3 and F8
# 34 x 40, F4 to F7 30 x 40, F9 to F12 40 x 40.
SIZES = {"civilopedia": (34, 40), "trades": (34, 40), "units": (34, 40),
         "politics": (30, 40), "policies": (30, 40), "technology": (30, 40),
         "notifications": (30, 40), "victory": (34, 40)}
# The box (w, h) the ink of single icons fills, where it is not the default.
INK = {"save": (30, 30), "options": (30, 30), "quit": (32, 32), "menu": (30, 30),
       "idleprev": (28, 30), "idlenext": (28, 30), "skip": (32, 28),
       "panup": (28, 30), "pandown": (28, 30), "panleft": (30, 28), "panright": (30, 28),
       "autoplay": (32, 32), "upgrade": (32, 32), "disband": (28, 32),
       "destination": (26, 34), "moreactions": (32, 12), "transform": (34, 30),
       "swapunits": (34, 28), "civilopedia": (32, 30), "trades": (34, 28),
       "units": (32, 32), "victory": (32, 30)}

MARK_FONT_URL = fc.MARK_FONT_URL        # Cinzel (SIL OFL 1.1), a variable font
MARK_LINES = ("UNCIV",)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    wesnoth.build(out, ICONS, sizes=SIZES, ink=INK)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        cnc.render({**{s: spec for s, (spec, _) in BOLT_ICONS.items()},
                    "_bolt": vcmi.BOLT}, raw)
        vcmi.bolt_icons(BOLT_ICONS, raw, out)
    wesnoth.wordmark(out / "program.png", MARK_LINES, MARK_FONT_URL, weight=fc.MARK_WEIGHT,
                     max_h=30)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
