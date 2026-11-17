#!/usr/bin/env python3
"""Fetch + render the Dune II icons (reproducible).

Dune II is Westwood's first real-time strategy game, so its sets look like the
C&C and OpenRA ones: the keys with the same action reuse the OpenRA set's
icons (copied from `../openra/icons/`), and the others are drawn the same way:
a Font Awesome Free (CC BY 4.0) or game-icons.net (CC BY 3.0) silhouette,
shaded and dithered. The ESC marks are DUNE over LEGACY or II in Black Ops One
(SIL OFL 1.1); the game's logo art is not used. SOURCES.md credits each.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/dune2/fetch_icons.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import wz_units  # noqa: E402
from polyhost.res.overlay_sources.openra import fetch_icons as ora  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ORA_ICONS = Path(__file__).resolve().parents[1] / "openra" / "icons"

# The same action as in the OpenRA set: the same picture.
SHARED = ["attackmove", "stop", "guard", "repair", "deploy", "harvesters", "tabupgrade",
          "conyard", "cycleproduction", "zoomreset", "screenshot", "teamchat",
          *(f"{kind}{d}" for kind in ("group", "groupnew", "groupcombine") for d in "123456789")]

ICONS = {
    # Dune Legacy
    "deselect": "fa:xmark",
    "ungroup": "fa:link-slash",
    "move": "fa:location-arrow",
    "capture": "fa:flag",
    "drop": "fa:parachute-box",
    "place": "fa:trowel-bricks",
    "ornithopters": "gi:lorc/dragonfly",
    "slower": "fa:backward",
    "faster": "fa:forward",
    "pause": "fa:pause",
    "fullscreen": "fa:expand",
    "clock": "fa:clock",
    "skip": "fa:forward-fast",
    "sound": "fa:volume-high",
    "music": "fa:music",
    "fps": "fa:gauge-high",
    # The original game (OpenDUNE, DOSBox)
    "retreat": "fa:person-running",
    "build": "fa:hammer",
    "mentat": "gi:lorc/brain",
    "options": "fa:gear",
    "nextunit": "fa:forward-step",
    "prevunit": "fa:backward-step",
}

# F4..F6 skip 10 s, 30 s, 2 min: the skip picture over the time it skips, a
# file each (skip_icons()), so each key has its own image and its own recipe.
SKIPS = {"skip10": "10s", "skip30": "30s", "skip120": "2m"}
SKIP_SIZE = (30, 40)        # the key area of F4..F6 (dune_legacy.yaml)
SKIP_PICTURE_H = 20         # the skip picture's height at the top of the area
SKIP_TEXT_H = 13            # the time's largest height at the bottom
SKIP_GAP = 4                # unlit rows between the picture and the time
RASTERIZE = Path(__file__).resolve().parent / "rasterize.yaml"
ZOOM_LEVELS = "123"                             # F1..F3 in Dune Legacy: zoom level 1..3


def dither_icons(out: Path) -> None:
    """The new icons drawn like the OpenRA set: relief, dither, lit outline, 40x40."""
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


def _enclosed(mask):
    """The unlit pixels `mask` encloses: those not reachable from the border."""
    import numpy as np
    outside = np.zeros_like(mask)
    outside[0, :], outside[-1, :], outside[:, 0], outside[:, -1] = (
        ~mask[0, :], ~mask[-1, :], ~mask[:, 0], ~mask[:, -1])
    while True:
        grown = program_mark.dilate(outside, 1) & ~mask
        if (grown == outside).all():
            return ~mask & ~outside
        outside = grown


def skip_icons(out: Path) -> None:
    """skip10/30/120.png (F4..F6): the skip picture dithered like the other
    icons in the top SKIP_PICTURE_H rows of a SKIP_SIZE area, and the time it
    skips (DejaVu Sans Bold) at the bottom right. Reads _skip.png, the plain
    render of ICONS["skip"]."""
    import numpy as np
    from PIL import Image
    w, h = SKIP_SIZE
    alpha = Image.open(out / "_skip.png").convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    scale = 320 / max(alpha.size)
    alpha = alpha.resize((round(alpha.width * scale), round(alpha.height * scale)), Image.LANCZOS)
    mask = np.asarray(alpha) > 127
    pic = wz_units.keycap(cnc.relief(mask, seed=len("skip")), mask, size=(w, SKIP_PICTURE_H),
                          mirror=False)
    # One text height for the three keys: the largest at which every time fits.
    th = next(t for t in range(SKIP_TEXT_H, 5, -1)
              if all(zeroad._digit(x, t).shape[1] <= w for x in SKIPS.values()))
    for stem, text in SKIPS.items():
        canvas = np.zeros((h, w), bool)
        top = h - th - SKIP_GAP - pic.shape[0]
        canvas[top:top + pic.shape[0], w - pic.shape[1]:] = pic
        g = zeroad._digit(text, th)
        canvas[h - g.shape[0]:, w - g.shape[1]:] = g
        cnc._save_mask(canvas, out / f"{stem}.png")
    (out / "_skip.png").unlink()
    print(f"  {', '.join(SKIPS)}.png  <- {ICONS['skip']} + {', '.join(SKIPS.values())}")


def zoom_levels(out: Path) -> None:
    """zoom1..3.png: the reset-zoom magnifier with the level drawn lit in the
    middle of its lens, as large as the lens allows."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    base = np.asarray(Image.open(out / "zoomreset.png").convert("RGBA").getchannel("A")) > 127
    lens = _enclosed(base)
    ys, xs = np.nonzero(lens)
    cy, cx = (ys.min() + ys.max()) / 2, (xs.min() + xs.max()) / 2
    room = round(0.5 * min(ys.max() - ys.min(), xs.max() - xs.min()))
    for n in ZOOM_LEVELS:
        for px in range(40, 6, -1):
            f = ImageFont.truetype(str(cnc._font(cnc.DIGIT_FONT_URL)), px)
            left, t, right, bottom = f.getbbox(n)
            im = Image.new("L", (right - left + 4, bottom - t + 4), 0)
            ImageDraw.Draw(im).text((2 - left, 2 - t), n, font=f, fill=255)
            g = np.array(im) > 110
            gy, gx = np.nonzero(g)
            g = g[gy.min():gy.max() + 1, gx.min():gx.max() + 1]
            if max(g.shape) <= room:
                break
        m = base.copy()
        y0, x0 = round(cy - g.shape[0] / 2), round(cx - g.shape[1] / 2)
        m[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] |= g
        cnc._save_mask(m, out / f"zoom{n}.png")
    print(f"  zoom1..{ZOOM_LEVELS[-1]}.png  <- zoomreset.png + the level in the lens")


def rasterize(out: Path) -> None:
    """The icons picked re-rasterized in the icon picker (rasterize.yaml, written
    by tools/apply_icon_picks.py): the SVG's silhouette shaded and dithered with
    the page's settings, by the page's renderer, at the picked region."""
    import yaml

    from polyhost.res.overlay_sources import svg_silhouette
    from polyhost.services.game_assets import picture
    if not RASTERIZE.exists():
        return
    entries = yaml.safe_load(RASTERIZE.read_text(encoding="utf-8")) or {}
    for stem, e in entries.items():
        m = picture.vector(svg_silhouette.silhouette(e["svg"]), e, tuple(e["region"]))
        cnc._save_mask(m, out / f"{stem}.png")
        print(f"  {stem}.png  <- {e['svg']} re-rasterized at {e['region'][0]}x{e['region'][1]}")


def programs(out: Path) -> None:
    """program_legacy.png and program_dune2.png: DUNE over LEGACY or II, each line
    at the largest size that fits, over the whole 72x40 cell."""
    import numpy as np
    w, h = program_mark.W, program_mark.H
    for stem, second in (("legacy", "LEGACY"), ("dune2", "II")):
        lines = []
        for text, top in (("DUNE", 16), (second, 12 if second == "LEGACY" else 16)):
            for cap in range(top, 5, -1):
                m = ora._text(text, cap)
                if m.shape[1] <= w - 2:
                    break
            lines.append(m)
        canvas = np.zeros((h, w), bool)
        y = (h - sum(m.shape[0] for m in lines) - 4) // 2
        for m in lines:
            x = (w - m.shape[1]) // 2
            canvas[y:y + m.shape[0], x:x + m.shape[1]] = m
            y += m.shape[0] + 4
        cnc._save_mask(canvas, out / f"program_{stem}.png")
        print(f"  program_{stem}.png  <- DUNE {second} (Black Ops One)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for stem in SHARED:
        shutil.copy(ORA_ICONS / f"{stem}.png", out / f"{stem}.png")
    cnc.render({**ICONS, "_skip": ICONS["skip"]}, out)
    dither_icons(out)
    skip_icons(out)
    zoom_levels(out)
    rasterize(out)
    programs(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
