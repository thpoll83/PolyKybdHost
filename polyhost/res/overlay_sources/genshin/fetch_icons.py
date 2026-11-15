#!/usr/bin/env python3
"""Fetch + render the Genshin Impact icons (reproducible).

Flat 1-bit silhouettes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and Material Symbols (Apache-2.0), drawn by `game_set.py`. The ESC
mark is GENSHIN in Bebas Neue (SIL OFL 1.1); HoYoverse's logo art is not used.

    PYTHONPATH=. python polyhost/res/overlay_sources/genshin/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_set  # noqa: E402

ICONS = {
    # Combat
    "skill": "gi:lorc/wind-slap",
    "burst": "gi:lorc/star-swirl",
    "aim": "ms:my_location",
    "member": "gi:delapouite/person",
    "jump": "gi:delapouite/jump-across",
    # World
    "interact": "ms:touch_app",
    "gadget": "gi:lorc/gear-hammer",
    "special": "ms:bolt",
    "drop": "ms:south",
    "navigate": "gi:delapouite/position-marker",
    "abandon": "ms:flag",
    # Menus
    "bag": "gi:delapouite/backpack",
    "character": "ms:badge",
    "map": "ms:map",
    "quests": "gi:lorc/scroll-unfurled",
    "party": "gi:delapouite/three-friends",
    "friends": "gi:delapouite/shaking-hands",
    "notification": "ms:notifications",
    "tutorial": "ms:school",
    "chat": "ms:chat",
    "wheel": "ms:donut_large",
    "handbook": "gi:lorc/book-cover",
    "coop": "gi:delapouite/team-upgrade",
    "wish": "ms:auto_awesome",
    "battlepass": "gi:delapouite/ticket",
    "events": "gi:delapouite/calendar",
    "teapot": "gi:delapouite/house",
}

# The F-key area AoE2 measured (see the CS2 SOURCES.md).
SIZES = {s: (34, 40) for s in ("handbook", "coop", "wish", "battlepass", "events", "teapot")}
INK = {"chat": (34, 34), "character": (36, 34), "bag": (34, 40),
       "events": (32, 36)}


def main() -> int:
    return game_set.build(Path(__file__).resolve().parent / "icons", ICONS, sizes=SIZES, ink=INK,
                          mark="GENSHIN")


if __name__ == "__main__":
    raise SystemExit(main())
