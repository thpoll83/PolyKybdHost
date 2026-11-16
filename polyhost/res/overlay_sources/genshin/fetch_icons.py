#!/usr/bin/env python3
"""Fetch + render the Genshin Impact icons (reproducible).

Flat 1-bit silhouettes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and Material Symbols (Apache-2.0), drawn by `game_set.py`. The ESC
mark sets the wordmark GENSHIN / IMPACT in Marcellus (SIL OFL 1.1), a serif
close to the logo's lettering; HoYoverse's logo art is not used.

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
    "src_member": "gi:delapouite/person",   # only drawn with its number
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
# Party members 1 to 4, and Alt+1 to 4: switch to that member and cast the burst.
NUMBERED = {f"member{n}": ("src_member", str(n)) for n in range(1, 5)}
NUMBERED.update({f"burst{n}": ("burst", str(n)) for n in range(1, 5)})


def program(path: Path) -> None:
    """program.png: GENSHIN over IMPACT in Marcellus. Left as it is when the PNG exists."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    im, d, P = game_set.mark_canvas()
    marcellus = game_set.google_font(game_set.MARCELLUS)
    # Marcellus is thin; a 3 px stroke (of 8 per keycap pixel) keeps every stem lit.
    game_set.fit_text(d, "GENSHIN", (1, 1, 71, 21), marcellus, stroke=3)
    game_set.fit_text(d, "IMPACT", (10, 24, 62, 39), marcellus, stroke=3)
    game_set.save_mark(im, path)
    print(f"  {path.name}  <- GENSHIN IMPACT wordmark")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_set.build(out, ICONS, sizes=SIZES, ink=INK, numbered=NUMBERED, mark=None)
    program(out / "program.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
