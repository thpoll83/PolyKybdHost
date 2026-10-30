#!/usr/bin/env python3
"""Fetch + render the RimWorld icons (reproducible).

The key icons are flat 1-bit silhouettes, as in the Age of Empires II and
Warcraft III sets: game shapes from game-icons.net (CC BY 3.0, credit per
author), interface shapes from Microsoft Fluent UI System Icons (MIT, the
filled style) and one Material Symbol (Apache-2.0). The game-speed, pause and colonist-cycle icons are drawn here.
SOURCES.md credits each. The ESC mark is RIM over WORLD set in Orbitron Bold
(SIL OFL 1.1); the game's logo art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/rimworld/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_icons, icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402


def fl(folder: str) -> str:
    """The filled 24 px Fluent asset of `folder`."""
    return f"{folder}/SVG/ic_fluent_{icon_fetch._snake(folder)}_24_filled.svg"


ICONS = {
    # Main tabs (Tab, F1 to F9)
    "architect": "gi:delapouite/brick-wall",
    "work": "gi:lorc/flat-hammer",
    "schedule": fl("Clock"),
    "assign": "gi:delapouite/t-shirt",
    "animals": "gi:skoll/pig",
    "wildlife": "gi:caro-asercion/deer",
    "research": "gi:lorc/erlenmeyer",
    "quests": fl("Flag"),
    "world": "gi:delapouite/earth-africa-europe",
    "history": "gi:lorc/open-book",
    # Screenshots (F10, F11)
    "screenshot": fl("Camera"),
    "screenshotmode": fl("Eye Off"),
    # Camera
    "panup": fl("Arrow Up"),
    "zoomin": fl("Zoom In"),
    "zoomout": fl("Zoom Out"),
    "rotateleft": fl("Arrow Counterclockwise"),
    "rotateright": fl("Arrow Clockwise"),
    # Map displays
    "roomstats": "ms:bed",
    "beauty": fl("Sparkle"),
    "search": fl("Search"),
    # Commands with one meaning whatever is selected
    "draft": "gi:lorc/crossed-sabres",
    "forbid": fl("Prohibited"),
    "power": fl("Power"),
    "cancel": fl("Dismiss Circle"),
    "deconstruct": "gi:quoting/damaged-house",
    # Drawn into the colonist-cycle icons by colonists()
    "_person": "gi:delapouite/person",
}

# Key area of each icon, from rimworld.yaml; the default is 40 x 40.
SIZES = {"work": (34, 40), "schedule": (34, 40), "assign": (34, 40), "animals": (30, 40),
         "wildlife": (34, 40), "research": (34, 40), "quests": (34, 40), "world": (34, 40)}
# Solid or wide icons that read heavier than the rest: drawn in a smaller box
# in the bottom-right corner of their key area.
INK = {"schedule": (30, 30), "screenshot": (30, 30), "screenshotmode": (32, 32),
       "zoomin": (30, 30), "zoomout": (30, 30), "search": (30, 30), "forbid": (30, 30),
       "power": (30, 30), "cancel": (30, 30), "rotateleft": (32, 32), "rotateright": (32, 32),
       "panup": (30, 34), "world": (30, 30), "quests": (30, 34),
       "beauty": (32, 32)}

# The ESC mark is set in Orbitron (SIL OFL 1.1), its Bold instance.
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/orbitron/Orbitron%5Bwght%5D.ttf")
MARK_SS = 8                 # supersampling factor for the ESC mark
MARK_THRESHOLD = 100        # grey level (0..255) from which a box-filtered pixel is lit

# The drawn speed family: a right-pointing triangle TRI_W x TRI_H, centred on the
# 40 px height, and pause bars of the same height.
TRI_W, TRI_H = 13, 24
SIGN, BAR = 11, 3           # the plus / minus beside the Home / End triangle


def _svg(spec: str) -> bytes:
    if spec.startswith("gi:"):
        return icon_fetch._get(game_icons.URL.format(spec[3:]))
    return icon_fetch._fetch_svg(spec)[0]


def render(out: Path) -> None:
    import cairosvg
    out.mkdir(parents=True, exist_ok=True)
    for stem, spec in ICONS.items():
        png = cairosvg.svg2png(bytestring=_svg(spec), output_width=256, output_height=256)
        (out / f"{stem}.png").write_bytes(png)
        print(f"  {stem}.png  <- {spec}")


def _alpha_mask(path: Path, box: tuple[int, int]):
    """The icon's ink, cropped and scaled to fit `box`, as a bool array."""
    import numpy as np
    from PIL import Image
    alpha = Image.open(path).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    scale = min(box[0] / alpha.width, box[1] / alpha.height)
    alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                         Image.LANCZOS)
    return np.asarray(alpha) > 150


def _place(mask, size=(40, 40), dy=0):
    """`mask` in the bottom-right corner of a canvas of `size` (w, h), raised by dy."""
    import numpy as np
    canvas = np.zeros((size[1], size[0]), bool)
    h, w = mask.shape
    canvas[size[1] - h - dy:size[1] - dy, size[0] - w:] = mask
    return canvas


def flat_icons(out: Path) -> None:
    """Every fetched key icon as a flat 1-bit silhouette, drawn at exactly its
    key area so the generator places it 1:1. The icons in INK fill a smaller box
    in the bottom-right corner of that area."""
    for stem in ICONS:
        if stem.startswith("_"):
            continue
        size = SIZES.get(stem, (40, 40))
        cnc._save_mask(_place(_alpha_mask(out / f"{stem}.png", INK.get(stem, size)), size),
                       out / f"{stem}.png")
    print(f"  {len(ICONS) - 1} key icons drawn flat")


def pan(out: Path) -> None:
    """panleft/panright/pandown.png: the Fluent up arrow turned a quarter at a
    time. All four are centred on the height."""
    import numpy as np
    from PIL import Image
    up = np.asarray(Image.open(out / "panup.png").getchannel("A")) > 0
    m = up[:, up.any(axis=0)]
    m = m[m.any(axis=1)]
    for stem, k in (("panleft", 1), ("pandown", 2), ("panright", 3)):
        r = np.rot90(m, k)
        cnc._save_mask(_place(r, dy=(40 - r.shape[0]) // 2), out / f"{stem}.png")
    cnc._save_mask(_place(m, dy=(40 - m.shape[0]) // 2), out / "panup.png")
    print("  panleft.png, pandown.png, panright.png  <- panup.png turned")


def _triangle(w=TRI_W, h=TRI_H):
    import numpy as np
    yy, xx = np.mgrid[0:h, 0:w]
    half = (h - 1) / 2
    return np.abs(yy - half) <= half * (1 - (xx + 0.5) / w) + 0.5


def _row(parts, gap=0):
    """The masks side by side, `gap` px apart, vertically centred on each other."""
    import numpy as np
    h = max(p.shape[0] for p in parts)
    w = sum(p.shape[1] for p in parts) + gap * (len(parts) - 1)
    c = np.zeros((h, w), bool)
    x = 0
    for p in parts:
        y = (h - p.shape[0]) // 2
        c[y:y + p.shape[0], x:x + p.shape[1]] = p
        x += p.shape[1] + gap
    return c


def speeds(out: Path) -> None:
    """speed1..3.png (one to three triangles), pause.png (two bars of the same
    height), faster.png and slower.png (a plus or a minus beside one triangle).
    All 40x40, centred on the height."""
    import numpy as np
    t = _triangle()
    for n in (1, 2, 3):
        cnc._save_mask(_place(_row([t] * n), dy=(40 - TRI_H) // 2), out / f"speed{n}.png")
    bar = np.ones((TRI_H, 5), bool)
    cnc._save_mask(_place(_row([bar, bar], gap=5), dy=(40 - TRI_H) // 2), out / "pause.png")
    minus = np.zeros((SIGN, SIGN), bool)
    minus[SIGN // 2 - BAR // 2:SIGN // 2 + BAR // 2 + 1, :] = True
    plus = minus | minus.T
    for stem, sign in (("faster", plus), ("slower", minus)):
        cnc._save_mask(_place(_row([sign, t], gap=3), dy=(40 - TRI_H) // 2), out / f"{stem}.png")
    print("  speed1..3.png, pause.png, faster.png, slower.png  <- drawn")


def colonists(out: Path) -> None:
    """prevcolonist.png and nextcolonist.png: a person with a small triangle on
    the side the selection moves to."""
    import numpy as np
    person = _alpha_mask(out / "_person.png", (18, 40))
    t = _triangle(9, 16)
    for stem, parts in (("prevcolonist", [np.fliplr(t), person]), ("nextcolonist", [person, t])):
        cnc._save_mask(_place(_row(parts, gap=3)), out / f"{stem}.png")
    print("  prevcolonist.png, nextcolonist.png  <- _person.png + a drawn triangle")


def _mark_line(font, text: str, width: int):
    """`text` in `font` at the size whose ink is `width` px wide, as a bool mask."""
    import numpy as np
    from PIL import Image, ImageDraw
    ss = MARK_SS
    ref = font.font_variant(size=400)
    b = ref.getbbox(text)
    f = font.font_variant(size=round(400 * width * ss / (b[2] - b[0])))
    f.set_variation_by_name("Bold")
    b = f.getbbox(text)
    im = Image.new("L", (b[2] - b[0] + 2 * ss, b[3] - b[1] + 2 * ss), 0)
    ImageDraw.Draw(im).text((ss - b[0], ss - b[1]), text, font=f, fill=255)
    w, h = im.width // ss, im.height // ss
    m = np.asarray(im.crop((0, 0, w * ss, h * ss)).resize((w, h), Image.BOX)) > MARK_THRESHOLD
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def program(out: Path) -> None:
    """program.png: RIM (40 px wide) over WORLD (70 px wide), 4 px apart,
    centred on the whole 72x40 cell. Left as-is when committed."""
    import numpy as np
    from PIL import ImageFont
    dest = out / "program.png"
    if dest.exists():
        print("  program.png  <- committed asset (left as-is)")
        return
    font = ImageFont.truetype(str(cnc._font(FONT_URL)), 400)
    font.set_variation_by_name("Bold")
    lines = [_mark_line(font, "RIM", 40), _mark_line(font, "WORLD", 70)]
    gap = 4
    canvas = np.zeros((40, 72), bool)
    y = (40 - sum(m.shape[0] for m in lines) - gap) // 2
    for m in lines:
        x = (72 - m.shape[1]) // 2
        canvas[y:y + m.shape[0], x:x + m.shape[1]] = m
        y += m.shape[0] + gap
    cnc._save_mask(canvas, dest)
    print("  program.png  <- RIM / WORLD (Orbitron Bold)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    render(out)
    colonists(out)
    flat_icons(out)
    pan(out)
    speeds(out)
    program(out)
    (out / "_person.png").unlink()
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
