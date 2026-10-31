#!/usr/bin/env python3
"""Fetch + render the Warzone 2100 icons (reproducible).

The key icons are flat silhouettes from game-icons.net (CC BY 3.0), Font
Awesome Free (CC BY 4.0) and one from Material Design Icons (Apache-2.0), as in
the Warcraft III set. A few are drawn here: the three firing ranges, the
compass letters, the track, the half-track, the hover unit, and the small marks
added to an icon (plus, ringed plus, "no group", return arrow). SOURCES.md credits each. The ESC mark is WARZONE over 2100 set in
Orbitron Black (SIL OFL 1.1); the game's own art (GPL) is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/warzone2100/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_icons  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.warcraft3 import fetch_icons as wc3  # noqa: E402

ICONS = {
    # Reticule screens (F1 to F6)
    "manufacture": "gi:delapouite/factory",
    "research": "fa:flask",
    "build": "fa:hammer",
    "design": "fa:pen-ruler",
    "intelligence": "fa:user-secret",
    "commanders": "gi:delapouite/sergeant",
    # F7 to F12 and their Shift layer
    "quicksave": "fa:floppy-disk",
    "quickload": "fa:folder-open",
    "damagebars": "fa:bars-progress",
    "screenshot": "fa:camera",
    "formationspeed": "gi:delapouite/speedometer",
    "lastmessage": "gi:lorc/ringing-bell",
    "radar": "gi:lorc/radar-sweep",
    "console": "fa:terminal",
    "sensordisplay": "fa:satellite-dish",
    # Camera and display
    "trackcamera": "fa:video",
    "overlays": "fa:layer-group",
    "consolehistory": "fa:clock-rotate-left",
    "teamchathistory": "fa:comments",
    "slowdown": "fa:backward",
    "speedup": "fa:forward",
    "normalspeed": "fa:play",
    "radarterrain": "fa:mountain",
    "radarallies": "fa:people-arrows",
    "shadows": "fa:circle-half-stroke",
    "trapcursor": "fa:computer-mouse",
    "fullscreen": "fa:expand",
    "mappings": "fa:keyboard",
    # Unit orders
    "centrehq": "fa:building-flag",
    "unassigned": "fa:person-circle-question",
    "returnfire": "gi:lorc/shield-bounces",
    "fireatwill": "fa:gun",
    "guard": "fa:shield-halved",
    "hold": "fa:anchor",
    "pursue": "fa:person-running",
    "patrol": "fa:arrow-right-arrow-left",
    "repair": "fa:wrench",
    "stop": "fa:hand",
    "transport": "fa:plane-arrival",
    "recycle": "fa:recycle",
    "retreatmedium": "fa:battery-half",
    "retreatheavy": "fa:battery-quarter",
    "doordie": "fa:skull",
    "beacon": "fa:location-dot",
    # Unit selection
    "combat": "gi:lorc/crossed-swords",
    "landcombat": "mdi:tank",
    "cyborgs": "gi:delapouite/cyborg-face",
    "combatcyborgs": "gi:delapouite/battle-mech",
    "engineers": "fa:helmet-safety",
    "mechanics": "fa:screwdriver-wrench",
    "damaged": "fa:heart-crack",
    "wheels": "gi:delapouite/car-wheel",
    "vtols": "fa:jet-fighter-up",
    "armedvtols": "fa:jet-fighter",
    "transporters": "fa:helicopter",
    "repairtanks": "fa:truck-medical",
    "sensors": "fa:tower-broadcast",
    "trucks": "fa:truck",
    "onscreen": "fa:display",
    "everyunit": "fa:earth-europe",
    "samecomponents": "fa:clone",
    # Chat
    "chat": "gi:delapouite/chat-bubble",
    "teamchat": "gi:lorc/conversation",
    "quickchat": "fa:comment-dots",
}

# Control groups: one tank at full height. Alt+digit (select commander N): the
# commander's chevrons, drawn the same way.
GROUP_UNIT = "lorc/tank"
COMMANDER = "delapouite/sergeant"

# Key area of each icon, from warzone2100.yaml; the default is 40 x 40.
SIZES = {"manufacture": (34, 40), "research": (34, 40), "build": (34, 40),
         "design": (30, 40), "intelligence": (34, 40), "commanders": (34, 40),
         "quicksave": (34, 40), "quickload": (34, 40), "damagebars": (34, 40),
         "radar": (34, 40), "console": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"quicksave": (30, 30), "quickload": (30, 30), "screenshot": (30, 30),
       "chat": (34, 34), "teamchathistory": (34, 34), "quickchat": (34, 34),
       "doordie": (34, 34), "damaged": (34, 34), "onscreen": (34, 34),
       "trackcamera": (34, 34), "slowdown": (34, 34), "speedup": (34, 34),
       "normalspeed": (30, 30), "shadows": (34, 34), "trapcursor": (34, 34)}

# Icons with a small mark in the bottom-right corner, drawn by marked():
# {output stem: (source stem, mark)}.
MARKED = {
    # Alt: the same selection, only units that are in no group
    "landcombat_nogroup": ("landcombat", "nogroup"),
    "combatcyborgs_nogroup": ("combatcyborgs", "nogroup"),
    "tracks_nogroup": ("tracks", "nogroup"),
    "halftracks_nogroup": ("halftracks", "nogroup"),
    "armedvtols_nogroup": ("armedvtols", "nogroup"),
    "sensors_nogroup": ("sensors", "nogroup"),
    # Shift+H: return to HQ
    "returnhq": ("centrehq", "return"),
    # - and = over the radar: radar zoom
    "radarzoomin": ("_radar40", "plus"),
    "radarzoomout": ("_radar40", "minus"),
    # C: hold fire is the fire-at-will bullets struck through
    "holdfire": ("fireatwill", "strike"),
}

# Ctrl+Up/Down/Left/Right and Backspace: the view direction as a compass letter.
COMPASS = {"north": "N", "south": "S", "east": "E", "west": "W"}

# The ESC mark is set in Orbitron (SIL OFL 1.1), its Black instance.
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/orbitron/Orbitron%5Bwght%5D.ttf")
SS = 8                                       # supersampling factor for drawn icons
SEAM = aoe2.GROUP_SEAM                       # unlit pixels between an icon and its mark
MARK = 13                                    # size of a corner mark, in px
RETURN_SIZE = (46, 40)                        # Shift+H: the building and the arrow beside it


def _load_mask(path: Path):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGBA").getchannel("A")) > 127


def _fit(stem: str, src: Path, box: tuple[int, int], size: tuple[int, int]):
    """The ink of `src` scaled into `box`, bottom-right in a `size` canvas."""
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


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key area
    so the generator places it 1:1. The icons in INK fill a smaller box in the
    bottom-right corner of that area."""
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        cnc._save_mask(_fit(stem, out / f"{stem}.png", INK.get(stem, size), size), out / f"{stem}.png")
    # The radar at 40 x 40, for the radar zoom marks (the F7 copy is 34 wide).
    cnc._save_mask(_fit("_radar40", out / "_radar.png", (40, 40), (40, 40)), out / "_radar40.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def _draw(fn, size=(40, 40), threshold=110):
    """Call `fn(draw, ss)` on a SS-times canvas and box-filter it to `size`."""
    import numpy as np
    from PIL import Image, ImageDraw
    im = Image.new("L", (size[0] * SS, size[1] * SS), 0)
    fn(ImageDraw.Draw(im), SS)
    return np.asarray(im.resize(size, Image.BOX)) > threshold


def _mark(kind: str):
    """A MARK x MARK corner mark."""
    import math

    def draw(d, s):
        n, w = MARK * s, 3 * s
        if kind in ("plus", "minus"):
            d.rectangle((0, (n - w) // 2, n - 1, (n + w) // 2 - 1), fill=255)
        if kind == "plus":
            d.rectangle(((n - w) // 2, 0, (n + w) // 2 - 1, n - 1), fill=255)
        if kind == "nogroup":                    # a ring struck through
            d.ellipse((0, 0, n - 1, n - 1), outline=255, width=2 * s)
            r = n / 2
            k = r * math.cos(math.radians(45))
            d.line((r - k, r + k, r + k, r - k), fill=255, width=2 * s)
        if kind == "return":                     # an arrow pointing right
            d.polygon([(n - 1, n // 2), (n // 2, 0), (n // 2, n - 1)], fill=255)
            d.rectangle((0, n // 2 - w // 2, n // 2, n // 2 + w // 2), fill=255)
    return _draw(draw, (MARK, MARK))


def marked(out: Path) -> None:
    """The icons in MARKED: the source icon with a corner mark, (strike) with
    a diagonal line through it, or (return) narrower with an arrow pointing into
    it from the left. SEAM px of the icon are cleared around the
    mark, as around the plus of a control group."""
    import numpy as np
    for stem, (src, kind) in MARKED.items():
        icon = _load_mask(out / f"{src}.png")
        H, W = icon.shape
        if kind == "strike":                     # from bottom left to top right
            line = _draw(lambda d, s: d.line((2 * s, (H - 3) * s, (W - 3) * s, 2 * s),
                                             fill=255, width=4 * s), (W, H))
        elif kind == "return":                   # wider (RETURN_SIZE), an arrow into the icon
            W, H = RETURN_SIZE
            icon = _fit(src, out / f"{src}.png", (W - MARK - SEAM, H), (W, H))
            line = np.zeros((H, W), bool)
            line[H - MARK - 4:H - 4, :MARK] = _mark(kind)
        else:
            line = np.zeros((H, W), bool)
            line[H - MARK:, W - MARK:] = _mark(kind)
        cnc._save_mask((icon & ~program_mark.dilate(line, SEAM)) | line, out / f"{stem}.png")
        print(f"  {stem}.png  <- {src}.png + {kind}")


def compass(out: Path) -> None:
    """north/south/east/west.png: the letter inside a ring, 40 x 40."""
    from PIL import ImageFont
    font = ImageFont.truetype(str(cnc._font(cnc.DIGIT_FONT_URL)), 24 * SS)
    for stem, letter in COMPASS.items():
        def draw(d, s, letter=letter):
            d.ellipse((1 * s, 1 * s, 39 * s - 1, 39 * s - 1), outline=255, width=3 * s)
            left, top, right, bottom = font.getbbox(letter)
            d.text((20 * s - (left + right) // 2, 20 * s - (top + bottom) // 2), letter,
                   font=font, fill=255)
        cnc._save_mask(_draw(draw), out / f"{stem}.png")
    print(f"  {', '.join(COMPASS)}.png  <- DejaVu Sans Bold letter in a ring")


def ranges(out: Path) -> None:
    """rangeshort/rangeoptimum/rangelong.png: a unit (a dot, bottom left) and
    one, two or three arcs of fire, 40 x 40."""
    for stem, arcs in (("rangeshort", 1), ("rangeoptimum", 2), ("rangelong", 3)):
        def draw(d, s, arcs=arcs):
            cx, cy = 5 * s, 35 * s
            d.ellipse((cx - 5 * s, cy - 5 * s, cx + 5 * s, cy + 5 * s), fill=255)
            for i in range(arcs):
                r = (14 + 10 * i) * s
                d.arc((cx - r, cy - r, cx + r, cy + r), 270, 360, fill=255, width=4 * s)
        cnc._save_mask(_draw(draw), out / f"{stem}.png")
    print("  rangeshort.png, rangeoptimum.png, rangelong.png  <- drawn arcs")


def hover(out: Path) -> None:
    """hovers.png: a hull on an air cushion over two wave lines, 40 x 40."""
    def draw(d, s):
        d.polygon([(8 * s, 18 * s), (12 * s, 9 * s), (28 * s, 9 * s), (33 * s, 18 * s)], fill=255)
        d.rectangle((30 * s, 4 * s, 34 * s, 18 * s), fill=255)               # the rear fan
        d.rounded_rectangle((1 * s, 18 * s, 39 * s, 28 * s), radius=5 * s, fill=255)
        for y in (32, 37):                                                   # waves
            pts = [(x * s, (y + (1.6 if (x // 4) % 2 else -1.6)) * s) for x in range(2, 40, 4)]
            d.line(pts, fill=255, width=2 * s)
    cnc._save_mask(_draw(draw), out / "hovers.png")
    print("  hovers.png  <- drawn")


def _tread(d, s, x0, x1, y0=18, y1=38, wheels=3):
    """A track: a loop with `wheels` road wheels inside, from x0 to x1."""
    r = (y1 - y0) // 2
    d.rounded_rectangle((x0 * s, y0 * s, x1 * s - 1, y1 * s - 1), radius=r * s, outline=255, width=3 * s)
    step = (x1 - x0 - 2 * r) / max(1, wheels - 1)
    for i in range(wheels):
        cx, cy, k = (x0 + r + i * step) * s, (y0 + r) * s, min(4, r - 4) * s
        d.ellipse((cx - k, cy - k, cx + k, cy + k), fill=255)


def tracks(out: Path) -> None:
    """tracks.png (Ctrl+T): a track loop with three road wheels.
    halftracks.png (Ctrl+F): a wheel in front of a shorter track. 40 x 40."""
    def track(d, s):
        _tread(d, s, 1, 40)

    def halftrack(d, s):
        d.ellipse((1 * s, 23 * s, 17 * s, 39 * s), outline=255, width=3 * s)    # the wheel
        d.ellipse((6 * s, 28 * s, 12 * s, 34 * s), fill=255)                    # its hub
        _tread(d, s, 19, 40, 24, 39, wheels=2)
    cnc._save_mask(_draw(track), out / "tracks.png")
    cnc._save_mask(_draw(halftrack), out / "halftracks.png")
    print("  tracks.png, halftracks.png  <- drawn")


def groups(out: Path) -> None:
    """group.png (select), groupnew.png (Ctrl: assign, a plus), groupadd.png
    (Shift: add, a ringed plus) and commander.png (Alt), 48 x 40 like the
    Warcraft III groups. One image for all ten digits: the legend tells the
    digit."""
    g = wc3._single(out / "_group.png")
    aoe2._save_cell(g, out / "group.png")
    aoe2._save_cell(aoe2._with_plus(g), out / "groupnew.png")
    aoe2._save_cell(wc3._with_ring_plus(g), out / "groupadd.png")
    aoe2._save_cell(wc3._single(out / "_commander.png"), out / "commander.png")
    print("  group.png, groupnew.png, groupadd.png  <- _group.png; commander.png  <- _commander.png")


def _mark_font(px: int):
    from PIL import ImageFont
    f = ImageFont.truetype(str(cnc._font(FONT_URL)), px)
    f.set_variation_by_name("Black")
    return f


def program(out: Path) -> None:
    """program.png: WARZONE at the largest size that fits 70 px, over a 2100
    that fits the same width, centred on the whole 72x40 cell. Drawn at SS times
    the size and box-filtered down."""
    import numpy as np
    from PIL import Image, ImageDraw
    w, h, ss = program_mark.W, program_mark.H, SS
    lines = []
    for text, cap_max in (("WARZONE", 14), ("2100", 18)):
        for cap in range(cap_max, 5, -1):
            ref = _mark_font(200).getbbox("H")
            font = _mark_font(round(200 * cap * ss / (ref[3] - ref[1])))
            box = font.getbbox(text)
            if box[2] - box[0] <= (w - 2) * ss:
                break
        lines.append((text, font, box, cap))
    gap = 4 * ss
    height = sum(b[3] - b[1] for _, _, b, _ in lines) + gap
    y = (h * ss - height) // 2
    canvas = np.zeros((h, w), bool)
    for text, font, box, _ in lines:
        im = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(im).text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                                text, font=font, fill=255)
        canvas |= np.asarray(im.resize((w, h), Image.BOX)) > 100
        y += box[3] - box[1] + gap
    cnc._save_mask(canvas, out / "program.png")
    print(f"  program.png  <- WARZONE (cap {lines[0][3]} px) over 2100 (cap {lines[1][3]} px), Orbitron Black")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, "_radar": ICONS["radar"]}, out)
    game_icons.render({"_group": GROUP_UNIT, "_commander": COMMANDER}, out, render_px=256)
    flat_icons(out)
    hover(out)
    tracks(out)
    marked(out)
    compass(out)
    ranges(out)
    groups(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
