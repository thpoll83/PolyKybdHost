#!/usr/bin/env python3
"""Fetch + render the DevilutionX icons (reproducible).

The key icons are flat silhouettes from game-icons.net (CC BY 3.0) and Font
Awesome Free (CC BY 4.0), as in the Warcraft III set. The gamma keys add a
plus or a minus to a sun. SOURCES.md credits each. The ESC mark is
"Devilution" over a large "X" set in New Rocker (SIL OFL 1.1); the game's logo
art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/devilutionx/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402

ICONS = {
    # Belt and spells
    "belt": "gi:lorc/round-bottom-flask",
    "quickspell": "gi:lorc/fire-ray",
    "speedbook": "gi:lorc/magic-palm",
    "spellbook": "gi:lorc/book-aura",
    # Panels
    "inventory": "gi:lorc/knapsack",
    "character": "gi:delapouite/skills",
    "questlog": "gi:lorc/scroll-unfurled",
    "automap": "fa:map",
    "closepanels": "fa:rectangle-xmark",
    "chatlog": "gi:delapouite/notebook",
    "gameinfo": "fa:circle-info",
    "help": "fa:circle-question",
    # View
    "zoom": "fa:magnifying-glass",
    "mapzoomin": "fa:magnifying-glass-plus",
    "mapzoomout": "fa:magnifying-glass-minus",
    "highlight": "fa:tags",
    "fullscreen": "fa:expand",
    "screenshot": "fa:camera",
    # Game
    "pause": "fa:pause",
    "save": "fa:floppy-disk",
    "load": "fa:folder-open",
    # Chat and the four default quick messages
    "chat": "gi:delapouite/chat-bubble",
    "msghelp": "fa:hand",
    "msgfollow": "gi:lorc/footprint",
    "msggift": "gi:delapouite/present",
    "msgdie": "gi:lorc/skull-crossed-bones",
}
# F1 to F8: the key area that keeps the F-key legend whole, as for Warcraft III.
SIZES = {stem: (34, 40) for stem in ("help", "save", "load", "quickspell")}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"save": (30, 30), "load": (30, 30), "help": (30, 30), "gameinfo": (34, 34),
       "closepanels": (34, 34), "pause": (30, 30), "chat": (34, 34), "msghelp": (34, 34),
       "screenshot": (30, 30), "zoom": (30, 30), "mapzoomin": (30, 30),
       "mapzoomout": (30, 30), "highlight": (34, 34), "fullscreen": (30, 30)}

# G and F (gamma down and up): a sun with a minus or a plus.
SUN = "fa:sun"
SIGN = 13           # size of the plus or minus
SIGN_BAR = 3        # its stroke width
SIGN_SEAM = 3       # unlit pixels between the sign and the sun

# The ESC mark is set in New Rocker (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/newrocker/NewRocker-Regular.ttf")
MARK_SS = 8                 # supersampling factor for the ESC mark
MARK_THRESHOLD = 110        # grey level (0..255) from which a box-filtered pixel is lit
MARK_GAP = 2                # px between the two lines
MARK_X_SCALE = 2.0          # the X is this many times the size of "Devilution"


def _fit(stem: str, out: Path, size, box):
    """The icon's ink scaled into `box`, in the bottom-right corner of a `size` canvas."""
    import numpy as np
    from PIL import Image
    alpha = Image.open(out / f"{stem}.png").convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    scale = min(box[0] / alpha.width, box[1] / alpha.height)
    alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                         Image.LANCZOS)
    m = np.asarray(alpha) > 150
    canvas = np.zeros((size[1], size[0]), bool)
    canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
    return canvas


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key area
    so the generator places it 1:1. The icons in INK fill a smaller box in the
    bottom-right corner of that area."""
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        cnc._save_mask(_fit(stem, out, size, INK.get(stem, size)), out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def gamma_icons(out: Path) -> None:
    """gammaup.png (F) and gammadown.png (G): the sun in a 34x34 box at the top
    left, and a plus or a minus at the bottom right, SIGN_SEAM px clear of it."""
    import numpy as np
    sun = np.zeros((40, 40), bool)
    sun[:34, :34] = _fit("_sun", out, (34, 34), (34, 34))
    cy, cx = 40 - SIGN // 2 - 1, 40 - SIGN // 2 - 1
    for stem, plus in (("gammaup", True), ("gammadown", False)):
        p = np.zeros((40, 40), bool)
        p[cy - SIGN_BAR // 2:cy + SIGN_BAR // 2 + 1, cx - SIGN // 2:cx + SIGN // 2 + 1] = True
        if plus:
            p[cy - SIGN // 2:cy + SIGN // 2 + 1, cx - SIGN_BAR // 2:cx + SIGN_BAR // 2 + 1] = True
        ring = np.zeros((40, 40), bool)
        ring[cy - SIGN // 2:cy + SIGN // 2 + 1, cx - SIGN // 2:cx + SIGN // 2 + 1] = True
        mask = (sun & ~program_mark.dilate(ring, SIGN_SEAM)) | p
        cnc._save_mask(mask, out / f"{stem}.png")
    print(f"  gammaup.png, gammadown.png  <- {SUN} + a plus or a minus")


def _mark_font(px: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(cnc._font(FONT_URL)), px)


def program(out: Path) -> None:
    """program.png: "Devilution" at the largest size that fits 70 px wide, over an
    X MARK_X_SCALE times as large, centred on the whole 72x40 cell. Drawn at
    MARK_SS times the size and box-filtered down."""
    import numpy as np
    from PIL import Image, ImageDraw
    w, h, ss = program_mark.W, program_mark.H, MARK_SS
    gap = MARK_GAP * ss
    for cap in range(16, 5, -1):
        ref = _mark_font(200).getbbox("H")
        px = round(200 * cap * ss / (ref[3] - ref[1]))
        top, bottom = _mark_font(px), _mark_font(round(px * MARK_X_SCALE))
        tb, bb = top.getbbox("Devilution"), bottom.getbbox("X")
        height = (tb[3] - tb[1]) + gap + (bb[3] - bb[1])
        if tb[2] - tb[0] <= (w - 2) * ss and height <= h * ss:
            break
    y = (h * ss - height) // 2
    canvas = np.zeros((h, w), bool)
    for text, font, box in (("Devilution", top, tb), ("X", bottom, bb)):
        im = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(im).text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                                text, font=font, fill=255)
        canvas |= np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD
        y += box[3] - box[1] + gap
    cnc._save_mask(canvas, out / "program.png")
    print(f"  program.png  <- Devilution X (New Rocker, cap {cap} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, "_sun": SUN}, out)
    flat_icons(out)
    gamma_icons(out)
    (out / "_sun.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
