#!/usr/bin/env python3
"""Shared steps for a game overlay set whose icons are flat 1-bit silhouettes
and whose ESC mark is the game's short name set in a font.

The Counter-Strike 2 set (`cs2/fetch_icons.py`) does these steps inline. The
sets made after it (Team Fortress 2, Apex Legends, Rocket League, Path of
Exile 1 and 2, Overwatch 2, Genshin Impact) call this module instead:

    from polyhost.res.overlay_sources import game_set
    game_set.build(out, ICONS, sizes=SIZES, ink=INK, mark="TF2")

- `ICONS` is ``{stem: "gi:author/name" | "ms:name"}``: game-icons.net
  (CC BY 3.0, credit per author in the set's SOURCES.md) or Material Symbols
  (Apache-2.0).
- Each icon is drawn at exactly its key area (`sizes`, default 40 x 40), so
  the generator places it 1:1. An icon in `ink` fills that smaller box at the
  bottom right of its area.
- `numbered` is ``{stem: (source stem, digit text[, box])}``: the source
  icon in `box` (default 28 x 40) at the bottom right of a 40 x 40 area,
  with the digits in the top-left corner, as the CS2 radio wheels. A source whose stem starts with ``src_`` is deleted
  afterwards: no key draws it.
- The ESC mark is `mark` in Bebas Neue (SIL OFL 1.1) at the largest size that
  fits 70 x 38 px, centred on the whole 72 x 40 cell. It is written only when
  its PNG is missing, so a hand edit is kept. No game's logo art is used.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.factorio import fetch_icons as fac  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

AREA = (40, 40)
DIGIT_PX = 15          # digit height of a numbered icon, as the CS2 radio wheels
NUMBER_BOX = (28, 40)  # the source icon of a numbered icon, at the right of its area


def flat_icons(out: Path, icons: dict, sizes: dict, ink: dict) -> None:
    """Every fetched icon as a flat 1-bit silhouette at exactly its key area."""
    for stem in icons:
        size = sizes.get(stem, AREA)
        cnc._save_mask(zeroad._flat(out / f"{stem}.png", size, ink.get(stem, size)),
                       out / f"{stem}.png")
    print(f"  {len(icons)} key icons drawn flat")


def numbered_icons(out: Path, numbered: dict) -> None:
    """``{stem: (source stem, text[, box])}``: the source icon with `text` in the
    top-left corner. Returns the source stems."""
    sources = set()
    for stem, (src, text, *box) in numbered.items():
        sources.add(src)
        m = zeroad._flat(out / f"{src}.png", AREA, box[0] if box else NUMBER_BOX)
        d = zeroad._digit(text, DIGIT_PX)
        m[0:d.shape[0], 0:d.shape[1]] |= d
        cnc._save_mask(m, out / f"{stem}.png")
        print(f"  {stem}.png  <- {src} + {text}")
    return sources


def text_mark(path: Path, text: str) -> None:
    """`text` in Bebas Neue at the largest size that fits 70 x 38 px, centred
    on the whole 72 x 40 cell. Left as it is when the PNG exists."""
    if not fac._missing(path):
        return
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font_path = cnc._font(fac.MARK_FONT_URL)
    w, h, ss = 72, 40, fac.MARK_SS
    for px in range(400, 40, -4):
        font = ImageFont.truetype(str(font_path), px)
        b = font.getbbox(text)
        if b[2] - b[0] <= 70 * ss and b[3] - b[1] <= 38 * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text(((w * ss - (b[2] - b[0])) // 2 - b[0],
                             (h * ss - (b[3] - b[1])) // 2 - b[1]), text,
                            font=font, fill=255)
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > fac.MARK_THRESHOLD, path)
    print(f"  {path.name}  <- {text} (Bebas Neue, {(b[3] - b[1]) // ss} px high)")


def build(out: Path, icons: dict, *, sizes: dict | None = None, ink: dict | None = None,
          numbered: dict | None = None, mark: str) -> int:
    """Fetch and draw a whole set into `out`; returns 0 for ``main()``."""
    sizes, ink, numbered = sizes or {}, ink or {}, numbered or {}
    fac.render(icons, out)
    flat_icons(out, icons, sizes, ink)
    for src in numbered_icons(out, numbered):
        if src.startswith("src_"):
            (out / f"{src}.png").unlink()
    text_mark(out / "program.png", mark)
    print(f"Wrote icons to {out}")
    return 0
