#!/usr/bin/env python3
"""Fetch + render the Factorio icons (reproducible).

The key icons are flat 1-bit silhouettes, as in the Warcraft III and Age of
Empires II sets: game shapes from game-icons.net (CC BY 3.0, credit per author
in SOURCES.md) and interface shapes from Material Symbols (Apache-2.0). The
quickbar keys, the wire modes and the zoom keys are drawn here with Liberation
Sans Bold. The ESC mark is FACTORIO set in Bebas Neue (SIL OFL 1.1); the game's
logo art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/factorio/fetch_icons.py

The fetched icons are re-rendered on every run. The drawn icons (quickbar
slots, wires, zoom, the ESC mark) are written only when their PNG is missing,
so a hand edit to a committed PNG is kept.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_icons, icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402

ICONS = {
    # Movement
    "up": "ms:north",
    "left": "ms:west",
    "down": "ms:south",
    "right": "ms:east",
    # Basic interaction
    "inventory": "gi:lorc/knapsack",
    "pipette": "gi:lorc/eyedropper",
    "rotate": "ms:rotate_right",
    "rotateback": "ms:rotate_left",
    "fliph": "ms:flip",
    "flipv": "ms:flip",                # turned by 90 degrees in ROTATE
    "pickup": "gi:lorc/grab",
    "drop": "ms:place_item",
    "raillayer": "gi:delapouite/rail-road",
    "weapon": "gi:john-colburn/pistol-gun",
    "shoot": "gi:delapouite/crosshair",
    "shootselected": "gi:sbed/targeted",
    "vehicle": "gi:delapouite/car-door",
    "chat": "gi:delapouite/chat-bubble",
    "quickbars": "ms:swap_vert",
    # Panels
    "map": "ms:map",
    "technology": "gi:lorc/round-bottom-flask",
    "production": "ms:bar_chart",
    "networks": "ms:hub",
    "library": "ms:library_books",
    "trains": "ms:train",
    "logistics": "gi:delapouite/cardboard-box-closed",
    "character": "ms:person",
    "crafting": "gi:lorc/gear-hammer",
    "back": "ms:arrow_back",
    "forward": "ms:arrow_forward",
    # Tools
    "artillery": "gi:lorc/cannon",
    "newblueprint": "ms:architecture",
    "newdecon": "gi:lorc/wrecking-ball",
    "newupgrade": "gi:delapouite/upgrade",
    "discharge": "gi:lorc/lightning-shield",
    "spidertron": "gi:carl-olsen/spider-alt",
    "exoskeleton": "gi:delapouite/leg-armor",
    "roboport": "gi:delapouite/delivery-drone",
    # Trains
    "connect": "ms:link",
    "disconnect": "ms:link_off",
    # Miscellaneous and debug
    "pause": "ms:pause",
    "debugsettings": "ms:bug_report",
    "basicdebug": "ms:analytics",
    "resetzoom": "ms:youtube_searched_for",
    "replaynext": "ms:switch_account",
    "hidegui": "ms:visibility_off",
}

# Turned clockwise by this many degrees after rendering.
ROTATE = {"flipv": 90}
# Key area of each icon, from factorio.yaml; the default is 40 x 40.
SIZES = {"logistics": (34, 40), "character": (34, 40), "debugsettings": (30, 40),
         "basicdebug": (30, 40)}
# Solid or wide icons that read heavier than the rest: drawn in a smaller box at
# the bottom right of their key area.
INK = {"chat": (34, 34), "inventory": (34, 40), "logistics": (34, 34),
       "pause": (30, 34), "trains": (34, 40),
       "up": (30, 40), "down": (30, 40), "left": (34, 30), "right": (34, 30)}
# The wire wrapped round both ends of the cable glyph in the wire-mode icons.
WIRE_GLYPH = "ms:cable"
# The magnifier the Shift+F9 icon is drawn round.
ZOOM_GLYPH = "ms:search"

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
# The ESC mark is set in Bebas Neue (SIL OFL 1.1).
MARK_FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
                 "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/bebasneue/BebasNeue-Regular.ttf")
MARK_SS = 8                                   # supersampling factor for the drawn icons
MARK_THRESHOLD = 90                           # grey level (0..255) from which a mark pixel is lit


def render(mapping: dict[str, str], out_dir: Path, render_px: int = 256) -> None:
    """`{stem: "gi:author/name" | "ms:name"}` into `out_dir` as RGBA PNGs."""
    import cairosvg
    out_dir.mkdir(parents=True, exist_ok=True)
    for stem, spec in mapping.items():
        if spec.startswith("gi:"):
            svg = icon_fetch._get(game_icons.URL.format(spec[3:]))
        else:
            svg, _, _ = icon_fetch._fetch_svg(spec)
        png = cairosvg.svg2png(bytestring=svg, output_width=render_px, output_height=render_px)
        (out_dir / f"{stem}.png").write_bytes(png)
        print(f"  {stem}.png  <- {spec}")


def flat_icons(out: Path) -> None:
    """Every fetched icon as a flat 1-bit silhouette, drawn at exactly its key
    area. The icons in INK fill a smaller box in the bottom-right corner."""
    import numpy as np
    from PIL import Image
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        box = INK.get(stem, size)
        alpha = Image.open(out / f"{stem}.png").convert("RGBA").getchannel("A")
        if stem in ROTATE:
            alpha = alpha.rotate(-ROTATE[stem], expand=True)
        alpha = alpha.crop(alpha.getbbox())
        scale = min(box[0] / alpha.width, box[1] / alpha.height)
        alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                             Image.LANCZOS)
        m = np.asarray(alpha) > 150
        canvas = np.zeros((size[1], size[0]), bool)
        canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def _glyph_mask(spec: str, box: tuple[int, int]):
    """A fetched glyph as a 1-bit mask that fits `box` (w, h)."""
    import io

    import cairosvg
    import numpy as np
    from PIL import Image
    svg, _, _ = icon_fetch._fetch_svg(spec)
    a = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg, output_width=256,
                                               output_height=256))).getchannel("A")
    a = a.crop(a.getbbox())
    k = min(box[0] / a.width, box[1] / a.height)
    a = a.resize((max(1, round(a.width * k)), max(1, round(a.height * k))), Image.LANCZOS)
    return np.asarray(a) > 150


def _text_mask(text: str, font, size: tuple[int, int], centre: tuple[float, float]):
    """`text` drawn MARK_SS times larger, box-filtered to `size`, centred on
    `centre` (x, y in output pixels, by the ink box)."""
    import numpy as np
    from PIL import Image, ImageDraw
    ss = MARK_SS
    im = Image.new("L", (size[0] * ss, size[1] * ss), 0)
    b = font.getbbox(text)
    x = centre[0] * ss - (b[2] - b[0]) / 2 - b[0]
    y = centre[1] * ss - (b[3] - b[1]) / 2 - b[1]
    ImageDraw.Draw(im).text((round(x), round(y)), text, font=font, fill=255)
    return np.asarray(im.resize(size, Image.BOX)) > 110


def _bold(cap_px: int):
    """Liberation Sans Bold at the size whose digit height is `cap_px` output
    pixels, for drawing at MARK_SS."""
    from PIL import ImageFont
    ref = ImageFont.truetype(BOLD, 200).getbbox("0")
    return ImageFont.truetype(BOLD, round(200 * cap_px * MARK_SS / (ref[3] - ref[1])))


def _missing(path: Path) -> bool:
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return False
    return True


def quickbar(out: Path) -> None:
    """slot<N>.png (1..0: use quickbar slot N) and bar<N>.png (Shift: select
    quickbar N), 40x40. A slot is a square with the number inside; a quickbar
    is the number over a row of four small slots. 0 is slot and quickbar 10."""
    import numpy as np
    digit_font = None
    for digit in "1234567890":
        n = "10" if digit == "0" else digit
        slot, bar = out / f"slot{digit}.png", out / f"bar{digit}.png"
        if not (_missing(slot) | _missing(bar)):
            continue
        digit_font = digit_font or _bold(18)
        if not slot.exists():
            m = np.zeros((40, 40), bool)
            m[1:39, 1:39] = True
            m[4:36, 4:36] = False                 # a 3 px frame
            m |= _text_mask(n, digit_font, (40, 40), (20, 20))
            cnc._save_mask(m, slot)
        if not bar.exists():
            m = _text_mask(n, digit_font, (40, 40), (20, 13))
            for i in range(4):                    # four 8x8 slots, 2 px apart
                x = 1 + i * 10
                m[30:38, x:x + 8] = True
                m[32:36, x + 2:x + 6] = False
            cnc._save_mask(m, bar)
        print(f"  slot{digit}.png, bar{digit}.png  <- drawn ({n})")


def wires(out: Path) -> None:
    """wirecopper.png, wirered.png, wiregreen.png (Alt+C, Alt+R, Alt+G): the
    cable glyph over CU, RED or GRN, 40x40. The three modes differ only by the
    wire's colour, which a 1-bit keycap cannot show, so the word tells them apart."""
    import numpy as np
    word_font = None
    for stem, word in (("wirecopper", "CU"), ("wirered", "RED"), ("wiregreen", "GRN")):
        path = out / f"{stem}.png"
        if not _missing(path):
            continue
        word_font = word_font or _bold(11)
        g = _glyph_mask(WIRE_GLYPH, (40, 24))
        m = np.zeros((40, 40), bool)
        m[0:g.shape[0], (40 - g.shape[1]) // 2:(40 - g.shape[1]) // 2 + g.shape[1]] = g
        m |= _text_mask(word, word_font, (40, 40), (20, 33.5))
        cnc._save_mask(m, path)
        print(f"  {stem}.png  <- {WIRE_GLYPH} + {word}")


def zoom2x(out: Path) -> None:
    """zoom2x.png (Shift+F9, zoom level 2x): the magnifier with 2x in the lens, 40x40."""
    import numpy as np
    path = out / "zoom2x.png"
    if not _missing(path):
        return
    g = _glyph_mask(ZOOM_GLYPH, (40, 40))
    m = np.zeros((40, 40), bool)
    m[40 - g.shape[0]:, 40 - g.shape[1]:] = g
    # The lens of Material's `search` is centred at 37.5 % of the glyph.
    cx = 40 - g.shape[1] + 0.375 * g.shape[1]
    cy = 40 - g.shape[0] + 0.375 * g.shape[0]
    m |= _text_mask("2x", _bold(10), (40, 40), (cx, cy))
    cnc._save_mask(m, path)
    print("  zoom2x.png  <- ms:search + 2x")


def program(out: Path) -> None:
    """program.png: FACTORIO in Bebas Neue at the largest size that fits
    70 x 38 px, centred on the whole 72x40 cell."""
    path = out / "program.png"
    if not _missing(path):
        return
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font_path = cnc._font(MARK_FONT_URL)
    w, h, ss = 72, 40, MARK_SS
    for px in range(400, 40, -4):
        font = ImageFont.truetype(str(font_path), px)
        b = font.getbbox("FACTORIO")
        if b[2] - b[0] <= 70 * ss and b[3] - b[1] <= 38 * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text(((w * ss - (b[2] - b[0])) // 2 - b[0],
                             (h * ss - (b[3] - b[1])) // 2 - b[1]), "FACTORIO",
                            font=font, fill=255)
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD, path)
    print(f"  program.png  <- FACTORIO (Bebas Neue, {(b[3] - b[1]) // ss} px high)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    render(ICONS, out)
    flat_icons(out)
    quickbar(out)
    wires(out)
    zoom2x(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
