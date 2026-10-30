#!/usr/bin/env python3
"""Fetch + render the StarCraft II icons (reproducible).

The key icons are flat silhouettes from game-icons.net (CC BY 3.0), Font
Awesome Free (CC BY 4.0) and Material Design Icons (Apache-2.0), as in the
Warcraft III set. The control groups are game-icons.net units, drawn once at
full height, with a modifier mark from game_assets/dither.py (the same marks
the runtime reader of the StarCraft files draws). The health-bar keys are
drawn here: a bar over a word. SOURCES.md credits each icon. The ESC mark is
STARCRAFT II set in Teko SemiBold (SIL OFL 1.1); the game's logo art is not
used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/starcraft2/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_icons  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.warcraft3 import fetch_icons as wc3  # noqa: E402
from polyhost.services.game_assets import dither  # noqa: E402

ICONS = {
    # Selection
    "idleworker": "gi:delapouite/miner",
    "army": "fa:person-military-rifle",
    "bases": "fa:industry",
    "lastalert": "fa:triangle-exclamation",
    "subgroupnext": "fa:forward-step",
    "subgroupprev": "fa:backward-step",
    # Camera
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "zoomtoggle": "mdi:magnify-expand",
    "camdefault": "mdi:image-filter-center-focus",
    "rotatecw": "fa:rotate-right",
    "rotateccw": "fa:rotate-left",
    "follow": "fa:crosshairs",
    # Chat
    "chat": "gi:delapouite/chat-bubble",
    "chatall": "gi:delapouite/megaphone",
    "chatallies": "gi:lorc/conversation",
    "chatplayer": "fa:user",
    "voice": "fa:microphone",
    # Interface
    "ping": "mdi:map-marker-radius",
    "alliancecolours": "fa:palette",
    "terrain": "fa:mountain",
    "fps": "fa:gauge-high",
    "pause": "fa:pause",
    "quicksave": "fa:floppy-disk",
    "music": "fa:music",
    "sound": "fa:volume-high",
    "screenshot": "fa:camera",
    "fullscreen": "fa:expand",
    # Menus
    "achievements": "fa:trophy",
    "gamemenu": "fa:bars",
    "messagelog": "gi:delapouite/notebook",
    "help": "fa:circle-question",
    "social": "fa:user-group",
    "resources": "fa:gem",
}

# Control groups: one unit per digit, drawn once at full height. A neutral
# science-fiction set; the runtime reader replaces it with the units of the
# race chosen in the settings when the StarCraft files are on the machine.
GROUP_UNITS = {
    "1": "lorc/space-suit",
    "2": "delapouite/walking-turret",
    "3": "lorc/tank",
    "4": "delapouite/jet-fighter",
    "5": "delapouite/spaceship",
    "6": "lorc/scarab-beetle",
    "7": "lorc/hydra",
    "8": "delapouite/ufo",
    "9": "lorc/alien-skull",
    "0": "delapouite/drill",
}
# The mark each modifier adds to a group (dither.with_plus / with_mark):
# Ctrl create, Shift add, Alt create and steal, Shift+Alt add and steal.
GROUP_MARKS = {"groupnew": "plus", "groupadd": "ring", "groupsteal": "box", "groupaddsteal": "disc"}

# Key area of each icon, from starcraft2.yaml; the default is 40 x 40.
SIZES = {"idleworker": (34, 40), "army": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"lastalert": (34, 34), "quicksave": (34, 34), "help": (34, 34), "chat": (34, 34),
       "zoomin": (30, 30), "zoomout": (30, 30), "zoomtoggle": (32, 32), "music": (30, 30),
       "screenshot": (30, 30), "pause": (26, 30), "subgroupnext": (30, 30),
       "subgroupprev": (30, 30), "fullscreen": (30, 30), "chatplayer": (30, 34),
       "voice": (30, 34), "rotatecw": (32, 32), "rotateccw": (32, 32)}

# Camera locations (F5 to F8): a film camera with the number cut out of its body.
CAMERA = "fa:video"
CAMERA_SIZE = (34, 40)

# Health bars (' \ [ ]): a bar over a word, all words at one size.
HP_WORDS = {"hpall": "ALL", "hpown": "OWN", "hpallies": "ALLY", "hpenemies": "ENEMY"}
HP_FONT = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")

# The ESC mark is set in Teko (SIL OFL 1.1), its SemiBold instance.
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/teko/Teko%5Bwght%5D.ttf")
MARK_SS = 8                                     # supersampling factor for the ESC mark
# Grey level (0..255) from which a box-filtered ESC mark pixel is lit, per line.
MARK_THRESHOLD = {"STARCRAFT": 80, "II": 110}


def groups(out: Path) -> None:
    """group<N>.png (select) and one marked copy per modifier (GROUP_MARKS)."""
    for digit in GROUP_UNITS:
        g = wc3._single(out / f"_unit{digit}.png")
        canvas = _cell(g)
        aoe2._save_cell(canvas, out / f"group{digit}.png")
        for stem, mark in GROUP_MARKS.items():
            marked = dither.with_plus(canvas) if mark == "plus" else dither.with_mark(canvas, mark)
            aoe2._save_cell(marked, out / f"{stem}{digit}.png")
        print(f"  group{digit}.png and {len(GROUP_MARKS)} marked copies  <- _unit{digit}.png")


def _cell(mask):
    """`mask` bottom-right in a GROUP_W x GROUP_H canvas, so a mark has the
    whole cell to sit in."""
    import numpy as np
    canvas = np.zeros((aoe2.GROUP_H, aoe2.GROUP_W), bool)
    h, w = mask.shape
    canvas[aoe2.GROUP_H - h:, aoe2.GROUP_W - w:] = mask
    return canvas


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key
    area so the generator places it 1:1. The icons in INK fill a smaller box
    in the bottom-right corner of that area."""
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        cnc._save_mask(_flat(out / f"{stem}.png", size, INK.get(stem, size)), out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def _flat(src: Path, size, box):
    import numpy as np
    from PIL import Image
    alpha = Image.open(src).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    scale = min(box[0] / alpha.width, box[1] / alpha.height)
    alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                         Image.LANCZOS)
    m = np.asarray(alpha) > 150
    canvas = np.zeros((size[1], size[0]), bool)
    canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
    return canvas


def _text(text: str, font):
    """`text` as a 1-bit mask cropped to its ink."""
    import numpy as np
    from PIL import Image, ImageDraw
    left, top, right, bottom = font.getbbox(text)
    im = Image.new("L", (right - left + 4, bottom - top + 4), 0)
    ImageDraw.Draw(im).text((2 - left, 2 - top), text, font=font, fill=255)
    m = np.asarray(im) > 110
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def cameras(out: Path) -> None:
    """camera<N>.png (F5 to F8: go to camera location N) and cameraset<N>.png
    (Ctrl: save it, with the plus at the top right)."""
    import numpy as np
    from PIL import ImageFont
    body = _flat(out / "_camera.png", CAMERA_SIZE, CAMERA_SIZE)
    ys, xs = np.nonzero(body)
    # The body is the solid part left of the lens: the columns lit over the full height.
    full = body.sum(axis=0) >= (ys.max() - ys.min() + 1) - 1
    bx0, bx1 = np.nonzero(full)[0].min(), np.nonzero(full)[0].max()
    by0, by1 = ys.min(), ys.max()
    for n in range(1, 5):
        for px in range(30, 6, -1):
            g = _text(str(n), ImageFont.truetype(str(cnc._font(cnc.DIGIT_FONT_URL)), px))
            if g.shape[0] <= by1 - by0 - 3 and g.shape[1] <= bx1 - bx0 - 3:
                break
        m = body.copy()
        y0 = by0 + (by1 - by0 + 1 - g.shape[0]) // 2
        x0 = bx0 + (bx1 - bx0 + 1 - g.shape[1]) // 2
        m[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] &= ~g
        cnc._save_mask(m, out / f"camera{n}.png")
        cnc._save_mask(dither.with_plus(m, top=True), out / f"cameraset{n}.png")
    print(f"  camera1..4.png, cameraset1..4.png  <- {CAMERA} with the number cut out")


def health_bars(out: Path) -> None:
    """hp*.png: a health bar, two thirds full, over a word. One font size for
    all four words, the largest at which ENEMY fits 40 px."""
    import numpy as np
    from PIL import ImageFont
    size = 40
    for px in range(30, 6, -1):
        font = ImageFont.truetype(str(HP_FONT), px)
        words = {stem: _text(word, font) for stem, word in HP_WORDS.items()}
        if max(m.shape[1] for m in words.values()) <= size:
            break
    for stem, word in words.items():
        m = np.zeros((size, size), bool)
        # The bar: a 2 px frame, 12 px high, two thirds filled.
        top, bh = 6, 12
        m[top:top + bh, 1:size - 1] = True
        m[top + 2:top + bh - 2, 3:size - 3] = False
        m[top + 4:top + bh - 4, 5:5 + (size - 10) * 2 // 3] = True
        wy = size - word.shape[0] - 2
        wx = (size - word.shape[1]) // 2
        m[wy:wy + word.shape[0], wx:wx + word.shape[1]] |= word
        cnc._save_mask(m, out / f"{stem}.png")
    print(f"  {', '.join(f'{s}.png' for s in HP_WORDS)}  <- a bar over the word "
          f"(Liberation Sans Bold {px} px)")


def _mark_font(px: int):
    from PIL import ImageFont
    f = ImageFont.truetype(str(cnc._font(FONT_URL)), px)
    f.set_variation_by_name("SemiBold")
    return f


def program(out: Path) -> None:
    """program.png: STARCRAFT at the largest size that fits 70 px, over a II
    1.5 times as tall, centred on the whole 72x40 cell. Drawn at MARK_SS times
    the size and box-filtered down."""
    import numpy as np
    from PIL import Image, ImageDraw
    w, h, ss = 72, 40, MARK_SS
    gap = 4 * ss
    for cap in range(16, 5, -1):
        ref = _mark_font(200).getbbox("H")
        px = round(200 * cap * ss / (ref[3] - ref[1]))
        top, bottom = _mark_font(px), _mark_font(round(px * 1.5))
        tb, bb = top.getbbox("STARCRAFT"), bottom.getbbox("II")
        height = (tb[3] - tb[1]) + gap + (bb[3] - bb[1])
        if tb[2] - tb[0] <= (w - 2) * ss and height <= (h - 2) * ss:
            break
    y = (h * ss - height) // 2
    canvas = np.zeros((h, w), bool)
    for text, font, box in (("STARCRAFT", top, tb), ("II", bottom, bb)):
        im = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(im).text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                                text, font=font, fill=255)
        canvas |= np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD[text]
        y += box[3] - box[1] + gap
    cnc._save_mask(canvas, out / "program.png")
    print(f"  program.png  <- STARCRAFT II (Teko SemiBold, cap {cap} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, "_camera": CAMERA}, out)
    game_icons.render({f"_unit{d}": n for d, n in GROUP_UNITS.items()}, out, render_px=256)
    flat_icons(out)
    groups(out)
    cameras(out)
    health_bars(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
