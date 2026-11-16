#!/usr/bin/env python3
"""Fetch + render the Path of Exile 1 and 2 icons (reproducible).

One icon folder for both games (`poe.yaml`, `poe2.yaml`). Flat 1-bit
silhouettes from game-icons.net (CC BY 3.0, credit per author in SOURCES.md)
and Material Symbols (Apache-2.0), drawn by `game_set.py`. The skill slot
keys get their slot number drawn in. The ESC marks are drawn here to resemble
the games' winged crests: EXILE in Bebas Neue (SIL OFL 1.1) between two wings,
an arch above and a point below; Path of Exile 2 adds two horns and three
fangs. Grinding Gear Games' logo art is not used. A mark is written only when
its PNG is missing.

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


def crest(path: Path, two: bool) -> None:
    """program.png (two=False) or program2.png: the crest on the 72x40 cell."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    im, d, P = game_set.mark_canvas()
    ss = game_set.MARK_SS
    game_set.fit_text(d, "EXILE", (17, 11, 55, 29), game_set.bebas())
    d.arc(P((25, 1), (47, 21)), 185, 355, fill=255, width=int(2.2 * ss))
    d.line(P((18, 9.5), (54, 9.5)), fill=255, width=int(1.6 * ss))
    d.line(P((18, 30.5), (54, 30.5)), fill=255, width=int(1.6 * ss))
    if two:
        d.polygon(P((19, 9), (14, 0), (24, 8)), fill=255)
        d.polygon(P((53, 9), (58, 0), (48, 8)), fill=255)
        for x in (31, 36, 41):
            d.polygon(P((x - 2.5, 31), (x, 39), (x + 2.5, 31)), fill=255)
    else:
        d.polygon(P((31, 31), (36, 39), (41, 31)), fill=255)
    # Three feathers on each side, sweeping out and up.
    for x, s in ((16, -1), (56, 1)):
        for dy, length, thick in ((0, 15, 3.2), (5, 13, 3), (10, 10, 2.8)):
            y = 12 + dy
            d.polygon(P((x, y), (x + s * length, y - 4), (x + s * (length - 1), y - 4 + thick),
                        (x, y + thick)), fill=255)
    game_set.save_mark(im, path)
    print(f"  {path.name}  <- drawn crest")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_set.build(out, ICONS, sizes=SIZES, ink=INK, numbered=NUMBERED, mark=None)
    crest(out / "program.png", two=False)
    crest(out / "program2.png", two=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
