#!/usr/bin/env python3
"""Fetch + render the OpenRCT2 icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0),
Material Design Icons (Apache-2.0) and game-icons.net (CC BY 3.0), as in the
Warcraft III set. A few are composed here from those shapes: the see-through
toggles (the shape as an outline, or every second pixel for the supports), the
height marks (a ruler beside the shape), Build new ride (the rides list's
ferris wheel with a plus), and the two land toggles (an isometric block with
one part dotted). SOURCES.md credits each. The ESC mark is OpenRCT2's own
logo (GPL-3.0-or-later), dithered to 1 bit, with OPEN and RCT in Silkscreen
Bold (SIL OFL 1.1) either side of its bottom tip.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/openrct2/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402

# Drawn flat at their key area (FLAT_SIZES, default 40 x 40).
ICONS = {
    # Construction windows (F1 to F5, B, Z)
    "land": "fa:mountain",
    "water": "fa:water",
    "scenery": "fa:tree",
    "paths": "fa:shoe-prints",
    "clearscenery": "gi:lorc/wood-axe",
    "rotateobject": "mdi:rotate-3d-variant",
    # Information windows
    "finances": "fa:sack-dollar",
    "research": "fa:flask",
    "rides": "mdi:ferris-wheel",
    "park": "gi:delapouite/park-bench",
    "guests": "fa:users",
    "staff": "fa:helmet-safety",
    "messages": "fa:envelope",
    "map": "fa:map",
    "chat": "fa:comment",
    "shortcuts": "fa:keyboard",
    "transparency": "mdi:circle-opacity",
    "cheats": "fa:wand-magic-sparkles",
    "console": "fa:terminal",
    # View
    "underground": "mdi:tunnel",
    "transparentwater": "mdi:water-opacity",
    "gridlines": "mdi:grid",
    "pathissues": "fa:triangle-exclamation",
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "rotatecw": "fa:rotate-right",
    "rotateccw": "fa:rotate-left",
    "windowed": "fa:expand",
    # Game
    "pause": "fa:pause",
    "slower": "fa:backward",
    "faster": "fa:forward",
    "closetop": "fa:rectangle-xmark",
    "closeall": "mdi:close-box-multiple",
    "screenshot": "fa:camera",
    "giantscreenshot": "fa:panorama",
    "load": "fa:folder-open",
    "save": "fa:floppy-disk",
}

# Shapes that only feed the composed icons below.
PARTS = {
    "_rides": "mdi:ferris-wheel",
    "_scenery": "fa:tree",
    "_supports": "mdi:pillar",
    "_guests": "fa:users",
    "_land": "fa:mountain",
    "_track": "gi:delapouite/rail-road",
    "_paths": "fa:shoe-prints",
}

# Key area of each icon; the default is 40 x 40. F1 and F2 keep their legend
# whole at 34 px, F4 and F5 at 30 px (the widths measured for AoE2).
FLAT_SIZES = {"land": (34, 40), "water": (34, 40), "paths": (30, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"save": (34, 34), "load": (34, 34), "chat": (34, 34), "messages": (34, 34),
       "zoomin": (30, 30), "zoomout": (30, 30), "screenshot": (30, 30),
       "pause": (26, 30), "slower": (34, 26), "faster": (34, 26)}

# See-through toggles (3, 4, 6): the shape as an outline OUTLINE px wide.
HOLLOW = {"seerides": "_rides", "seescenery": "_scenery", "seeguests": "_guests"}
OUTLINE = 2
# Height marks (8, 9, 0): a ruler on the left, the shape on the right.
HEIGHTS = {"heightland": "_land", "heighttrack": "_track", "heightpaths": "_paths"}

# The ESC mark: OpenRCT2's logo at tag v0.5.6 (GPL-3.0-or-later, like the game)
# and its text in Silkscreen Bold (SIL OFL 1.1).
LOGO_URL = ("https://raw.githubusercontent.com/OpenRCT2/OpenRCT2/"
            "82b309798a83346b7f9fc61a53847f4323deb19d/resources/logo/icon_x256.png")
# The cache is named after the file, so a different icon_x256.png in the temp dir is refused.
LOGO_SHA256 = "abf1529f307f63594e7fe1324466738ad03b03829e659dd0a299fafe42add4d1"
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/silkscreen/Silkscreen-Bold.ttf")
MARK_TEXT = ("OPEN", "RCT")                     # bottom-left and bottom-right of the logo
MARK_CAP = 5                                    # capital height of the text, px
MARK_GAP = 2                                    # unlit pixels between the text and the logo
MARK_SS = 8                                     # supersampling factor for drawn shapes and text
MARK_THRESHOLD = 110                            # grey level (0..255) from which a pixel is lit


def _alpha(path: Path):
    from PIL import Image
    a = Image.open(path).convert("RGBA").getchannel("A")
    return a.crop(a.getbbox())


def _fit(path: Path, box: tuple[int, int]):
    """The shape in `path` scaled to fit `box` (w, h), 1-bit."""
    import numpy as np
    from PIL import Image
    a = _alpha(path)
    k = min(box[0] / a.width, box[1] / a.height)
    a = a.resize((max(1, round(a.width * k)), max(1, round(a.height * k))), Image.LANCZOS)
    return np.asarray(a) > 150


def _place(mask, size: tuple[int, int]):
    """`mask` in the bottom-right corner of a `size` (w, h) canvas."""
    import numpy as np
    canvas = np.zeros((size[1], size[0]), bool)
    canvas[size[1] - mask.shape[0]:, size[0] - mask.shape[1]:] = mask
    return canvas


def flat_icons(out: Path) -> None:
    """Every plain key icon as a flat 1-bit silhouette, drawn at exactly its key
    area so the generator places it 1:1. The icons in INK fill a smaller box in
    the bottom-right corner of that area."""
    for stem in ICONS:
        size = FLAT_SIZES.get(stem, (40, 40))
        m = _fit(out / f"{stem}.png", INK.get(stem, size))
        cnc._save_mask(_place(m, size), out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def new_ride(out: Path) -> None:
    """newride.png (F5, Build new ride): the ferris wheel of the rides list
    (R) with the Ctrl plus of the AoE2 control groups, 30 x 40 so the F5
    legend stays whole."""
    m = _place(_fit(out / "_rides.png", (30, 40)), (30, 40))
    cnc._save_mask(aoe2._with_plus(m, size=11), out / "newride.png")
    print("  newride.png  <- _rides.png + a plus")


def hollow(out: Path) -> None:
    """The see-through toggles: the shape reduced to its outline."""
    for stem, part in HOLLOW.items():
        m = _place(_fit(out / f"{part}.png", (40, 40)), (40, 40))
        inner = ~program_mark.dilate(~m, OUTLINE)
        cnc._save_mask(m & ~inner, out / f"{stem}.png")
        print(f"  {stem}.png  <- {part}.png as an outline")
    # The pillar's parts are too thin for an outline: every second pixel instead.
    import numpy as np
    m = _place(_fit(out / "_supports.png", (40, 40)), (40, 40))
    yy, xx = np.mgrid[0:40, 0:40]
    cnc._save_mask(m & ((xx + yy) % 2 == 0), out / "seesupports.png")
    print("  seesupports.png  <- _supports.png, every second pixel")


def heights(out: Path) -> None:
    """The height-mark toggles: a ruler at the left of the area (a 2 px bar,
    the full height, with a tick every 4 px, long and short in turn), the shape
    in a 28 x 28 box at the bottom right."""
    import numpy as np
    ruler = np.zeros((40, 9), bool)
    ruler[:, :2] = True
    for i, y in enumerate(range(1, 40, 4)):
        ruler[y:y + 2, 2:9 if i % 2 == 0 else 6] = True
    for stem, part in HEIGHTS.items():
        m = _place(_fit(out / f"{part}.png", (28, 28)), (40, 40))
        m[:, :ruler.shape[1]] |= ruler
        cnc._save_mask(m, out / f"{stem}.png")
        print(f"  {stem}.png  <- a ruler + {part}.png")


def land_blocks(out: Path) -> None:
    """hidebase.png (H) and hidevertical.png (V): an isometric block of land.
    Hide base land draws the top face as a dotted outline and the two side
    faces solid; Hide vertical land draws the top face solid and the side faces
    as a dotted outline. Drawn at MARK_SS times the size and box-filtered."""
    import numpy as np
    from PIL import Image, ImageDraw
    ss, size = MARK_SS, 40
    # Corners of the block: top face (n, e, s, w), side faces down by `depth`.
    cx, top, half_w, half_h, depth = 20, 3, 18, 10, 14
    n, e = (cx, top), (cx + half_w, top + half_h)
    s, w = (cx, top + 2 * half_h), (cx - half_w, top + half_h)
    s2, e2, w2 = (s[0], s[1] + depth), (e[0], e[1] + depth), (w[0], w[1] + depth)
    faces = {"top": [n, e, s, w], "left": [w, s, s2, w2], "right": [s, e, e2, s2]}

    def scaled(points):
        return [(x * ss, y * ss) for x, y in points]

    def solid(name):
        im = Image.new("L", (size * ss, size * ss), 0)
        ImageDraw.Draw(im).polygon(scaled(faces[name]), fill=255)
        return np.asarray(im.resize((size, size), Image.BOX)) > 110

    def dotted(name):
        im = Image.new("L", (size * ss, size * ss), 0)
        pts = scaled(faces[name])
        ImageDraw.Draw(im).line(pts + pts[:1], fill=255, width=2 * ss)
        m = np.asarray(im.resize((size, size), Image.BOX)) > 110
        yy, xx = np.mgrid[0:size, 0:size]
        return m & (((xx + yy) // 3) % 2 == 0)

    gap = 1                                     # unlit pixels between two solid faces
    sides = solid("left") | solid("right")
    sides &= ~program_mark.dilate(solid("left") & solid("right"), gap)
    base = sides | dotted("top")
    vertical = solid("top") | ((dotted("left") | dotted("right")) & ~program_mark.dilate(solid("top"), 2))
    cnc._save_mask(base, out / "hidebase.png")
    cnc._save_mask(vertical, out / "hidevertical.png")
    print("  hidebase.png, hidevertical.png  <- drawn")


def _mark_font(px: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(cnc._font(FONT_URL)), px)


def _mark_word(text: str):
    """`text` with capitals MARK_CAP px tall, as a cropped 1-bit mask."""
    import numpy as np
    from PIL import Image, ImageDraw
    ss = MARK_SS
    b = _mark_font(400).getbbox("H")
    f = _mark_font(round(MARK_CAP * ss * 400 / (b[3] - b[1])))
    left, top, right, bottom = f.getbbox(text)
    im = Image.new("L", (right - left + 2 * ss, bottom - top + 2 * ss), 0)
    ImageDraw.Draw(im).text((ss - left, ss - top), text, font=f, fill=255)
    m = np.asarray(im.resize((im.width // ss, im.height // ss), Image.BOX)) > MARK_THRESHOLD
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _logo_grey():
    """The logo as grey (0..1) by colour, and its cover: the yellow stripes and
    the grey slide are bright; the red stripes, the blue sky and the dark frame
    are dark, so the tower stands out from the sky."""
    import colorsys
    import numpy as np
    from PIL import Image
    import hashlib
    path = cnc._font(LOGO_URL)
    if hashlib.sha256(path.read_bytes()).hexdigest() != LOGO_SHA256:
        raise SystemExit(f"{path} is not the OpenRCT2 logo of v0.5.6; delete it and run again")
    im = np.asarray(Image.open(path).convert("RGBA"), float) / 255
    mx, mn = im[..., :3].max(-1), im[..., :3].min(-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    hue = np.vectorize(lambda r, g, b: colorsys.rgb_to_hsv(r, g, b)[0] * 360)(im[..., 0], im[..., 1], im[..., 2])
    bright = ((hue > 30) & (hue < 80) & (sat > 0.25)) | (sat < 0.25)
    v = np.where(bright, mx, 0.1 * mx)
    return np.where(mx < 0.3, 0, v), im[..., 3] > 0.5


def program(out: Path) -> None:
    """program.png: OpenRCT2's logo dithered into a 40 px diamond in the middle
    of the 72x40 cell, OPEN at the bottom left and RCT at the bottom right."""
    import numpy as np
    from polyhost.services.game_assets.dither import keycap
    w, h = program_mark.W, program_mark.H
    grey, cover = _logo_grey()
    logo = keycap(grey, cover, (h, h), floor=0, curve=2.0, sharpen=1.5)
    canvas = np.zeros((h, w), bool)
    lh, lw = logo.shape
    canvas[(h - lh) // 2:(h - lh) // 2 + lh, (w - lw) // 2:(w - lw) // 2 + lw] = logo
    keep_off = program_mark.dilate(canvas, MARK_GAP)
    for text, x_of in zip(MARK_TEXT, (lambda tw: 0, lambda tw: w - tw), strict=True):
        m = _mark_word(text)
        th, tw = m.shape
        word = np.zeros((h, w), bool)
        word[h - 1 - th:h - 1, x_of(tw):x_of(tw) + tw] = m
        if (word & keep_off).any():
            raise SystemExit(f"program.png: {text} comes closer than {MARK_GAP} px to the logo")
        canvas |= word
    cnc._save_mask(canvas, out / "program.png")
    print("  program.png  <- OpenRCT2 logo (dithered) + OPEN / RCT (Silkscreen Bold)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    flat_icons(out)
    new_ride(out)
    hollow(out)
    heights(out)
    land_blocks(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
