#!/usr/bin/env python3
"""Fetch + render the OpenRA icons (reproducible).

OpenRA plays Command & Conquer, so its overlay looks like the C&C Remastered
one: the keys with the same action reuse that set's icons (copied from
`../cnc_remastered/icons/`), and the others are drawn the same way: a Font
Awesome Free (CC BY 4.0) or game-icons.net (CC BY 3.0) silhouette, shaded and
dithered. The control groups are the C&C Warzone 2100 units, with a mark per
modifier. The ESC marks are OpenRA's own mod logos (GPL-3.0, from the OpenRA
repository) beside the mod name. SOURCES.md credits each.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/openra/fetch_icons.py
    python polyhost/res/overlay_sources/openra/gen_mods.py
"""
from __future__ import annotations

import io
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import wz_units  # noqa: E402
from polyhost.res.overlay_sources.icon_fetch import _get  # noqa: E402

CNC_ICONS = Path(__file__).resolve().parents[1] / "cnc_remastered" / "icons"

# The same action as in the C&C Remastered overlay: the same picture.
SHARED = ["stop", "guard", "scatter", "selectall", "conyard", "lastevent", "tabstructures",
          *(f"bookmark{n}" for n in "1234"), *(f"bookmarkset{n}" for n in "1234")]

ICONS = {
    # Orders and stances
    "attackmove": "gi:lorc/crossed-swords",
    "deploy": "fa:circle-down",
    "attackanything": "gi:lorc/sword-clash",
    "defend": "fa:shield",
    "returnfire": "fa:reply",
    "holdfire": "fa:ban",
    # Selection
    "sametype": "fa:object-group",
    "harvesters": "fa:truck",
    "toselection": "fa:crosshairs",
    "cycleproduction": "fa:industry",
    # Base
    "sell": "fa:dollar-sign",
    "repair": "fa:wrench",
    "beacon": "fa:location-dot",
    # View
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "zoomreset": "fa:magnifying-glass",
    "statusbars": "fa:bars-progress",
    # Other
    "mute": "fa:volume-xmark",
    "screenshot": "fa:camera",
    "teamchat": "gi:lorc/conversation",
    "allchat": "gi:delapouite/megaphone",
}

# OpenRA's mod logos, GPL-3.0 like the rest of the OpenRA repository.
LOGO_URL = ("https://raw.githubusercontent.com/OpenRA/OpenRA/"
            "cd207614b55d53bd2897408386fcec8a1f48cce0/packaging/artwork/{}_scalable.svg")
MODS = {"ra": "RA", "cnc": "C&C"}          # logo file stem -> the name beside it

MARK = 13                                   # size of a group's modifier mark, px


def _ring(H, W, cy, cx, r):
    import numpy as np
    yy, xx = np.mgrid[0:H, 0:W]
    disc = (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r
    return disc, disc & program_mark.dilate(~disc, 1)


def _mark(mask, kind):
    """`mask` (a group) with a modifier mark in the lower-right corner, the
    group cleared 2 px around it: "ring" a plus in a ring (Ctrl+Shift: add to
    the group), "box" a plus in a square (Shift: add the group to the
    selection), "sight" a ring with four ticks (Alt: jump to the group)."""
    import numpy as np
    H, W = mask.shape
    h = MARK // 2
    cy, cx = H - h - 3, W - h - 3                  # the ring (radius h + 1) inside the cell
    m = np.zeros((H, W), bool)
    plus = np.zeros((H, W), bool)
    plus[cy - 1:cy + 2, cx - h + 2:cx + h - 1] = True
    plus[cy - h + 2:cy + h - 1, cx - 1:cx + 2] = True
    if kind == "ring":
        area, ring = _ring(H, W, cy, cx, h + 1)
        m = ring | plus
    elif kind == "box":
        area = np.zeros((H, W), bool)
        area[cy - h:cy + h + 1, cx - h:cx + h + 1] = True
        m = (area & program_mark.dilate(~area, 1)) | plus
    else:
        area, ring = _ring(H, W, cy, cx, h - 1)
        m = ring.copy()
        m[cy, cx - h:cx - h + 4] = m[cy, cx + h - 3:cx + h + 1] = True
        m[cy - h:cy - h + 4, cx] = m[cy + h - 3:cy + h + 1, cx] = True
        area = area | m
    return (mask & ~program_mark.dilate(area, 2)) | m


def groups(out: Path) -> None:
    """group<N> (select) and groupnew<N> (Ctrl: create) as in the C&C set, plus
    groupadd<N> (Ctrl+Shift), groupcombine<N> (Shift) and groupjump<N> (Alt)."""
    import numpy as np
    from PIL import Image
    for d in "1234567890":
        for stem in (f"group{d}", f"groupnew{d}"):
            shutil.copy(CNC_ICONS / f"{stem}.png", out / f"{stem}.png")
        g = np.asarray(Image.open(CNC_ICONS / f"group{d}.png").convert("RGBA").getchannel("A")) > 127
        for stem, kind in (("groupadd", "ring"), ("groupcombine", "box"), ("groupjump", "sight")):
            cnc._save_mask(_mark(g, kind), out / f"{stem}{d}.png")
    print("  group, groupnew (C&C) + groupadd, groupcombine, groupjump  <- C&C group icons")


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


def _text(text, cap, gap=1):
    import numpy as np
    font = cnc._font(cnc.STENCIL_URL)
    gs = [cnc._glyph(c, font, cap)[0] for c in text]
    m = np.zeros((max(g.shape[0] for g in gs), sum(g.shape[1] for g in gs) + gap * (len(gs) - 1)), bool)
    x = 0
    for g in gs:
        m[m.shape[0] - g.shape[0]:, x:x + g.shape[1]] = g
        x += g.shape[1] + gap
    return m


def programs(out: Path) -> None:
    """program_<mod>.png: the mod's logo on the left, OPEN over the mod's name on
    the right, over the whole 72x40 cell. The logo's dark linework is lit, so
    the star keeps its hammer and sickle."""
    import cairosvg
    import numpy as np
    from PIL import Image
    for stem, name in MODS.items():
        svg = _get(LOGO_URL.format(stem))
        im = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg, output_width=320, output_height=320)))
        a = np.asarray(im.convert("RGBA")).astype(float) / 255
        lum = a[..., :3] @ [0.299, 0.587, 0.114]
        ink = Image.fromarray((((a[..., 3] > 0.5) & (lum < 0.4)) * 255).astype(np.uint8))
        ink = ink.crop(ink.getbbox())
        s = min(36 / ink.width, 36 / ink.height)
        logo = np.asarray(ink.resize((round(ink.width * s), round(ink.height * s)), Image.LANCZOS)) > 127
        w, h = program_mark.W, program_mark.H
        canvas = np.zeros((h, w), bool)
        y = (h - logo.shape[0]) // 2
        canvas[y:y + logo.shape[0], 1:1 + logo.shape[1]] = logo
        x0 = 1 + logo.shape[1] + 3
        right = w - x0 - 1
        top = _text("OPEN", 7)
        for cap in range(12, 5, -1):                # the name at the largest size that fits
            bottom = _text(name, cap)
            if bottom.shape[1] <= right:
                break
        y = (h - top.shape[0] - 3 - bottom.shape[0]) // 2
        for m in (top, bottom):
            x = x0 + (right - m.shape[1]) // 2
            canvas[y:y + m.shape[0], x:x + m.shape[1]] = m
            y += m.shape[0] + 3
        cnc._save_mask(canvas, out / f"program_{stem}.png")
        print(f"  program_{stem}.png  <- OpenRA {stem}_scalable.svg + OPEN {name}")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for stem in SHARED:
        shutil.copy(CNC_ICONS / f"{stem}.png", out / f"{stem}.png")
    cnc.render(ICONS, out)
    dither_icons(out)
    groups(out)
    programs(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
