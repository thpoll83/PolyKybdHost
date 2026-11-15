#!/usr/bin/env python3
"""Fetch + render the Mindustry icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0),
game-icons.net (CC BY 3.0) and Material Design Icons (Apache-2.0), as in the
fheroes2 set. The digits are a filled block (block selection), a shield (control
group) and a shield with a plus (create control group), each with the number cut
out. SOURCES.md credits each. The ESC mark is the game's own window icon
(GPL-3.0), reduced to 1 bit.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/mindustry/fetch_icons.py

program.png is kept when it already exists, so a hand edit survives a re-run.
Delete it to draw it again.

flat_icons(), numbered() and with_sign() are also used by the Veloren, OpenMW
and OpenXcom sets.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.devilutionx import fetch_icons as dx  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Movement and the player's unit
    "forward": "fa:arrow-up",
    "left": "fa:arrow-left",
    "back": "fa:arrow-down",
    "right": "fa:arrow-right",
    "command": "gi:lorc/rally-the-troops",
    "control": "fa:gamepad",
    "respawn": "fa:heart-pulse",
    "pickup": "fa:upload",
    "dropcargo": "fa:download",
    # Building
    "clearbuilding": "fa:eraser",
    "pausebuilding": "fa:circle-pause",
    "rotate": "fa:rotate",
    "rebuild": "fa:hammer",
    "schematic": "fa:vector-square",
    "flipx": "mdi:flip-horizontal",
    "flipy": "mdi:flip-vertical",
    "schematics": "mdi:floor-plan",
    "categoryprev": "fa:angles-left",
    "categorynext": "fa:angles-right",
    "blockinfo": "fa:circle-info",
    # Units
    "allunits": "fa:robot",
    "factories": "fa:industry",
    "ping": "fa:location-crosshairs",
    # View and game
    "pause": "fa:pause",
    "minimap": "fa:map",
    "research": "fa:sitemap",
    "planetmap": "fa:globe",
    "togglemenus": "fa:eye-slash",
    "powerlines": "fa:bolt",
    "blockstatus": "fa:traffic-light",
    "fullscreen": "fa:expand",
    "screenshot": "fa:camera",
    # Multiplayer
    "playerlist": "fa:users",
    "chat": "gi:delapouite/chat-bubble",
    "console": "fa:terminal",
}
# Parts of the numbered digit icons, drawn by digit_icons().
PARTS = {"_block": "fa:square", "_shield": "fa:shield"}

# Key area of each icon, from mindustry.yaml; the default is 40 x 40. The narrow
# ones keep the key's own legend whole (widths measured for AoE2, see
# ../aoe2/SOURCES.md, Placement).
SIZES = {"blockinfo": (34, 40), "powerlines": (34, 40), "blockstatus": (34, 40),
         "console": (34, 40), "command": (34, 40), "control": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box at the
# bottom right of their key area.
INK = {"forward": (30, 36), "back": (30, 36), "left": (36, 30), "right": (36, 30),
       "blockinfo": (30, 30), "pausebuilding": (32, 32), "pause": (28, 30),
       "screenshot": (30, 30), "fullscreen": (30, 30), "chat": (34, 34),
       "playerlist": (38, 30), "planetmap": (32, 32), "ping": (34, 34),
       "control": (34, 24), "powerlines": (26, 34), "blockstatus": (20, 36),
       "console": (32, 28), "pickup": (32, 32), "dropcargo": (32, 32),
       "rotate": (32, 32), "factories": (36, 32), "minimap": (38, 32),
       "clearbuilding": (36, 32), "allunits": (38, 30), "research": (38, 30),
       "togglemenus": (40, 32), "respawn": (36, 32), "schematic": (32, 32)}

SLOTS = range(1, 11)       # the keys 1 to 9 and 0 (slot 10)
DIGIT_MARGIN = 5           # lit px kept above and below a cut-out digit

# The ESC mark: the game's window icon (core/assets/icons/icon.png, 256 x 256).
MARK_URL = ("https://raw.githubusercontent.com/Anuken/Mindustry/"
            "17012d61d9e4c3cbd9820d87e81c24495486ac53/core/assets/icons/icon.png")
MARK_SIZE = 40
MARK_LUMA = 130            # pixels lighter than this are lit


def flat_icons(out: Path, icons, sizes, ink) -> None:
    """Every icon of `icons` as a flat 1-bit silhouette, drawn at exactly its key
    area (`sizes`, default 40 x 40) so the generator places it 1:1. The icons in
    `ink` fill a smaller box in the bottom-right corner of that area."""
    for stem in icons:
        size = sizes.get(stem, (40, 40))
        cnc._save_mask(dx._fit(stem, out, size, ink.get(stem, size)), out / f"{stem}.png")
    print(f"  {len(icons)} key icons drawn flat")


def numbered(mask, text: str, margin: int = DIGIT_MARGIN):
    """`mask` with `text` cut out of its largest lit area, centred on that area
    and leaving `margin` lit px above and below."""
    import numpy as np
    ys, xs = np.nonzero(dx._largest_area(mask))
    height = ys.max() + 1 - ys.min() - 2 * margin
    g = zeroad._digit(text, height)
    width = xs.max() + 1 - xs.min() - 4
    while g.shape[1] > width:
        height -= 1
        g = zeroad._digit(text, height)
    cy, cx = (ys.min() + ys.max() + 1) // 2, (xs.min() + xs.max() + 1) // 2
    m = mask.copy()
    y0, x0 = cy - g.shape[0] // 2, cx - g.shape[1] // 2
    m[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] &= ~g
    return m


def with_sign(mask, plus: bool, size: int = 13, bar: int = 3, seam: int = 3):
    """`mask` with a plus or a minus in its bottom-right corner, `seam` unlit px
    clear of the rest."""
    import numpy as np
    h, w = mask.shape
    cy, cx = h - size // 2 - 1, w - size // 2 - 1
    p = np.zeros_like(mask)
    p[cy - bar // 2:cy + bar // 2 + 1, cx - size // 2:cx + size // 2 + 1] = True
    if plus:
        p[cy - size // 2:cy + size // 2 + 1, cx - bar // 2:cx + bar // 2 + 1] = True
    box = np.zeros_like(mask)
    box[cy - size // 2:cy + size // 2 + 1, cx - size // 2:cx + size // 2 + 1] = True
    return (mask & ~program_mark.dilate(box, seam)) | p


def digit_icons(out: Path) -> None:
    """block<N>.png: a filled block with N cut out (select block N).
    group<N>.png: a shield with N cut out (control group N).
    newgroup<N>.png: the same shield, smaller, with a plus (create group N).
    The groups show the digit of their key, so group 10 shows 0."""
    import numpy as np
    block = dx._fit("_block", out, (40, 40), (34, 34))
    shield = dx._fit("_shield", out, (40, 40), (38, 40))
    small = np.zeros((40, 40), bool)
    small[:34, :34] = dx._fit("_shield", out, (34, 34), (34, 34))
    for n in SLOTS:
        cnc._save_mask(numbered(block, str(n)), out / f"block{n}.png")
        cnc._save_mask(numbered(shield, str(n % 10), 8), out / f"group{n}.png")
        cnc._save_mask(with_sign(numbered(small, str(n % 10), 7), True), out / f"newgroup{n}.png")
    print(f"  block, group, newgroup 1..{SLOTS[-1]}  <- numbered")


def program(out: Path) -> None:
    """program.png: the game's window icon, box-filtered to MARK_SIZE px and cut
    at MARK_LUMA. The light tile and the light parts of the core are lit."""
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
    print("  program.png  <- core/assets/icons/icon.png (Mindustry, GPL-3.0)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    flat_icons(out, ICONS, SIZES, INK)
    digit_icons(out)
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
