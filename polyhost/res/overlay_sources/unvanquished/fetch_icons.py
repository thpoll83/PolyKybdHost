#!/usr/bin/env python3
"""Fetch + render the Unvanquished icons (reproducible).

The key icons are flat 1-bit silhouettes, as in the Xonotic set: game shapes
from game-icons.net (CC BY 3.0, credit per author in SOURCES.md) and interface
shapes from Material Symbols (Apache-2.0). The two team vote keys get a T
drawn here. The ESC mark is the game's name set in Bebas Neue (SIL OFL 1.1);
the game's logo art is CC BY-SA 2.5 and is not used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/unvanquished/fetch_icons.py

The fetched icons are re-rendered on every run. The drawn icons (the team vote
keys, the ESC mark) are written only when their PNG is missing, so a hand edit
to a committed PNG is kept.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.factorio import fetch_icons as fac  # noqa: E402
from polyhost.res.overlay_sources.xonotic import fetch_icons as xon  # noqa: E402

ICONS = {
    # Movement
    "forward": "ms:arrow_upward",
    "back": "ms:arrow_downward",
    "left": "ms:arrow_back",
    "right": "ms:arrow_forward",
    "jump": "gi:delapouite/jump-across",
    "centerview": "ms:center_focus_strong",
    # Actions
    "activate": "ms:touch_app",
    "deconstruct": "gi:lorc/wrecking-ball",
    "taunt": "gi:lorc/shouting",
    # Menus
    "vsay": "gi:delapouite/megaphone",
    "beacon": "gi:delapouite/lighthouse",
    "bottactic": "ms:smart_toy",
    # Chat
    "chat": "ms:public",
    "teamchat": "ms:chat",
    "adminchat": "ms:shield_person",
    # Spectating
    "follow": "ms:videocam",
    "followprev": "ms:skip_previous",
    "follownext": "ms:skip_next",
    # Client
    "pause": "ms:pause",
    "console": "ms:terminal",
    "scoreboard": "ms:scoreboard",
    "voteyes": "ms:thumb_up",
    "voteno": "ms:thumb_down",
    "screenshot": "ms:screenshot_monitor",
}

# Key area of each icon, from unvanquished.yaml; the default is 40 x 40.
SIZES = {"voteyes": xon.F_KEY, "voteno": xon.F_KEY, "screenshot": xon.F_KEY_WIDE}
# Solid or wide icons that read heavier than the rest: drawn in a smaller box at
# the bottom right of their key area.
INK = {"forward": (30, 30), "back": (30, 30), "left": (30, 30), "right": (30, 30),
       "chat": (34, 34), "teamchat": (34, 34), "adminchat": (34, 34),
       "scoreboard": (40, 34), "pause": (30, 30), "voteyes": (32, 32), "voteno": (32, 32),
       "deconstruct": (36, 36), "centerview": (34, 34), "followprev": (32, 32),
       "follownext": (32, 32), "bottactic": (36, 36)}

# F3 and F4 (team vote yes / no): the thumb of F1 / F2, smaller, with a T.
TEAM_VOTES = {"teamvoteyes": "voteyes", "teamvoteno": "voteno"}
TEAM_BOX = (28, 28)         # the thumb, at the bottom right of the 34 x 40 area
TEAM_LETTER_PX = 12         # height of the T in the top-left corner of the area

# One line of 12 letters fits only at 15 px, where the letters touch.
MARK_LINES = ("UNVAN", "QUISHED")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    fac.render(ICONS, out)
    for stem, src in TEAM_VOTES.items():
        xon.lettered(out / f"{src}.png", "T", out / f"{stem}.png", xon.F_KEY,
                     TEAM_BOX, TEAM_LETTER_PX)
    xon.flat_icons(ICONS, SIZES, INK, out)
    xon.text_mark(MARK_LINES, fac.MARK_FONT_URL, out / "program.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
