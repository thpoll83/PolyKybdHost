#!/usr/bin/env python3
"""Fetch + render the Overwatch 2 icons (reproducible).

Flat 1-bit silhouettes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and Material Symbols (Apache-2.0), drawn by `game_set.py`. The ESC
mark is drawn here to resemble the Overwatch emblem (a ring whose top arc is
cut off, two prongs inside that splay into the lower ring); Blizzard's logo
art is not used. It is written only when program.png is missing.

    PYTHONPATH=. python polyhost/res/overlay_sources/overwatch/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_set  # noqa: E402

ICONS = {
    # Abilities and weapons (the same command for every hero; what it does
    # depends on the hero)
    "ultimate": "gi:lorc/burning-meteor",
    "ability2": "gi:lorc/magic-palm",
    "reload": "ms:autorenew",
    "melee": "gi:lorc/punch",
    "interact": "ms:touch_app",
    "weapon": "gi:john-colburn/pistol-gun",
    "jump": "gi:delapouite/jump-across",
    # Communication
    "ping": "gi:delapouite/position-marker",
    "comms": "gi:delapouite/walkie-talkie",
    "healing": "ms:medical_services",
    "ultstatus": "ms:percent",
    "spray": "gi:lorc/spray",
    "pushtotalk": "ms:mic",
    "mute": "ms:mic_off",
    "chat": "ms:chat",
    # Menus
    "scoreboard": "ms:scoreboard",
    "heroselect": "ms:switch_account",
    "endorse": "gi:delapouite/thumb-up",
    "social": "gi:delapouite/three-friends",
    "highlight": "gi:delapouite/film-projector",
    "screenshot": "ms:screenshot_monitor",
}

SIZES = {"highlight": (34, 40)}
INK = {"chat": (34, 34), "scoreboard": (40, 34), "healing": (36, 36),
       "ultstatus": (34, 34), "weapon": (40, 32)}


def program(path: Path) -> None:
    """program.png: the emblem, 39 px across, centred on the 72x40 cell."""
    import math
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    im, d, P = game_set.mark_canvas()
    ss = game_set.MARK_SS
    cx, cy, outer, inner = 36, 20, 19.5, 14.5

    def box(r):
        return [(cx - r) * ss, (cy - r) * ss, (cx + r) * ss, (cy + r) * ss]
    d.ellipse(box(outer), fill=255)
    d.ellipse(box(inner), fill=0)
    # The two cuts that part the top arc from the lower ring (10:30 and 1:30).
    for deg in (225, 315):
        t = math.radians(deg)
        d.line(P((cx + math.cos(t) * (inner - 1), cy + math.sin(t) * (inner - 1)),
                 (cx + math.cos(t) * (outer + 1), cy + math.sin(t) * (outer + 1))),
               fill=0, width=int(2.8 * ss))
    for k in (-1, 1):
        d.polygon(P((cx + k * 2.4, cy - 11), (cx + k * 7.2, cy - 11), (cx + k * 7.2, cy - 2),
                    (cx + k * 16, cy + 8), (cx + k * 11, cy + 12), (cx + k * 2.4, cy + 2)), fill=255)
    game_set.save_mark(im, path)
    print(f"  {path.name}  <- drawn emblem")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_set.build(out, ICONS, sizes=SIZES, ink=INK, mark=None)
    program(out / "program.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
