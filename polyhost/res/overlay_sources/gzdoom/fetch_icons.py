#!/usr/bin/env python3
"""Fetch + render the GZDoom and UZDoom icons (reproducible).

The key icons are flat 1-bit silhouettes from game-icons.net (CC BY 3.0), Font
Awesome Free (CC BY 4.0) and Material Design Icons (Apache-2.0), as in the
fheroes2 set. SOURCES.md credits each. No id Software artwork is used: the
weapon keys show generic weapon shapes.

The GZDoom ESC mark is the "GZ" of GZDoom's own icon (GPL-3.0). The UZDoom ESC
mark is "UZ" over "Doom" set in Black Ops One (SIL OFL 1.1), because UZDoom's
icon is CC BY-SA 4.0.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/gzdoom/fetch_icons.py

`CATALOGUE`, `build()`, `own_icon_mark()` and `wordmark()` are also used by
the Chocolate Doom and Quake sets (`../chocolate_doom`, `../quake`).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.icon_fetch import _get  # noqa: E402

# Every icon the Doom and Quake port sets draw: stem -> source icon.
CATALOGUE = {
    # Movement
    "forward": "fa:arrow-up",
    "back": "fa:arrow-down",
    "strafeleft": "fa:arrow-left",
    "straferight": "fa:arrow-right",
    "turnleft": "fa:reply",
    "turnright": "fa:share",
    "reverse": "mdi:arrow-u-down-left-bold",
    "jump": "gi:delapouite/jump-across",
    "crouch": "mdi:arrow-collapse-down",
    "use": "fa:hand-pointer",
    "autorun": "fa:person-running",
    "lookup": "fa:angles-up",
    "lookdown": "fa:angles-down",
    "centerview": "fa:arrows-to-dot",
    "mouselook": "fa:computer-mouse",
    "keylook": "fa:keyboard",
    # Doom weapons
    "fist": "gi:lorc/fist",
    "pistol": "gi:john-colburn/pistol-gun",
    "shotgun": "gi:skoll/winchester-rifle",
    "supershotgun": "gi:delapouite/sawed-off-shotgun",
    "chaingun": "gi:lorc/minigun",
    "rocket": "gi:lorc/rocket",
    "plasma": "gi:lorc/ray-gun",
    "bfg": "gi:lorc/bolter-gun",
    "chainsaw": "gi:delapouite/chainsaw",
    "weapontoggle": "fa:repeat",
    "reload": "fa:arrows-rotate",
    # Quake weapons (the shotguns, the rocket and the minigun are shared)
    "axe": "gi:lorc/wood-axe",
    "nailgun": "gi:lorc/nails",
    "grenade": "gi:lorc/grenade",
    "thunderbolt": "gi:sbed/electric",
    # Automap
    "map": "fa:map",
    "mapfollow": "fa:location-crosshairs",
    "mapgrid": "fa:table-cells",
    "mapmark": "fa:location-dot",
    "mapclear": "fa:eraser",
    "maptexture": "fa:image",
    "mapmaxzoom": "fa:expand",
    "maprotate": "fa:compass",
    "mapoverlay": "fa:layer-group",
    "maptag": "fa:tag",
    # Menus and the function keys
    "help": "fa:circle-question",
    "save": "fa:floppy-disk",
    "load": "fa:folder-open",
    "options": "fa:gear",
    "volume": "fa:volume-high",
    "display": "fa:display",
    "detail": "mdi:quality-high",
    "hud": "fa:gauge-high",
    "endgame": "fa:circle-stop",
    "messages": "fa:comment-slash",
    "quit": "fa:power-off",
    "gamma": "fa:sun",
    "spy": "fa:eye",
    "multiplayer": "fa:users",
    "zoom": "fa:magnifying-glass-plus",
    "sizeup": "fa:up-right-and-down-left-from-center",
    "sizedown": "fa:down-left-and-up-right-to-center",
    "pause": "fa:pause",
    "screenshot": "fa:camera",
    "chat": "fa:comment-dots",
    "scores": "fa:ranking-star",
    "console": "fa:terminal",
    # Levels and demos
    "restart": "fa:arrow-rotate-left",
    "nextlevel": "fa:forward-step",
    "prevlevel": "fa:backward-step",
    "demoskip": "fa:forward-fast",
    "demoend": "fa:flag-checkered",
}
# Icons composed from two parts by build(): stem -> (base part, added part).
COMPOSED = {
    "quicksave": ("fa:floppy-disk", "fa:bolt"),
    "quickload": ("fa:folder-open", "fa:bolt"),
    "swimup": ("fa:water", "fa:arrow-up"),
    "swimdown": ("fa:water", "fa:arrow-down"),
    "nextweapon": ("gi:john-colburn/pistol-gun", "fa:arrow-right"),
}
# Thin drawings (the long guns, the chainsaw): every stroke grown by this many
# pixels, so the shape stays readable at 1 bit.
BOLD = {"shotgun": 1, "supershotgun": 1, "chainsaw": 1}
# Icons that fill a box different from the default (see _box()).
INK = {
    "fist": (34, 40), "rocket": (36, 36), "bfg": (38, 38), "grenade": (34, 40),
    "thunderbolt": (30, 40), "axe": (36, 36), "nailgun": (36, 36),
    "jump": (36, 36), "autorun": (30, 34), "use": (28, 34), "mouselook": (24, 34),
    "keylook": (36, 30), "map": (34, 30), "display": (34, 30), "hud": (34, 30),
    "volume": (34, 28), "multiplayer": (36, 28), "scores": (36, 32),
    "console": (34, 28), "screenshot": (32, 28),
}

# The wordmark face: Black Ops One (SIL OFL 1.1), as the C&C set uses.
FONT_URL = cnc.STENCIL_URL
MARK_SS = 8                 # supersampling factor for a wordmark
MARK_GAP = 2                # px between two lines of a wordmark
MARK_THRESHOLD = 90         # grey level (0..255) from which a wordmark pixel is lit

# GZDoom's own icon, at the release tag the keys were read from.
GZDOOM_ICON = ("https://raw.githubusercontent.com/ZDoom/gzdoom/"
               "99aa489d09015a95bb78df2b30ede29f328cc874/src/win32/icon1.ico")
# The part of the 256 px frame that holds the letters "GZ" (left, top, right,
# bottom), and the grey level from which a pixel of the metal letters is lit.
GZDOOM_CROP = (34, 62, 226, 172)
GZDOOM_CUT = 105

STEMS = (
    "forward", "back", "strafeleft", "straferight", "jump", "crouch", "use", "autorun",
    "lookup", "lookdown", "centerview", "reload",
    "fist", "pistol", "shotgun", "chaingun", "rocket", "plasma", "bfg",
    "map", "mapfollow", "mapgrid", "mapmark", "mapclear", "maptexture", "mapmaxzoom",
    "help", "save", "load", "options", "display", "quicksave", "endgame", "messages",
    "quickload", "quit", "gamma", "spy", "sizeup", "sizedown", "pause", "screenshot",
    "chat", "scores", "console",
)
# Key area of each icon, from the specs; the default is 40 x 40. F1 to F9 are
# 34 px wide and F10 to F12 30 px, the widths the AoE2 set measured to keep the
# legends whole.
SIZES = {**{s: (34, 40) for s in ("help", "save", "load", "options", "display",
                                  "quicksave", "endgame", "messages", "quickload")},
         **{s: (30, 40) for s in ("quit", "gamma", "spy")}}


def _box(stem: str, spec: str, size: tuple[int, int]) -> tuple[int, int]:
    """The box an icon's ink fills inside its key area. A game-icons.net
    drawing uses the whole area; the solid Font Awesome and Material Design
    shapes read heavier and get a smaller box."""
    if stem in INK:
        return min(INK[stem][0], size[0]), min(INK[stem][1], size[1])
    if spec.startswith("gi:"):
        return size
    side = {40: 32, 34: 30, 30: 28}[size[0]]
    return side, side


def _mask(path: Path, box: tuple[int, int], bold: int = 0):
    """The icon's alpha cropped to its ink and scaled to fit `box` (w, h),
    1-bit. With `bold`, the drawing is scaled to a box that much smaller on
    every side and then grown by `bold` px, so it still fits `box`."""
    import numpy as np
    from PIL import Image
    alpha = Image.open(path).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    w, h = box[0] - 2 * bold, box[1] - 2 * bold
    scale = min(w / alpha.width, h / alpha.height)
    alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                         Image.LANCZOS)
    m = np.asarray(alpha) > 150
    if bold:
        m = program_mark.dilate(np.pad(m, bold), bold)
    return m


def _corner(mask, size: tuple[int, int]):
    """`mask` in the bottom-right corner of a `size` (w, h) canvas."""
    import numpy as np
    canvas = np.zeros((size[1], size[0]), bool)
    canvas[size[1] - mask.shape[0]:, size[0] - mask.shape[1]:] = mask
    return canvas


def _composed(stem: str, out: Path, size: tuple[int, int]):
    """A composed icon: the base part in the bottom-right corner and the added
    part at the top left, cut out of the base by a 2 px gap."""
    import numpy as np
    w, h = size
    if stem in ("swimup", "swimdown"):
        # The waves across the bottom, the arrow centred above them.
        base = _mask(out / f"_{stem}_base.png", (w - 4, 16))
        add = _mask(out / f"_{stem}_add.png", (20, 20))
        canvas = _corner(base, size)
        x0 = w - base.shape[1] + (base.shape[1] - add.shape[1]) // 2
        canvas[0:add.shape[0], x0:x0 + add.shape[1]] = add
        return canvas
    base_box, add_box = {"nextweapon": ((34, 26), (16, 16))}.get(stem, ((26, 26), (14, 20)))
    base = _mask(out / f"_{stem}_base.png", base_box)
    add = _mask(out / f"_{stem}_add.png", add_box)
    canvas = _corner(base, size)
    a = np.zeros((h, w), bool)
    x0 = w - base.shape[1] - (0 if stem == "nextweapon" else min(8, w - base.shape[1]))
    a[0:add.shape[0], x0:x0 + add.shape[1]] = add
    return (canvas & ~program_mark.dilate(a, 2)) | a


def build(out: Path, stems, sizes: dict) -> None:
    """Render `stems` (names from CATALOGUE or COMPOSED) into `out`, each a flat
    1-bit silhouette drawn at exactly its key area (`sizes`, default 40 x 40)
    so the generator places it 1:1."""
    plain = {s: CATALOGUE[s] for s in stems if s in CATALOGUE}
    parts = {}
    for s in stems:
        if s in COMPOSED:
            parts[f"_{s}_base"], parts[f"_{s}_add"] = COMPOSED[s]
    cnc.render({**plain, **parts}, out)
    for stem, spec in plain.items():
        size = sizes.get(stem, (40, 40))
        m = _mask(out / f"{stem}.png", _box(stem, spec, size), BOLD.get(stem, 0))
        cnc._save_mask(_corner(m, size), out / f"{stem}.png")
    for stem in stems:
        if stem in COMPOSED:
            cnc._save_mask(_composed(stem, out, sizes.get(stem, (40, 40))), out / f"{stem}.png")
    for part in parts:
        (out / f"{part}.png").unlink()
    print(f"  {len(plain)} key icons drawn flat, {len(stems) - len(plain)} composed")


def own_icon_mark(path: Path, url: str, crop, cut: int, dark: bool = False,
                  frame: int | None = None, box=(40, 40)) -> None:
    """An ESC mark cut from a program's own icon: the part `crop` (left, top,
    right, bottom; None for the whole icon) of the icon at `url`, box-filtered
    to fit `box`, lit where the grey level is above `cut` (below it with
    `dark`). `frame` selects one size of an .ico file."""
    import numpy as np
    from PIL import Image
    im = Image.open(io.BytesIO(_get(url)))
    if frame:
        im.size = (frame, frame)
    im = im.convert("RGBA")
    if crop:
        im = im.crop(crop)
    scale = min(box[0] / im.width, box[1] / im.height)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.BOX)
    rgba = np.asarray(im).astype(int)
    grey = (rgba[..., 0] * 299 + rgba[..., 1] * 587 + rgba[..., 2] * 114) // 1000
    solid = rgba[..., 3] > 128
    cnc._save_mask(solid & ((grey < cut) if dark else (grey > cut)), path)
    print(f"  {path.name}  <- {url.rsplit('/', 1)[1]} ({im.width} x {im.height})")


def wordmark(path: Path, lines, font_url: str = FONT_URL, threshold: int = MARK_THRESHOLD) -> None:
    """A wordmark over the whole 72x40 cell: `lines` at the largest one size at
    which each fits 70 px wide and all, MARK_GAP apart, fit 38 px high. Drawn
    at MARK_SS times the size and box-filtered down."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    w, h, ss = 72, 40, MARK_SS
    gap = MARK_GAP * ss
    font_path = str(cnc._font(font_url))
    for px in range(400, 40, -4):
        font = ImageFont.truetype(font_path, px)
        boxes = [font.getbbox(line) for line in lines]
        height = sum(b[3] - b[1] for b in boxes) + gap * (len(boxes) - 1)
        if all(b[2] - b[0] <= (w - 2) * ss for b in boxes) and height <= (h - 2) * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    draw = ImageDraw.Draw(im)
    y = (h * ss - height) // 2
    for line, box in zip(lines, boxes):
        draw.text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                  line, font=font, fill=255)
        y += box[3] - box[1] + gap
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > threshold, path)
    print(f"  {path.name}  <- {' / '.join(lines)} ({px / ss:.1f} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    build(out, STEMS, SIZES)
    own_icon_mark(out / "program.png", GZDOOM_ICON, GZDOOM_CROP, GZDOOM_CUT, frame=256)
    wordmark(out / "program_uzdoom.png", ("UZ", "Doom"))
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
