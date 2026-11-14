#!/usr/bin/env python3
"""Fetch + render the NetHack icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0), Material
Design Icons (Apache-2.0) and game-icons.net (CC BY 3.0); the direction keys
(an arrow to move, an arrow that ends at a bar to rush, a double chevron to
run) are drawn by the helpers of the Dungeon Crawl Stone Soup set. SOURCES.md
credits each. The ESC mark is "Net" over "Hack" set in VT323 (SIL OFL 1.1); the
game's own art is under the NetHack General Public License and is not used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/nethack/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.dcss import fetch_icons as dcss  # noqa: E402

ICONS = {
    # Plain keys
    "apply": "mdi:pickaxe",
    "closedoor": "fa:door-closed",
    "drop": "mdi:tray-arrow-down",
    "eat": "fa:utensils",
    "fire": "fa:crosshairs",
    "inventory": "mdi:bag-personal",
    "opendoor": "fa:door-open",
    "pay": "fa:coins",
    "quaff": "fa:flask",
    "read": "fa:scroll",
    "search": "fa:magnifying-glass",
    "throw": "gi:lorc/thrown-daggers",
    "wield": "mdi:sword",
    "swapweapons": ("mdi:sword", "swap"),
    "zap": "gi:lorc/crystal-wand",
    "pickup": "mdi:tray-arrow-up",
    "wait": "fa:hourglass-half",
    "whatis": "fa:question",
    "glance": "fa:eye",
    "known": "fa:clipboard-list",
    "knownclass": "fa:list",
    # Shift
    "takeoffall": "mdi:hanger",
    "call": "fa:tag",
    "droptype": "mdi:download-multiple",
    "engrave": "fa:pen-nib",
    "fight": "fa:hand-fist",
    "inventtype": "fa:filter",
    "options": "fa:gear",
    "puton": ("fa:ring", "plus"),
    "quiver": "mdi:bow-arrow",
    "remove": ("fa:ring", "minus"),
    "save": "fa:floppy-disk",
    "takeoff": ("fa:shirt", "minus"),
    "wear": ("fa:shirt", "plus"),
    "twoweapon": "mdi:sword-cross",
    "cast": "fa:wand-sparkles",
    "upstairs": "mdi:stairs-up",
    "downstairs": "mdi:stairs-down",
    "help": "fa:circle-question",
    "autopickup": "fa:magnet",
    "extended": "mdi:form-textbox",
    "whatdoes": "fa:keyboard",
    "seeall": "mdi:shield-sword",
    "shell": "fa:terminal",
    "showtrap": "gi:lorc/wolf-trap",
    "travel": "fa:route",
    "lookhere": "mdi:map-marker-question",
    # Ctrl
    "repeat": "fa:rotate-right",
    "kick": "mdi:karate",
    "overview": "fa:sitemap",
    "messages": "fa:message",
    "redraw": "fa:arrows-rotate",
    "teleport": "gi:lorc/teleport",
    "attributes": "fa:id-card",
    "suspend": "fa:pause",
    # Alt (the extended commands with a Meta key)
    "adjust": "fa:arrow-down-a-z",
    "chat": "fa:comments",
    "dip": "fa:fill-drip",
    "enhance": "fa:ranking-star",
    "force": "fa:lock-open",
    "invoke": "fa:hand-sparkles",
    "jump": "gi:delapouite/jump-across",
    "loot": "mdi:treasure-chest",
    "monster": "fa:dragon",
    "offer": "gi:lorc/fire-bowl",
    "pray": "fa:hands-praying",
    "rub": "gi:lorc/magic-lamp",
    "sit": "fa:chair",
    "turn": "fa:ghost",
    "untrap": ("gi:lorc/wolf-trap", "minus"),
    "version": "fa:circle-info",
    "wipe": "fa:soap",
    "extendedlist": "fa:rectangle-list",
    # Alt+Shift
    "annotate": "fa:thumbtack",
    "conduct": "fa:medal",
    "ride": "fa:horse",
    "tip": "mdi:package-down",
}
for _d in dcss.DIRECTIONS:
    ICONS[f"move_{_d}"] = f"draw:move:{_d}"
    ICONS[f"rush_{_d}"] = f"draw:rush:{_d}"
    ICONS[f"run_{_d}"] = f"draw:run:{_d}"

SIZES: dict = {}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"save": (34, 34), "help": (34, 34), "messages": (34, 34), "closedoor": (34, 36),
       "known": (34, 36), "suspend": (30, 30), "version": (34, 34), "call": (34, 34),
       "options": (34, 34), "inventtype": (34, 34), "extendedlist": (36, 34),
       "whatis": (24, 34)}

# The ESC mark is set in VT323 (SIL OFL 1.1), a terminal font.
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/vt323/VT323-Regular.ttf")
MARK_LINES = ("Net", "Hack")
MARK_THRESHOLD = 110        # grey level (0..255) from which a pixel is lit
MARK_GAP = 0                # px between the two lines


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    dcss.build(ICONS, out, SIZES, INK)
    dcss.wordmark(MARK_LINES, FONT_URL, out / "program.png", MARK_THRESHOLD, MARK_GAP)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
