#!/usr/bin/env python3
"""Fetch + render the Apex Legends icons (reproducible).

Flat 1-bit silhouettes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and Material Symbols (Apache-2.0), drawn by `game_set.py`. The ESC
mark is APEX in Bebas Neue (SIL OFL 1.1); Respawn's logo art is not used.

    PYTHONPATH=. python polyhost/res/overlay_sources/apex/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_set  # noqa: E402

ICONS = {
    # Weapons and abilities
    "weapon": "gi:john-colburn/pistol-gun",
    "holster": "ms:back_hand",
    "tactical": "gi:lorc/lightning-helix",
    "ultimate": "gi:lorc/burning-meteor",
    "grenade": "gi:lorc/grenade",
    "fireselect": "ms:repeat",
    "reload": "ms:autorenew",
    "melee": "gi:lorc/punch",
    "inspect": "ms:visibility",
    "jump": "gi:delapouite/jump-across",
    "crouch": "ms:keyboard_double_arrow_down",
    # Healing items
    "heal": "ms:healing",
    "syringe": "gi:lorc/syringe",
    "medkit": "ms:medical_services",
    "cell": "ms:shield",
    "battery": "ms:battery_full",
    "phoenix": "ms:local_fire_department",
    # Interface
    "interact": "ms:touch_app",
    "inventory": "ms:backpack",
    "map": "ms:map",
    "pushtotalk": "ms:mic",
    "chat": "ms:chat",
    "screenshot": "ms:screenshot_monitor",
}

SIZES = {"screenshot": (34, 40)}
INK = {"chat": (34, 34), "medkit": (36, 36), "heal": (36, 36), "grenade": (34, 40),
       "inventory": (34, 40), "battery": (30, 40), "cell": (32, 38), "weapon": (40, 32)}


def main() -> int:
    return game_set.build(Path(__file__).resolve().parent / "icons", ICONS, sizes=SIZES, ink=INK,
                          mark="APEX")


if __name__ == "__main__":
    raise SystemExit(main())
