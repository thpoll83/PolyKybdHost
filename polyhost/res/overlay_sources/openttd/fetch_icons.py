#!/usr/bin/env python3
"""Fetch + render the OpenTTD icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0)
and game-icons.net (CC BY 3.0), as in the Warcraft III set. The transparency
keys (Ctrl+1 to Ctrl+9) show the object with a checkered inside, the
invisibility keys (Ctrl+Shift+1 to Ctrl+Shift+8) the object struck through.
SOURCES.md credits each icon. The ESC mark is OpenTTD set in Alfa Slab One
(SIL OFL 1.1); the game's own logo and the OpenGFX graphics are not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/openttd/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402

ICONS = {
    # Main toolbar, F1 to F12
    "pause": "fa:pause",
    "settings": "fa:gear",
    "saveload": "fa:floppy-disk",
    "smallmap": "fa:map",
    "towns": "fa:city",
    "subsidies": "fa:hand-holding-dollar",
    "finances": "fa:sack-dollar",
    "companies": "fa:building",
    "graphs": "fa:chart-line",
    "league": "fa:trophy",
    "industries": "fa:industry",
    # Main toolbar, Shift+F1 to Shift+F12
    "trainlist": "fa:train",
    "roadvehlist": "fa:bus",
    "shiplist": "fa:ship",
    "aircraftlist": "fa:plane",
    "buildroad": "fa:road",
    "builddocks": "fa:anchor",
    "buildairport": "fa:plane-departure",
    "buildtrees": "fa:seedling",
    "music": "fa:music",
    # View
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "centerzoom": "fa:magnifying-glass-location",
    "viewport": "fa:window-restore",
    "transparency": "fa:ghost",
    "transparencybar": "fa:sliders",
    "refresh": "fa:arrows-rotate",
    # Landscaping
    "landscaping": "fa:mountain-sun",
    # Windows and messages
    "closewindows": "fa:rectangle-xmark",
    "closenews": "fa:newspaper",
    "deletenews": "fa:trash-can",
    "console": "fa:terminal",
    # Game
    "screenshot": "fa:camera",
    "quit": "fa:power-off",
    "abandon": "fa:door-open",
    "cheats": "fa:wand-magic-sparkles",
    # Chat
    "chat": "fa:comment",
    "chatall": "fa:bullhorn",
    "chatcompany": "fa:comments",
    "chatserver": "fa:server",
}

# Ctrl+1 to Ctrl+9 (transparency) and Ctrl+Shift+1 to Ctrl+Shift+8
# (invisibility), in the order of TransparencyOption in src/transparency.h.
OBJECTS = {
    "1": ("signs", "fa:signs-post"),
    "2": ("trees", "fa:tree"),
    "3": ("houses", "fa:house"),
    "4": ("industrybuildings", "fa:industry"),
    "5": ("companybuildings", "fa:warehouse"),
    "6": ("bridges", "fa:bridge"),
    "7": ("structures", "fa:tower-broadcast"),
    "8": ("catenary", "fa:bolt"),
    "9": ("loading", "fa:percent"),
}
INVISIBLE = "12345678"                       # loading indicators have no invisibility key

# E (level land); Q and W are drawn by terrain().
TERRAIN = {"_level": "fa:arrows-down-to-line"}

# Key area of each icon, from openttd.yaml; the default is 40 x 40.
SIZES = {"pause": (34, 40), "settings": (34, 40), "saveload": (34, 40),
         "smallmap_f4": (30, 40), "towns": (30, 40), "subsidies": (30, 40), "stations": (30, 40),
         "finances": (34, 40), "trainlist": (34, 40), "roadvehlist": (34, 40),
         "shiplist": (34, 40), "aircraftlist": (30, 40), "buildroad": (34, 40)}
# Icons used on a second key with a narrower area: stem -> (source stem, area, ink box).
NARROW = {"smallmap_f4": ("smallmap", (30, 40), (30, 30)),
          "zoomin_f5": ("zoomin", (30, 40), (26, 26)),
          "zoomout_f6": ("zoomout", (30, 40), (26, 26))}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"saveload": (30, 30), "settings": (30, 30), "pause": (24, 30), "smallmap": (34, 34),
       "zoomin": (30, 30), "zoomout": (30, 30), "centerzoom": (30, 30), "music": (30, 30),
       "screenshot": (32, 30), "closewindows": (34, 30), "closenews": (34, 30),
       "deletenews": (28, 32), "console": (34, 30), "quit": (32, 32), "chat": (34, 34),
       "chatcompany": (36, 32), "chatserver": (30, 34), "viewport": (34, 34)}

# The ESC mark is set in Alfa Slab One (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/alfaslabone/AlfaSlabOne-Regular.ttf")
SS = 8                                       # supersampling factor for drawn icons
MARK_THRESHOLD = 110                         # grey level (0..255) from which a mark pixel is lit


def _alpha(path: Path):
    """The icon's alpha, cropped to its ink."""
    from PIL import Image
    a = Image.open(path).convert("RGBA").getchannel("A")
    return a.crop(a.getbbox())


def _fit(path: Path, box: tuple[int, int]):
    """The icon's ink scaled to fit `box` (w, h), 1-bit."""
    import numpy as np
    from PIL import Image
    a = _alpha(path)
    k = min(box[0] / a.width, box[1] / a.height)
    a = a.resize((max(1, round(a.width * k)), max(1, round(a.height * k))), Image.LANCZOS)
    return np.asarray(a) > 150


def _corner(m, size: tuple[int, int]):
    """`m` in the bottom-right corner of a `size` (w, h) canvas."""
    import numpy as np
    canvas = np.zeros((size[1], size[0]), bool)
    canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
    return canvas


def erode(m, n: int):
    return ~program_mark.dilate(~m, n)


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key area
    so the generator places it 1:1. The icons in INK fill a smaller box in the
    bottom-right corner of that area. The icons in NARROW are drawn a second
    time for a key with a narrower area."""
    for stem, (src, size, box) in NARROW.items():
        cnc._save_mask(_corner(_fit(out / f"{src}.png", box), size), out / f"{stem}.png")
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        m = _fit(out / f"{stem}.png", INK.get(stem, size))
        cnc._save_mask(_corner(m, size), out / f"{stem}.png")
    print(f"  {len(ICONS) + len(NARROW)} key icons drawn flat")


def _transparent(m):
    """The object as an outline with every second pixel lit inside."""
    import numpy as np
    yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]]
    inner = erode(m, 2)
    return (m & ~inner) | (inner & ((xx + yy) % 2 == 0))


def _struck(m):
    """The object with a 3 px bar from the top-left to the bottom-right corner,
    2 px clear on both sides."""
    import numpy as np
    H, W = m.shape
    yy, xx = np.mgrid[0:H, 0:W]
    # Distance from the line through (0, 0) and (W-1, H-1).
    d = np.abs((H - 1) * xx - (W - 1) * yy) / np.hypot(H - 1, W - 1)
    bar = d <= 1.5
    return (m & ~(d <= 3.5)) | bar


def objects(out: Path) -> None:
    """transp<N>.png (Ctrl+N) and invis<N>.png (Ctrl+Shift+N)."""
    for digit, (name, _spec) in OBJECTS.items():
        m = _corner(_fit(out / f"_{name}.png", (36, 34)), (40, 40))
        cnc._save_mask(_transparent(m), out / f"transp{digit}.png")
        if digit in INVISIBLE:
            cnc._save_mask(_struck(m), out / f"invis{digit}.png")
    print(f"  transp1..9.png, invis1..8.png  <- {len(OBJECTS)} objects")


def _draw(shapes, size=(40, 40)):
    """Polygons [(x, y), ...] in key pixels, drawn at SS times the size and
    box-filtered down, 1-bit."""
    import numpy as np
    from PIL import Image, ImageDraw
    im = Image.new("L", (size[0] * SS, size[1] * SS), 0)
    d = ImageDraw.Draw(im)
    for poly in shapes:
        d.polygon([(x * SS, y * SS) for x, y in poly], fill=255)
    return np.asarray(im.resize(size, Image.BOX)) > 110


def _arrow(cx, top, bottom, up=True, shaft=4, head=16, head_h=9):
    """A vertical arrow from `top` to `bottom`, pointing up or down."""
    h = shaft / 2
    if up:
        return [(cx, top), (cx + head / 2, top + head_h), (cx + h, top + head_h),
                (cx + h, bottom), (cx - h, bottom), (cx - h, top + head_h),
                (cx - head / 2, top + head_h)]
    return [(cx, bottom), (cx + head / 2, bottom - head_h), (cx + h, bottom - head_h),
            (cx + h, top), (cx - h, top), (cx - h, bottom - head_h), (cx - head / 2, bottom - head_h)]


def terrain(out: Path) -> None:
    """raise.png (W): ground with a hill and an up arrow over it. lower.png (Q):
    ground with a pit and a down arrow into it. level.png (E): the
    arrows-down-to-line icon."""
    hill = [(0, 40), (0, 32), (9, 32), (15, 23), (25, 23), (31, 32), (40, 32), (40, 40)]
    pit = [(0, 40), (0, 25), (9, 25), (15, 33), (25, 33), (31, 25), (40, 25), (40, 40)]
    cnc._save_mask(_draw([hill, _arrow(20, 1, 19, up=True)]), out / "raise.png")
    cnc._save_mask(_draw([pit, _arrow(20, 1, 21, up=False)]), out / "lower.png")
    cnc._save_mask(_corner(_fit(out / "_level.png", (34, 34)), (40, 40)), out / "level.png")
    print("  raise.png, lower.png drawn; level.png  <- fa:arrows-down-to-line")


def station(out: Path) -> None:
    """stations.png (F7): the train-subway icon under a roof, 30 x 40."""
    train = _corner(_fit(out / "_station_train.png", (22, 24)), (30, 40))
    roof = _draw([[(1, 13), (15, 3), (29, 13), (29, 16), (1, 16)]], (30, 40))
    cnc._save_mask(train | roof, out / "stations.png")
    print("  stations.png  <- fa:train-subway under a drawn roof")


def rails(out: Path) -> None:
    """buildrail.png (Shift+F7): the railway track turned upright, 30 x 40.
    autorail.png (A): the track turned 45 degrees, as the autorail tool lays it."""
    from PIL import Image
    a = Image.open(out / "_railway.png").convert("RGBA").getchannel("A")
    a = a.crop(a.getbbox())
    tmp = out / "_railway_rot.png"
    for stem, angle, size in (("buildrail", 90, (30, 40)), ("autorail", 45, (40, 40))):
        r = a.rotate(angle, resample=Image.BICUBIC, expand=True)
        Image.merge("RGBA", (r, r, r, r)).save(tmp)
        cnc._save_mask(_corner(_fit(tmp, size), size), out / f"{stem}.png")
    tmp.unlink()
    print("  buildrail.png, autorail.png  <- gi:delapouite/railway turned 90 and 45 degrees")


def _badge_plus(size=11, bar=3):
    import numpy as np
    p = np.zeros((size, size), bool)
    c = size // 2
    p[c - bar // 2:c + bar // 2 + 1, :] = True
    p[:, c - bar // 2:c + bar // 2 + 1] = True
    return p


def _badge_text(text: str, cap: int = 9):
    """`text` in DejaVu Sans Bold with a cap height of `cap` px, 1-bit."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font_path = cnc._font(cnc.DIGIT_FONT_URL)
    ref = ImageFont.truetype(str(font_path), 200).getbbox("1")
    px = round(200 * cap * SS / (ref[3] - ref[1]))
    f = ImageFont.truetype(str(font_path), px)
    box = f.getbbox(text)
    im = Image.new("L", (box[2] - box[0], box[3] - box[1]), 0)
    ImageDraw.Draw(im).text((-box[0], -box[1]), text, font=f, fill=255)
    im = im.resize((max(1, round(im.width / SS)), max(1, round(im.height / SS))), Image.BOX)
    return np.asarray(im) > 110


def screenshots(out: Path) -> None:
    """screenshotzoom.png (Ctrl+P, zoomed in): the camera with a plus above it.
    screenshotdefault.png (Ctrl+D, default zoom): the camera with 1:1 above it."""
    cam = _corner(_fit(out / "_camera.png", (30, 24)), (40, 40))
    for stem, badge in (("screenshotzoom", _badge_plus()), ("screenshotdefault", _badge_text("1:1"))):
        m = cam.copy()
        h, w = badge.shape
        x = 40 - 15 - w // 2                  # centred over the camera
        m[2:2 + h, x:x + w] |= badge
        cnc._save_mask(m, out / f"{stem}.png")
    print("  screenshotzoom.png, screenshotdefault.png  <- fa:camera + a plus or 1:1")


def close_all(out: Path) -> None:
    """closeall.png (Shift+Delete): the closed window twice, the back copy up
    and to the right, 2 px clear around the front copy."""
    import numpy as np
    w = _fit(out / "_window.png", (30, 24))
    h, ww = w.shape
    back = np.zeros((40, 40), bool)
    front = np.zeros((40, 40), bool)
    back[40 - h - 9:40 - 9, 40 - ww:] = w
    front[40 - h:, 40 - ww - 8:40 - 8] = w
    cnc._save_mask((back & ~program_mark.dilate(front, 2)) | front, out / "closeall.png")
    print("  closeall.png  <- fa:rectangle-xmark twice")


def _mark_font(px: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(cnc._font(FONT_URL)), px)


def program(out: Path) -> None:
    """program.png: "Open" over a larger "TTD", centred on the whole 72x40
    cell. Drawn at SS times the size and box-filtered down."""
    import numpy as np
    from PIL import Image, ImageDraw
    w, h, ss = program_mark.W, program_mark.H, SS
    gap = 3 * ss
    for cap in range(20, 5, -1):
        ref = _mark_font(200).getbbox("H")
        px = round(200 * cap * ss / (ref[3] - ref[1]))
        top, bottom = _mark_font(round(px * 0.6)), _mark_font(px)
        tb, bb = top.getbbox("Open"), bottom.getbbox("TTD")
        height = (tb[3] - tb[1]) + gap + (bb[3] - bb[1])
        if bb[2] - bb[0] <= (w - 2) * ss and height <= (h - 2) * ss:
            break
    y = (h * ss - height) // 2
    canvas = np.zeros((h, w), bool)
    for text, font, box in (("Open", top, tb), ("TTD", bottom, bb)):
        im = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(im).text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                                text, font=font, fill=255)
        canvas |= np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD
        y += box[3] - box[1] + gap
    cnc._save_mask(canvas, out / "program.png")
    print(f"  program.png  <- Open / TTD (Alfa Slab One, cap {cap} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **TERRAIN, **{f"_{n}": s for n, s in OBJECTS.values()},
                "_camera": "fa:camera", "_window": "fa:rectangle-xmark",
                "_station_train": "fa:train-subway", "_railway": "gi:delapouite/railway"}, out)
    flat_icons(out)
    station(out)
    rails(out)
    objects(out)
    terrain(out)
    screenshots(out)
    close_all(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
