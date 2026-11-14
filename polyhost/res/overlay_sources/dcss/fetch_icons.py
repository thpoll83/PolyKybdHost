#!/usr/bin/env python3
"""Fetch + render the Dungeon Crawl Stone Soup icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0), Material
Design Icons (Apache-2.0) and game-icons.net (CC BY 3.0). The direction keys
are drawn by this script: an arrow to move, a double chevron to run, a sword
pointing in the direction to attack. SOURCES.md credits each. The ESC mark is
the game's own 32 x 32 icon, the cauldron, reduced to 1 bit.

The NetHack, Cataclysm: Dark Days Ahead and Shattered Pixel Dungeon sets import
the helpers of this file (`build`, `DIRECTIONS`, `wordmark`).

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/dcss/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.icon_fetch import _get  # noqa: E402

# The eight directions, clockwise from north, and the vi key of each.
DIRECTIONS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")
VI_KEYS = {"n": "k", "ne": "u", "e": "l", "se": "n", "s": "j", "sw": "b", "w": "h", "nw": "y"}

# A corner glyph is drawn in the top-left corner of the key area; the base icon
# then fills CORNER_INK at the bottom right and is cut back CORNER_GAP px around
# the glyph.
CORNER_INK = (31, 31)
CORNER_GAP = 2
CORNER_SIGN = 13        # width and height of a plus or minus
CORNER_BAR = 3          # its stroke width
# Corner glyphs taken from an icon set: name -> (icon, box it is fitted into).
CORNER_ICONS = {
    "bolt": ("fa:bolt", (12, 18)),
    "swap": ("fa:right-left", (17, 13)),
    "again": ("fa:rotate-right", (14, 14)),
}
ATTACK_SWORD = "mdi:sword"      # points north-west as drawn
ARROW_SS = 8                    # supersampling factor for the drawn arrows

ICONS = {
    # Plain keys
    "wait": "fa:hourglass-half",
    "rest": "fa:bed",
    "ability": "fa:hand-sparkles",
    "equip": ("mdi:shield-sword", "plus"),
    "unequip": ("mdi:shield-sword", "minus"),
    "drop": "mdi:tray-arrow-down",
    "fire": "fa:crosshairs",
    "pickup": "mdi:tray-arrow-up",
    "inventory": "mdi:bag-personal",
    "skills": "fa:chart-simple",
    "autofire": ("fa:crosshairs", "bolt"),
    "explore": "fa:compass",
    "quaff": "fa:flask",
    "read": "fa:scroll",
    "shout": "fa:bullhorn",
    "attack": "mdi:sword-cross",
    "wield": "mdi:sword",
    "look": "fa:eye",
    "cast": "fa:wand-sparkles",
    "repeat": "fa:rotate-right",
    "again": "fa:repeat",
    "inspectfloor": "fa:magnifying-glass",
    "adjust": "fa:arrow-down-a-z",
    "weaponswap": ("mdi:sword", "swap"),
    "listarmour": "fa:shirt",
    "swapquiver": ("mdi:bow-arrow", "swap"),
    "known": "fa:clipboard-list",
    "gamemenu": "fa:bars",
    "autofight": ("mdi:sword-cross", "bolt"),
    # Shift
    "mutations": "fa:dna",
    "closedoor": "fa:door-closed",
    "droplast": ("mdi:tray-arrow-down", "again"),
    "experience": "fa:ranking-star",
    "throw": "gi:lorc/thrown-daggers",
    "travel": "fa:route",
    "spells": "fa:book",
    "memorise": "fa:brain",
    "opendoor": "fa:door-open",
    "puton": ("fa:ring", "plus"),
    "quiver": "mdi:bow-arrow",
    "remove": ("fa:ring", "minus"),
    "save": "fa:floppy-disk",
    "takeoff": ("fa:shirt", "minus"),
    "evoke": "gi:lorc/crystal-wand",
    "wear": ("fa:shirt", "plus"),
    "map": "fa:map",
    "forcecast": ("fa:wand-sparkles", "bolt"),
    "upstairs": "mdi:stairs-up",
    "downstairs": "mdi:stairs-down",
    "status": "fa:heart-pulse",
    "resists": "fa:shield-halved",
    "note": "fa:pen-to-square",
    "terrain": "fa:mountain",
    "religion": "fa:place-of-worship",
    "dump": "fa:file-export",
    "help": "fa:circle-question",
    "annotate": "fa:thumbtack",
    "gold": "fa:coins",
    "jewellery": "mdi:necklace",
    "inscribe": "fa:pen-nib",
    "quiverprev": ("mdi:bow-arrow", "left"),
    "quivernext": ("mdi:bow-arrow", "right"),
    "runes": "fa:gem",
    # Ctrl
    "autopickup": "fa:magnet",
    "clearmap": "fa:eraser",
    "macromenu": "fa:keyboard",
    "macroadd": ("fa:keyboard", "plus"),
    "stashes": "mdi:archive-search",
    "overview": "fa:sitemap",
    "messages": "fa:message",
    "quit": "fa:power-off",
    "redraw": "fa:arrows-rotate",
    "savenow": ("fa:floppy-disk", "bolt"),
    "waypoint": "fa:location-dot",
    "fullview": "fa:binoculars",
    "suspend": "fa:pause",
}
for _d in DIRECTIONS:
    ICONS[f"move_{_d}"] = f"draw:move:{_d}"
    ICONS[f"run_{_d}"] = f"draw:run:{_d}"
    ICONS[f"attack_{_d}"] = f"draw:attack:{_d}"

# Key area of each icon, from dcss.yaml; the default is 40 x 40.
SIZES = {"gamemenu": (34, 40)}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"save": (34, 34), "gamemenu": (30, 30), "help": (34, 34), "spells": (34, 34),
       "memorise": (34, 34), "map": (36, 34), "explore": (34, 34), "messages": (34, 34),
       "listarmour": (36, 34), "closedoor": (34, 36), "terrain": (36, 34),
       "waypoint": (34, 36), "suspend": (30, 30), "known": (34, 36), "resists": (34, 36)}

# The game's own icon (the cauldron), 32 x 32 pixel art.
OWN_ICON_URL = ("https://raw.githubusercontent.com/crawl/crawl/0.34.1/"
                "crawl-ref/source/dat/tiles/stone_soup_icon-32x32.png")
# The cauldron is drawn as its outline and its contents: a pixel is lit when
# its luma (0..255) is below OWN_ICON_OUTLINE (the black outline) or at least
# OWN_ICON_BRIGHT (the soup and the flames). The grey body stays dark.
OWN_ICON_OUTLINE = 60
OWN_ICON_BRIGHT = 130


def _fit(alpha, box: tuple[int, int]):
    """A PIL "L" image cropped to its ink and scaled to fit `box` (w, h), 1-bit."""
    import numpy as np
    from PIL import Image
    alpha = alpha.crop(alpha.getbbox())
    scale = min(box[0] / alpha.width, box[1] / alpha.height)
    alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                         Image.LANCZOS)
    return np.asarray(alpha) > 150


def _alpha(path: Path):
    from PIL import Image
    return Image.open(path).convert("RGBA").getchannel("A")


def _place(mask, size: tuple[int, int]):
    """`mask` in the bottom-right corner of a canvas of `size` (w, h)."""
    import numpy as np
    canvas = np.zeros((size[1], size[0]), bool)
    canvas[size[1] - mask.shape[0]:, size[0] - mask.shape[1]:] = mask
    return canvas


def _centre(mask, size: tuple[int, int]):
    import numpy as np
    canvas = np.zeros((size[1], size[0]), bool)
    y0, x0 = (size[1] - mask.shape[0]) // 2, (size[0] - mask.shape[1]) // 2
    canvas[y0:y0 + mask.shape[0], x0:x0 + mask.shape[1]] = mask
    return canvas


def _polygons(polygons, angle: float, size=(40, 40)):
    """Polygons given on a 40 x 40 grid for the direction north, turned
    clockwise by `angle` degrees about the centre, 1-bit."""
    import numpy as np
    from PIL import Image, ImageDraw
    ss = ARROW_SS
    im = Image.new("L", (size[0] * ss, size[1] * ss), 0)
    draw = ImageDraw.Draw(im)
    for poly in polygons:
        draw.polygon([(x * ss, y * ss) for x, y in poly], fill=255)
    im = im.rotate(-angle, resample=Image.BICUBIC)
    return np.asarray(im.resize(size, Image.BOX)) > 127


def _chevron(y: float, half: float = 13, bar: float = 7):
    """An upward chevron with its point at (20, y)."""
    return [(20, y), (20 + half, y + half), (20 + half, y + half + bar), (20, y + bar),
            (20 - half, y + half + bar), (20 - half, y + half)]


# What is drawn for the direction north, per style.
ARROW = [[(20, 3), (34, 19), (24, 19), (24, 37), (16, 37), (16, 19), (6, 19)]]
RUN = [_chevron(5), _chevron(18)]
# An arrow that ends at a bar: go until something stops you.
RUSH = [[(6, 3), (34, 3), (34, 8), (6, 8)],
        [(20, 11), (32, 24), (24, 24), (24, 38), (16, 38), (16, 24), (8, 24)]]
STYLES = {"move": ARROW, "run": RUN, "rush": RUSH}
# A diagonal has more room for an arrow or a chevron, so the drawing is enlarged
# about the centre. The bar of a rush arrow would leave the key area: it is
# reduced.
DIAGONAL_SCALE = {"move": 1.2, "run": 1.2, "rush": 0.95}


def direction_icon(style: str, direction: str, work: Path):
    """The icon of one direction key: `style` is move, run, rush or attack."""
    angle = DIRECTIONS.index(direction) * 45
    if style == "attack":
        # The sword points north-west as drawn, so north is one step clockwise.
        sword = _alpha(work / "_sword.png").rotate(-(angle + 45), resample=3, expand=True)
        return _centre(_fit(sword, (40, 40)), (40, 40))
    polygons = STYLES[style]
    if angle % 90:
        k = DIAGONAL_SCALE[style]
        polygons = [[(20 + (x - 20) * k, 20 + (y - 20) * k) for x, y in p] for p in polygons]
    return _polygons(polygons, angle)


def corner_glyph(name: str, work: Path):
    """The small glyph `name` as a 1-bit mask."""
    import numpy as np
    if name in CORNER_ICONS:
        return _fit(_alpha(work / f"_corner_{name}.png"), CORNER_ICONS[name][1])
    g = np.zeros((CORNER_SIGN, CORNER_SIGN), bool)
    lo = (CORNER_SIGN - CORNER_BAR) // 2
    if name in ("plus", "minus"):
        g[lo:lo + CORNER_BAR, :] = True
        if name == "plus":
            g[:, lo:lo + CORNER_BAR] = True
        return g
    if name in ("left", "right"):
        # A filled triangle pointing left or right.
        for x in range(CORNER_SIGN):
            reach = (x if name == "left" else CORNER_SIGN - 1 - x) // 2
            g[CORNER_SIGN // 2 - reach:CORNER_SIGN // 2 + reach + 1, x] = True
        return g
    raise ValueError(f"unknown corner glyph {name!r}")


def with_corner(base, glyph, size: tuple[int, int]):
    """`base` at the bottom right of the key area, `glyph` in its top-left
    corner, the base cut back CORNER_GAP px around the glyph."""
    import numpy as np
    canvas = _place(base, size)
    g = np.zeros_like(canvas)
    g[0:glyph.shape[0], 0:glyph.shape[1]] = glyph
    return (canvas & ~program_mark.dilate(g, CORNER_GAP)) | g


def build(icons: dict, out: Path, sizes: dict | None = None, ink: dict | None = None) -> None:
    """Every icon of `icons` as a flat 1-bit silhouette, drawn at exactly its
    key area so the generator places it 1:1.

    A value is an icon name ("fa:bed"), a pair of an icon name and a corner
    glyph (("fa:ring", "plus")), or "draw:<style>:<direction>" for a direction
    key. `sizes` gives key areas other than 40 x 40, `ink` a smaller box for
    icons that would read too heavy."""
    sizes, ink = sizes or {}, ink or {}
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        fetch = {"_sword": ATTACK_SWORD}
        fetch.update({f"_corner_{n}": spec for n, (spec, _) in CORNER_ICONS.items()})
        for stem, spec in icons.items():
            name = spec[0] if isinstance(spec, tuple) else spec
            if not name.startswith("draw:"):
                fetch[stem] = name
        cnc.render(fetch, work)
        for stem, spec in icons.items():
            size = sizes.get(stem, (40, 40))
            if isinstance(spec, tuple):
                base = _fit(_alpha(work / f"{stem}.png"), ink.get(stem, CORNER_INK))
                mask = with_corner(base, corner_glyph(spec[1], work), size)
            elif spec.startswith("draw:"):
                _, style, direction = spec.split(":")
                mask = direction_icon(style, direction, work)
            else:
                mask = _place(_fit(_alpha(work / f"{stem}.png"), ink.get(stem, size)), size)
            cnc._save_mask(mask, out / f"{stem}.png")
    print(f"  {len(icons)} key icons drawn flat")


def wordmark(lines, font_url: str, path: Path, threshold: int = 100, gap: int = 2,
             size: tuple[int, int] = (72, 40)) -> None:
    """The lines of `lines` set in the font at `font_url`, at the largest one
    size at which each fits the width less 2 px and all, `gap` px apart, fit
    the height less 2 px; centred, drawn at 8 times the size and box-filtered
    down. A pixel is lit from grey `threshold` of 255."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    (w, h), ss = size, 8
    font_path = str(cnc._font(font_url))
    for px in range(480, 40, -4):
        font = ImageFont.truetype(font_path, px)
        boxes = [font.getbbox(line) for line in lines]
        height = sum(b[3] - b[1] for b in boxes) + gap * ss * (len(boxes) - 1)
        if all(b[2] - b[0] <= (w - 2) * ss for b in boxes) and height <= (h - 2) * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    draw = ImageDraw.Draw(im)
    y = (h * ss - height) // 2
    for line, box in zip(lines, boxes):
        draw.text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                  line, font=font, fill=255)
        y += box[3] - box[1] + gap * ss
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > threshold, path)
    print(f"  {path.name}  <- {' / '.join(lines)} ({px / ss:.1f} px)")


def program(out: Path) -> None:
    """program.png: the game's own 32 x 32 icon, 1:1, as its outline and its
    bright parts (OWN_ICON_OUTLINE, OWN_ICON_BRIGHT)."""
    import numpy as np
    from PIL import Image
    im = Image.open(io.BytesIO(_get(OWN_ICON_URL))).convert("RGBA")
    luma = np.asarray(im.convert("L"))
    alpha = np.asarray(im.getchannel("A"))
    cnc._save_mask((alpha > 127) & ((luma < OWN_ICON_OUTLINE) | (luma >= OWN_ICON_BRIGHT)), out / "program.png")
    print("  program.png  <- stone_soup_icon-32x32.png")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    build(ICONS, out, SIZES, INK)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
