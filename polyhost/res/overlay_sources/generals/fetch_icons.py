#!/usr/bin/env python3
"""Fetch + render the Command & Conquer Generals / Zero Hour icons (reproducible).

Drawn like the C&C Remastered and OpenRA sets (relief, dither, lit outline),
which the control groups, camera views and several orders are taken from:
Generals is a C&C game, and the same meaning keeps the same picture. The new
key icons come from game-icons.net (CC BY 3.0) and Font Awesome Free
(CC BY 4.0); SOURCES.md credits each. The ESC mark is GENERALS set in Bebas
Neue (SIL OFL 1.1); EA's logo art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/generals/fetch_icons.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import wz_units  # noqa: E402
from polyhost.res.overlay_sources.factorio import fetch_icons as fac  # noqa: E402
from polyhost.services.game_assets import dither  # noqa: E402

HERE = Path(__file__).resolve().parent
CNC_ICONS = HERE.parent / "cnc_remastered" / "icons"
OPENRA_ICONS = HERE.parent / "openra" / "icons"

# Taken as they are: the same order or view in the C&C and OpenRA sets.
COPIED = {
    "stop": CNC_ICONS / "stop.png",
    "guard": CNC_ICONS / "guard.png",
    "lastevent": CNC_ICONS / "lastevent.png",
    "selectall": CNC_ICONS / "selectall.png",
    "commandcenter": CNC_ICONS / "conyard.png",
    "attackmove": OPENRA_ICONS / "attackmove.png",
    "sametype": OPENRA_ICONS / "sametype.png",
    "beacon": OPENRA_ICONS / "beacon.png",
    "screenshot": OPENRA_ICONS / "screenshot.png",
    "chatallies": OPENRA_ICONS / "teamchat.png",
    "chatall": OPENRA_ICONS / "allchat.png",
}

# New icons, drawn like the C&C set.
ICONS = {
    "hero": "gi:lorc/medal",
    "formation": "fa:table-cells",
    "diplomacy": "gi:delapouite/shaking-hands",
    "deletebeacon": "fa:trash-can",
    "controlbar": "fa:table-columns",
    "cheer": "fa:face-laugh-beam",
}

VIEWS = "12345678"                  # F1..F8 (the C&C set has 1..4)
MARK = 13                           # size of a group's modifier mark, px


def groups(out: Path) -> None:
    """group<N> (select) and groupnew<N> (Ctrl: create) from the C&C set, plus
    groupadd<N> (Shift: add the selection, a plus in a ring) and groupjump<N>
    (Alt: centre on the group, a sight), as in the OpenRA set."""
    import numpy as np
    from PIL import Image
    for d in "1234567890":
        for stem in (f"group{d}", f"groupnew{d}"):
            shutil.copy(CNC_ICONS / f"{stem}.png", out / f"{stem}.png")
        g = np.asarray(Image.open(CNC_ICONS / f"group{d}.png").convert("RGBA").getchannel("A")) > 127
        for stem, kind in (("groupadd", "ring"), ("groupjump", "sight")):
            cnc._save_mask(dither.with_mark(g, kind, MARK), out / f"{stem}{d}.png")
    print("  group, groupnew (C&C) + groupadd, groupjump")


def views(out: Path) -> None:
    """view<N> (F<N>: go to a saved camera view) and viewset<N> (Ctrl+F<N>:
    save it): the C&C set's bookmark with the number, the plus on top for Ctrl."""
    import numpy as np
    from PIL import Image
    base = np.asarray(Image.open(CNC_ICONS / "bookmark.png").convert("RGBA").getchannel("A")) > 127
    for n in VIEWS:
        numbered = cnc._stamp(base, n)
        cnc._save_mask(numbered, out / f"view{n}.png")
        cnc._save_mask(wz_units._with_plus(numbered, top=True), out / f"viewset{n}.png")
    print(f"  view1..{VIEWS[-1]}, viewset1..{VIEWS[-1]}  <- C&C bookmark + number")


def dither_icons(out: Path) -> None:
    """The new icons drawn like the C&C set: relief, dither, lit outline, 40x40."""
    import numpy as np
    from PIL import Image
    for stem in ICONS:
        alpha = Image.open(out / f"{stem}.png").convert("RGBA").getchannel("A")
        alpha = alpha.crop(alpha.getbbox())
        scale = 320 / max(alpha.size)
        alpha = alpha.resize((round(alpha.width * scale), round(alpha.height * scale)), Image.LANCZOS)
        mask = np.asarray(alpha) > 127
        m = wz_units.keycap(cnc.relief(mask, seed=len(stem)), mask, size=(40, 40), mirror=False)
        canvas = np.zeros((40, 40), bool)
        canvas[40 - m.shape[0]:, 40 - m.shape[1]:] = m
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons dithered")


def program(out: Path) -> None:
    """program.png: GENERALS in Bebas Neue at the largest size that fits
    70 x 38 px, centred on the whole 72x40 cell."""
    path = out / "program.png"
    if not fac._missing(path):
        return
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font_path = cnc._font(fac.MARK_FONT_URL)
    w, h, ss, text = 72, 40, fac.MARK_SS, "GENERALS"
    for px in range(400, 40, -4):
        font = ImageFont.truetype(str(font_path), px)
        b = font.getbbox(text)
        if b[2] - b[0] <= 70 * ss and b[3] - b[1] <= 38 * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text(((w * ss - (b[2] - b[0])) // 2 - b[0],
                             (h * ss - (b[3] - b[1])) // 2 - b[1]), text, font=font, fill=255)
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > fac.MARK_THRESHOLD, path)
    print(f"  program.png  <- {text} (Bebas Neue)")


def main() -> int:
    out = HERE / "icons"
    out.mkdir(exist_ok=True)
    for stem, src in COPIED.items():
        shutil.copy(src, out / f"{stem}.png")
    print(f"  {len(COPIED)} icons copied from the C&C and OpenRA sets")
    cnc.render(ICONS, out)
    dither_icons(out)
    groups(out)
    views(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
