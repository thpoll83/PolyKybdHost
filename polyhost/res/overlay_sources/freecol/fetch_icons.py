#!/usr/bin/env python3
"""Fetch + render the FreeCol icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0),
game-icons.net (CC BY 3.0) and Material Design Icons (Apache-2.0). Where
FreeCol has the same action as Freeciv or Civilization IV, the icon is the one
those sets use. SOURCES.md credits each icon. Each icon is drawn at exactly
its key area, so the generator places it 1:1.

The ESC mark is "FreeCol" set in IM Fell English SC (SIL OFL 1.1). The game's
icon art is not used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/freecol/fetch_icons.py

The key icons are re-rendered on every run; the output does not change between
runs. The ESC mark is written only when its PNG is missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.wesnoth import fetch_icons as wesnoth  # noqa: E402

ICONS = {
    # Unit orders
    "buildcolony": "fa:building-flag",
    "fortify": "fa:shield-halved",
    "sentry": "fa:eye",
    "wait": "fa:clock",
    "skip": "fa:forward-step",
    "disband": "fa:user-xmark",
    "clearorders": "fa:eraser",
    "goto": "fa:route",
    "gototile": "fa:location-dot",
    "executegoto": "fa:play",
    "road": "fa:road",
    "plow": "fa:tractor",
    "clearforest": "gi:lorc/wood-axe",
    "load": "fa:right-to-bracket",
    "unload": "fa:right-from-bracket",
    "assigntraderoute": "fa:signs-post",
    "rename": "fa:pen",
    "nextontile": "fa:layer-group",
    "rangedattack": "gi:lorc/cannon",
    "moveNW": "mdi:arrow-top-left-thick",
    "moveNE": "mdi:arrow-top-right-thick",
    "moveSW": "mdi:arrow-bottom-left-thick",
    "moveSE": "mdi:arrow-bottom-right-thick",
    # Game and view
    "endturn": "fa:hourglass-end",
    "europe": "fa:earth-europe",
    "traderoutes": "fa:money-bill-transfer",
    "center": "fa:crosshairs",
    "chat": "fa:comment",
    "borders": "fa:vector-square",
    "grid": "fa:table-cells",
    "findsettlement": "fa:magnifying-glass-location",
    "mapcontrols": "fa:arrows-up-down-left-right",
    "showtile": "fa:circle-info",
    "viewmode": "fa:arrow-pointer",
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "fullscreen": "fa:expand",
    "newgame": "fa:file-circle-plus",
    "open": "fa:folder-open",
    "save": "fa:floppy-disk",
    "saveandquit": "fa:door-open",
    "quit": "fa:power-off",
    "preferences": "fa:gear",
    "reconnect": "fa:plug",
    # Reports (function keys)
    "religion": "fa:place-of-worship",
    "labour": "fa:person-digging",
    "colonies": "fa:city",
    "foreign": "fa:handshake-simple",
    "indian": "gi:delapouite/tipi",
    "congress": "fa:landmark",
    "military": "gi:lorc/crossed-swords",
    "naval": "fa:ship",
    "trade": "fa:coins",
    "turnreport": "fa:envelope",
    "requirements": "fa:list-check",
    "cargo": "fa:boxes-stacked",
    "exploration": "fa:compass",
    "history": "fa:scroll",
    "production": "fa:industry",
    "education": "fa:graduation-cap",
    "difficulty": "fa:gauge-high",
    "gameoptions": "fa:sliders",
    "mapoptions": "fa:map",
}
# An icon with a short text above it: stem -> (icon, text).
TEXT_ICONS = {"minimapzoomout": ("fa:magnifying-glass-minus", "MAP")}

# Key area (w, h) of each icon; the default is 40 x 40. The function keys use
# the legend widths that the AoE2 and OpenTTD sets measured: F1 to F3 and F8
# 34 x 40, F4 to F7 30 x 40, F9 to F12 40 x 40.
SIZES = {"religion": (34, 40), "labour": (34, 40), "colonies": (34, 40),
         "foreign": (30, 40), "indian": (30, 40), "congress": (30, 40),
         "military": (30, 40), "naval": (34, 40), "cargo": (34, 40),
         "exploration": (34, 40), "history": (34, 40), "production": (30, 40),
         "education": (30, 40)}
# The box (w, h) the ink of single icons fills, where it is not the default.
INK = {"save": (30, 30), "preferences": (30, 30), "quit": (32, 32),
       "skip": (28, 30), "executegoto": (28, 30), "chat": (32, 32),
       "zoomin": (32, 32), "zoomout": (32, 32), "showtile": (32, 32),
       "gototile": (26, 34), "moveNW": (30, 30), "moveNE": (30, 30),
       "moveSW": (30, 30), "moveSE": (30, 30), "fullscreen": (30, 30),
       "exploration": (30, 30), "viewmode": (24, 34), "rename": (30, 30),
       "foreign": (30, 26), "military": (30, 30), "indian": (30, 30)}

MARK_FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
                 "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/imfellenglishsc/IMFeENsc28P.ttf")
MARK_LINES = ("FreeCol",)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    wesnoth.build(out, ICONS, sizes=SIZES, ink=INK, with_text=TEXT_ICONS)
    wesnoth.wordmark(out / "program.png", MARK_LINES, MARK_FONT_URL, threshold=70)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
