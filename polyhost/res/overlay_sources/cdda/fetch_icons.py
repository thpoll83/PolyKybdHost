#!/usr/bin/env python3
"""Fetch + render the Cataclysm: Dark Days Ahead icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0), Material
Design Icons (Apache-2.0) and game-icons.net (CC BY 3.0); the movement arrows
are drawn by the helpers of the Dungeon Crawl Stone Soup set. SOURCES.md credits
each. The ESC mark is "Cataclysm" over "DDA" set in Creepster (SIL OFL 1.1);
the game's own art is CC BY-SA 3.0 and is not used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/cdda/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.dcss import fetch_icons as dcss  # noqa: E402

ICONS = {
    # Plain keys
    "pause": "fa:hourglass-half",
    "opendoor": "fa:door-open",
    "closedoor": "fa:door-closed",
    "smash": "fa:hammer",
    "examine": "fa:magnifying-glass",
    "advinv": "fa:boxes-stacked",
    "pickup": "mdi:tray-arrow-up",
    "haul": "fa:dolly",
    "look": "fa:eye",
    "inventory": "mdi:bag-personal",
    "organize": "fa:arrow-down-a-z",
    "apply": "fa:hand-pointer",
    "wield": "mdi:knife-military",
    "insert": "fa:arrow-right-to-bracket",
    "throw": "gi:lorc/thrown-daggers",
    "fire": "fa:crosshairs",
    "defaultammo": "mdi:ammunition",
    "drop": "mdi:tray-arrow-down",
    "bionics": "fa:microchip",
    "mutations": "fa:dna",
    "recraft": ("fa:screwdriver-wrench", "again"),
    "ignoreenemy": "fa:eye-slash",
    "map": "fa:map",
    "help": "fa:circle-question",
    "reload": ("mdi:ammunition", "again"),
    "actionmenu": "fa:bars",
    "autoattack": ("mdi:sword-cross", "bolt"),
    "spells": "fa:wand-sparkles",
    "zoomin": "fa:magnifying-glass-plus",
    # Shift
    "grab": "fa:hand-back-fist",
    "zoneactivity": "fa:person-digging",
    "butcher": "gi:lorc/meat-cleaver",
    "chat": "fa:comments",
    "peek": "fa:user-secret",
    "listitems": "fa:list",
    "zones": "fa:vector-square",
    "compare": "fa:scale-balanced",
    "applywielded": "fa:hand-fist",
    "wear": ("fa:shirt", "plus"),
    "takeoff": ("fa:shirt", "minus"),
    "eat": "fa:utensils",
    "read": "fa:book-open",
    "martialarts": "mdi:karate",
    "unload": ("mdi:ammunition", "minus"),
    "firemode": "fa:sliders",
    "dropadjacent": "mdi:subdirectory-arrow-right",
    "medical": "fa:kit-medical",
    "bodystatus": "fa:heart-pulse",
    "sortarmor": "fa:layer-group",
    "wait": "fa:clock",
    "craft": "fa:screwdriver-wrench",
    "construct": "fa:trowel-bricks",
    "disassemble": "mdi:puzzle-remove",
    "sleep": "fa:bed",
    "vehicle": "mdi:steering",
    "safemode": "fa:triangle-exclamation",
    "whitelist": "fa:user-check",
    "save": "fa:floppy-disk",
    "playerinfo": "fa:id-card",
    "missions": "fa:flag-checkered",
    "factions": "fa:people-group",
    "messages": "fa:message",
    "itemactions": "fa:rectangle-list",
    "movemode": "fa:person-walking",
    "diary": "fa:trophy",
    "zoomout": "fa:magnifying-glass-minus",
    "keybindings": "fa:keyboard",
    "upstairs": "mdi:stairs-up",
    "downstairs": "mdi:stairs-down",
}
for _d in dcss.DIRECTIONS:
    ICONS[f"move_{_d}"] = f"draw:move:{_d}"

# Key area of each icon, from cdda.yaml; the default is 40 x 40.
SIZES = {"defaultammo": (34, 40)}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"save": (34, 34), "help": (34, 34), "actionmenu": (30, 30), "map": (36, 34),
       "messages": (34, 34), "wait": (34, 34), "closedoor": (34, 36), "safemode": (36, 34),
       "medical": (36, 34), "defaultammo": (30, 36), "itemactions": (36, 34)}

# The ESC mark is set in Creepster (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/creepster/Creepster-Regular.ttf")
MARK_LINES = ("Cataclysm", "DDA")
MARK_THRESHOLD = 100        # grey level (0..255) from which a pixel is lit


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    dcss.build(ICONS, out, SIZES, INK)
    dcss.wordmark(MARK_LINES, FONT_URL, out / "program.png", MARK_THRESHOLD)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
