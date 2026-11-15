#!/usr/bin/env python3
"""Fetch + render the KeeperFX icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0) and
game-icons.net (CC BY 3.0), drawn with the functions of the Beyond All Reason
set. Drawn here: the map bookmarks (a pin with the number cut out), the quick
messages (a speech bubble with the number cut out) and the frame skip keys (a
plus or a minus). SOURCES.md credits each. The ESC mark is "Keeper" over "FX"
set in Almendra Bold (SIL OFL 1.1); the game's own icon and the Dungeon Keeper art
are not used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/keeperfx/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.beyond_all_reason import fetch_icons as bar  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Camera
    "moveup": "fa:arrow-up",
    "movedown": "fa:arrow-down",
    "moveleft": "fa:arrow-left",
    "moveright": "fa:arrow-right",
    "rotatecw": "fa:arrow-rotate-right",
    "rotateccw": "fa:arrow-rotate-left",
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "tiltup": "fa:angle-up",
    "tiltdown": "fa:angle-down",
    "tiltreset": "fa:compass",
    # Go to a room
    "treasure": "fa:coins",
    "library": "fa:book",
    "lair": "fa:bed",
    "prison": "fa:dungeon",
    "torture": "fa:handcuffs",
    "training": "fa:dumbbell",
    "heart": "fa:heart",
    "workshop": "gi:lorc/anvil",
    "scavenger": "fa:eye",
    "temple": "fa:place-of-worship",
    "graveyard": "fa:cross",
    "barracks": "gi:delapouite/barracks",
    "hatchery": "gi:delapouite/chicken",
    "guardpost": "fa:flag",
    "bridge": "fa:bridge",
    "portal": "fa:door-open",
    # Go to creatures
    "fight": "gi:lorc/crossed-swords",
    "annoyed": "fa:face-angry",
    # Panel tabs (1 to 5)
    "tabinfo": "fa:circle-info",
    "tabrooms": "fa:table-cells-large",
    "tabspells": "fa:wand-magic-sparkles",
    "tabworkshop": "fa:door-closed",
    "tabcreatures": "fa:spider",
    # Hand and creatures
    "query": "fa:circle-question",
    "undopickup": "fa:rotate-left",
    "ascend": "fa:angles-up",
    "descend": "fa:angles-down",
    "teleportwork": "fa:briefcase",
    "teleportarms": "fa:bullhorn",
    "teleportlair": "fa:house",
    # Game and display
    "pause": "fa:pause",
    "map": "fa:map",
    "chat": "gi:delapouite/chat-bubble",
    "finishlevel": "fa:flag-checkered",
    "tooltips": "fa:comment-dots",
    "console": "fa:terminal",
    "togglegui": "fa:eye-slash",
    "record": "fa:video",
    "screenshot": "fa:camera",
    "resolution": "fa:display",
    "healthflowers": "fa:heart-pulse",
    "exit": "fa:power-off",
}

# Ctrl+= and Ctrl+- (frame skip): drawn by bar.plus_minus().
PLUS_MINUS = {"_skip": ("fa:forward", "frameskipup", "frameskipdown")}

# The map bookmarks (Shift+1 to 5 go to, Ctrl+1 to 5 store) and the quick
# messages (Ctrl+F1 to F8).
PIN = "fa:location-dot"
BOOKMARKS = (1, 2, 3, 4, 5)
BUBBLE = "fa:comment"
MESSAGES = (1, 2, 3, 4, 5, 6, 7, 8)

# Key area of each icon, from keeperfx.yaml; the default is 40 x 40.
SIZES = {"tooltips": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"heart": (34, 34), "chat": (34, 34), "tooltips": (30, 30), "pause": (26, 30),
       "tabinfo": (32, 32), "query": (32, 32), "annoyed": (32, 32), "tiltreset": (32, 32),
       "screenshot": (30, 30), "exit": (32, 32), "zoomin": (32, 32), "zoomout": (32, 32),
       "tabrooms": (32, 32), "teleportwork": (34, 34), "teleportlair": (34, 34),
       "library": (30, 34), "graveyard": (30, 36), "tabworkshop": (30, 36), "tiltup": (30, 30), "tiltdown": (30, 30)}

# The ESC mark is set in Almendra Bold (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/almendra/Almendra-Bold.ttf")
MARK_LINES = ("Keeper", "FX")
MARK_THRESHOLD = 90         # grey level (0..255) from which a pixel is lit


def messages(out: Path) -> None:
    """message<N>.png (Ctrl+F1 to F8): the speech bubble with N cut out of it,
    in a 34 x 40 area. The digit is centred on the bubble without its tail (the
    top 80 % of its height)."""
    import numpy as np
    for n in MESSAGES:
        bubble = bar._placed(out / "_bubble.png", (34, 40), (34, 32))
        ys, xs = np.nonzero(bubble)
        g = zeroad._digit(str(n), 13)
        cy = ys.min() + round((ys.max() - ys.min()) * 0.4)
        cx = (xs.min() + xs.max() + 1) // 2
        y0, x0 = cy - g.shape[0] // 2, cx - g.shape[1] // 2
        bubble[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] &= ~g
        cnc._save_mask(bubble, out / f"message{n}.png")
    print(f"  message<N>.png  <- {BUBBLE} with 1 to {MESSAGES[-1]}")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    parts = {"_pin": PIN, "_bubble": BUBBLE,
             **{base: row[0] for base, row in PLUS_MINUS.items()}}
    cnc.render({**ICONS, **parts}, out)
    bar.flat(ICONS, SIZES, INK, out)
    bar.plus_minus(PLUS_MINUS, out)
    bar.numbered_pins(out / "_pin.png", BOOKMARKS, "bookmark", "bookmarkset", out)
    messages(out)
    for stem in parts:
        (out / f"{stem}.png").unlink()
    bar.wordmark(MARK_LINES, FONT_URL, out, MARK_THRESHOLD)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
