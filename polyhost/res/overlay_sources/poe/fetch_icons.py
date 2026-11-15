#!/usr/bin/env python3
"""Fetch + render the Path of Exile 1 and 2 icons (reproducible).

One icon folder for both games (`poe.yaml`, `poe2.yaml`). Flat 1-bit
silhouettes from game-icons.net (CC BY 3.0, credit per author in SOURCES.md)
and Material Symbols (Apache-2.0), drawn by `game_set.py`. The skill slot
keys get their slot number drawn in. The ESC marks are POE and POE2 in Bebas
Neue (SIL OFL 1.1); Grinding Gear Games' logo art is not used.

    PYTHONPATH=. python polyhost/res/overlay_sources/poe/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_set  # noqa: E402

ICONS = {
    # Skills and flasks
    "src_skill": "gi:lorc/magic-swirl",        # only drawn with its slot number
    "flask": "gi:lorc/round-bottom-flask",
    "tempskill": "gi:lorc/hourglass",
    "weaponswap": "gi:lorc/crossed-swords",
    "dodge": "gi:lorc/dodging",
    "mines": "gi:lorc/land-mine",
    "minions": "ms:pets",
    "pickup": "gi:lorc/hand",
    "labels": "ms:label",
    # Panels
    "inventory": "ms:backpack",
    "character": "ms:badge",
    "skills": "gi:delapouite/spell-book",
    "passives": "ms:hub",
    "atlas": "gi:lorc/world",
    "atlaspassives": "ms:account_tree",
    "world": "ms:explore",
    "social": "gi:delapouite/three-friends",
    "ladder": "ms:leaderboard",
    "challenges": "gi:delapouite/trophy-cup",
    "pantheon": "gi:delapouite/greek-temple",
    "cosmetics": "gi:delapouite/t-shirt",
    "mtxstash": "ms:inventory_2",
    "shop": "gi:delapouite/shop",
    "events": "gi:delapouite/calendar",
    "options": "ms:settings",
    "guidebook": "ms:menu_book",
    "market": "ms:currency_exchange",
    "league": "ms:auto_awesome",
    "leaguepanel": "ms:dashboard",
    # Interface
    "map": "ms:map",
    "close": "ms:close",
    "chat": "ms:chat",
    "zoomin": "ms:zoom_in",
    "zoomout": "ms:zoom_out",
    "performance": "ms:monitoring",
    "screenshot": "ms:screenshot_monitor",
}

SIZES = {"performance": (34, 40), "screenshot": (34, 40)}
INK = {"chat": (34, 34), "inventory": (34, 40), "close": (30, 30), "mtxstash": (34, 34),
       "events": (32, 36), "character": (36, 34), "options": (34, 34), "flask": (34, 40),
       "ladder": (36, 32)}
# Skill slots 4 to 8 (Q W E R T) and 9 to 13 (Ctrl+Q to Ctrl+T).
NUMBERED = {f"skill{n}": ("src_skill", str(n), (24, 24)) for n in range(4, 14)}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_set.build(out, ICONS, sizes=SIZES, ink=INK, numbered=NUMBERED, mark="POE")
    game_set.text_mark(out / "program2.png", "POE2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
