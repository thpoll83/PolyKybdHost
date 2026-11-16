#!/usr/bin/env python3
"""Fetch + render the Apex Legends icons (reproducible).

Flat 1-bit silhouettes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and Material Symbols (Apache-2.0), drawn by `game_set.py`. The ESC
mark sets the wordmark APEX over a small LEGENDS between two dashes, in Bebas
Neue (SIL OFL 1.1); Respawn's logo art is not used.

    PYTHONPATH=. python polyhost/res/overlay_sources/apex/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_set  # noqa: E402

ICONS = {
    # Movement
    "forward": "ms:arrow_upward",
    "left": "ms:arrow_back",
    "back": "ms:arrow_downward",
    "right": "ms:arrow_forward",
    # Weapons and abilities
    "src_weapon": "gi:john-colburn/pistol-gun",   # only drawn with its number
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
       "inventory": (34, 40), "battery": (30, 40), "cell": (32, 38),
       "forward": (30, 34), "back": (30, 34), "left": (34, 30), "right": (34, 30)}
NUMBERED = {"weapon1": ("src_weapon", "1"), "weapon2": ("src_weapon", "2")}


def program(path: Path) -> None:
    """program.png: APEX, and LEGENDS between two dashes under it. Left as it is when the PNG exists."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    im, d, P = game_set.mark_canvas()
    ss = game_set.MARK_SS
    bebas = game_set.bebas()
    game_set.fit_text(d, "APEX", (8, 0, 64, 29), bebas)
    game_set.fit_text(d, "LEGENDS", (20, 32, 52, 39), bebas)
    d.line(P((8, 35.5), (17, 35.5)), fill=255, width=ss)
    d.line(P((55, 35.5), (64, 35.5)), fill=255, width=ss)
    game_set.save_mark(im, path)
    print(f"  {path.name}  <- APEX LEGENDS wordmark")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_set.build(out, ICONS, sizes=SIZES, ink=INK, numbered=NUMBERED, mark=None)
    program(out / "program.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
