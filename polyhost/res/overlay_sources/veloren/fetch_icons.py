#!/usr/bin/env python3
"""Fetch + render the Veloren icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0),
game-icons.net (CC BY 3.0) and Material Design Icons (Apache-2.0), as in the
fheroes2 set. The hotbar slots are a square frame with the slot number.
SOURCES.md credits each. The ESC mark is the game's own application icon
(GPL-3.0-or-later), reduced to 1 bit.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/veloren/fetch_icons.py

program.png is kept when it already exists, so a hand edit survives a re-run.
Delete it to draw it again.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.mindustry import fetch_icons as mindustry  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Movement
    "forward": "fa:arrow-up",
    "left": "fa:arrow-left",
    "back": "fa:arrow-down",
    "right": "fa:arrow-right",
    "jump": "gi:delapouite/jump-across",
    "sneak": "fa:user-ninja",
    "glide": "gi:lorc/feathered-wing",
    "togglewalk": "fa:person-walking",
    "autowalk": "fa:person-walking-arrow-right",
    "sit": "fa:chair",
    "dance": "mdi:human-female-dance",
    "greet": "mdi:hand-wave",
    # Combat and interaction
    "block": "fa:shield-halved",
    "wield": "gi:lorc/crossed-swords",
    "swaploadout": "fa:right-left",
    "interact": "fa:hand-pointer",
    "select": "fa:bullseye",
    "lantern": "gi:lorc/candle-light",
    "mount": "fa:horse",
    "stayfollow": "fa:paw",
    # Windows
    "map": "fa:map",
    "inventory": "gi:lorc/knapsack",
    "trade": "fa:handshake",
    "social": "fa:user-group",
    "crafting": "fa:hammer",
    "diary": "fa:book-open",
    "settings": "fa:gear",
    "controls": "fa:keyboard",
    # Group invite
    "accept": "fa:user-check",
    "decline": "fa:user-xmark",
    # Camera
    "freelook": "fa:eye",
    "cameraclamp": "fa:lock",
    "cyclecamera": "fa:street-view",
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "mapzoomin": "mdi:map-plus",
    "mapzoomout": "mdi:map-minus",
    # Interface
    "togglecursor": "fa:arrow-pointer",
    "toggleinterface": "fa:eye-slash",
    "toggleingameui": "fa:tags",
    "togglechat": "fa:comment-slash",
    "debug": "fa:bug",
    "screenshot": "fa:camera",
    "fullscreen": "fa:expand",
    "mutemusic": "fa:volume-xmark",
    # Chat
    "chat": "gi:delapouite/chat-bubble",
    "command": "fa:terminal",
}

# Key area of each icon, from veloren.yaml; the default is 40 x 40. The narrow
# ones keep the key's own legend whole (widths measured for AoE2, see
# ../aoe2/SOURCES.md, Placement).
SIZES = {"controls": (34, 40), "toggleinterface": (34, 40), "togglechat": (34, 40),
         "toggleingameui": (34, 40), "mutemusic": (34, 40), "screenshot": (30, 40),
         "sneak": (34, 40), "glide": (34, 40), "block": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box at the
# bottom right of their key area.
INK = {"forward": (30, 36), "back": (30, 36), "left": (36, 30), "right": (36, 30),
       "screenshot": (30, 30), "fullscreen": (30, 30), "chat": (34, 34),
       "settings": (32, 32), "controls": (34, 26), "debug": (34, 34),
       "select": (32, 32), "block": (30, 34), "map": (38, 32), "social": (38, 30),
       "trade": (40, 30), "diary": (38, 30), "cameraclamp": (28, 34),
       "freelook": (38, 28), "toggleinterface": (34, 28), "togglechat": (34, 28),
       "toggleingameui": (32, 32), "mutemusic": (34, 28), "accept": (38, 30),
       "decline": (38, 30), "swaploadout": (34, 34), "stayfollow": (34, 34),
       "zoomin": (32, 32), "zoomout": (32, 32), "togglecursor": (24, 34),
       "interact": (30, 36), "command": (36, 30), "sit": (30, 34)}

SLOTS = range(1, 11)   # 1 to 9 and Q (slot 10)
FRAME = 36             # the slot frame, square
FRAME_BORDER = 3       # px
FRAME_DIGIT = 20       # digit height

# The ESC mark: the game's application icon (256 x 256).
MARK_URL = ("https://raw.githubusercontent.com/veloren/veloren/"
            "b2f1060df37ba4eb2eb001ac1b115beaf404f656/assets/voxygen/net.veloren.veloren.png")
MARK_SIZE = 40
MARK_LUMA = 130        # pixels lighter than this are lit


def frame_digit(text: str, size: int = FRAME, border: int = FRAME_BORDER,
                height: int = FRAME_DIGIT):
    """A 40 x 40 mask: a square frame of `size` px in the bottom-right corner
    with `text` lit inside it. Also used by the OpenMW set."""
    import numpy as np
    c = np.zeros((40, 40), bool)
    f = np.ones((size, size), bool)
    f[border:-border, border:-border] = False
    for y, x in ((0, 0), (0, -1), (-1, 0), (-1, -1)):   # rounded corners
        f[y, x] = False
    g = zeroad._digit(text, height)
    while g.shape[1] > size - 2 * border - 4:
        height -= 1
        g = zeroad._digit(text, height)
    y, x = (size - g.shape[0]) // 2, (size - g.shape[1]) // 2
    f[y:y + g.shape[0], x:x + g.shape[1]] |= g
    c[40 - size:, 40 - size:] = f
    return c


def slots(out: Path) -> None:
    """slot1.png .. slot10.png: the frame with the slot number."""
    for n in SLOTS:
        cnc._save_mask(frame_digit(str(n)), out / f"slot{n}.png")
    print(f"  slot1..{SLOTS[-1]}.png  <- frame + number")


def program(out: Path) -> None:
    """program.png: the game's application icon, box-filtered to MARK_SIZE px
    and cut at MARK_LUMA: the V and the rim of the tile are lit."""
    import numpy as np
    from PIL import Image
    path = out / "program.png"
    if path.exists():
        print("  program.png  <- committed asset (left as-is)")
        return
    im = Image.open(io.BytesIO(cnc._get(MARK_URL))).convert("RGBA")
    bg = Image.new("RGBA", im.size, (0, 0, 0, 255))
    bg.alpha_composite(im)
    grey = bg.convert("L").resize((MARK_SIZE, MARK_SIZE), Image.BOX)
    cnc._save_mask(np.asarray(grey) > MARK_LUMA, path)
    print("  program.png  <- assets/voxygen/net.veloren.veloren.png (Veloren, GPL-3.0-or-later)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render(ICONS, out)
    mindustry.flat_icons(out, ICONS, SIZES, INK)
    slots(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
