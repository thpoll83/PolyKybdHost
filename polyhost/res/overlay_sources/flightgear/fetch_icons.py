#!/usr/bin/env python3
"""Fetch + render the FlightGear icons (reproducible).

The key icons are flat silhouettes from Material Design Icons (Apache-2.0) and
Font Awesome Free (CC BY 4.0). Cockpit terms that have no pictogram (autopilot
locks, flaps, mixture, magnetos) are set as text in Press Start 2P (SIL OFL
1.1), alone, under a pictogram, or above a plus or minus sign. SOURCES.md
credits each. The ESC mark is FlightGear's own application icon
(GPL-2.0-or-later), reduced to 40 x 40 at 1 bit.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/flightgear/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.fheroes2.fetch_icons import _alpha_mask  # noqa: E402
from polyhost.res.overlay_sources.hedgewars.fetch_icons import _corner  # noqa: E402
from polyhost.res.overlay_sources.icon_fetch import _get  # noqa: E402
from polyhost.res.overlay_sources.supertuxkart import fetch_icons as stk  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Flight controls
    "aileronleft": "mdi:rotate-left",
    "aileronright": "mdi:rotate-right",
    "elevatorup": "mdi:airplane-takeoff",
    "elevatordown": "mdi:airplane-landing",
    "rudderleft": "mdi:arrow-left-top-bold",
    "rudderright": "mdi:arrow-right-top-bold",
    "center": "fa:arrows-to-dot",
    "throttleup": "mdi:speedometer",
    "throttledown": "mdi:speedometer-slow",
    "trimup": "mdi:arrow-up-drop-circle-outline",
    "trimdown": "mdi:arrow-down-drop-circle-outline",
    "trimupfast": "mdi:chevron-triple-up",
    "trimdownfast": "mdi:chevron-triple-down",
    "ailerontrimleft": "mdi:arrow-left-drop-circle-outline",
    "ailerontrimright": "mdi:arrow-right-drop-circle-outline",
    "autocoordination": "mdi:link-variant",
    # Brakes
    "allbrakes": "mdi:car-brake-alert",
    "parkingbrake": "mdi:car-brake-parking",
    # Simulator
    "pause": "fa:pause",
    "speedup": "mdi:fast-forward",
    "slowdown": "mdi:rewind",
    "warpforward": "mdi:clock-fast",
    "warpback": "mdi:history",
    "replay": "mdi:replay",
    "mousemode": "mdi:mouse",
    "hotspots": "mdi:cursor-default-click",
    "tooltips": "mdi:tooltip-text",
    "propertybrowser": "mdi:file-tree",
    "multikey": "mdi:keyboard",
    "help": "mdi:help-circle",
    "map": "mdi:map",
    # Radio and chat
    "ptt": "mdi:microphone",
    "atc": "mdi:radio-tower",
    "chatmenu": "mdi:forum",
    "composechat": "mdi:message-text",
    # View
    "nextview": "mdi:eye-arrow-right",
    "prevview": "mdi:eye-arrow-left",
    "zoomin": "mdi:magnify-plus",
    "zoomout": "mdi:magnify-minus",
    "zoomreset": "mdi:magnify-scan",
    "cockpit": "mdi:video-3d",
    # Panels
    "panel": "mdi:view-dashboard",
    "swappanels": "mdi:swap-horizontal-bold",
    # Function keys
    "screenshot": "mdi:camera",
    "cubemap": "mdi:cube-outline",
    "panorama": "mdi:panorama-variant",
    "menubar": "mdi:menu",
    "fullscreen": "mdi:fullscreen",
    "autopilotdialog": "mdi:airplane-cog",
    "radiodialog": "mdi:radio-handheld",
}
# Parts of the composed icons; removed after the run.
PARTS = {
    "_brake": "mdi:car-brake-alert",
    "_tire": "mdi:tire",
    "_up": "mdi:arrow-up-bold",
    "_down": "mdi:arrow-down-bold",
    "_engine": "mdi:engine",
    "_eye": "mdi:eye",
    "_lock": "mdi:lock",
    "_flash": "mdi:flash",
    "_restore": "mdi:restore",
    "_brightness": "mdi:brightness-6",
    "_repeat": "mdi:repeat",
    "_cassette": "mdi:cassette",
    "_folder": "mdi:folder-open",
    "_look_left": "mdi:arrow-left-thick",
    "_look_right": "mdi:arrow-right-thick",
    "_look_forward": "mdi:arrow-up-thick",
    "_look_back": "mdi:arrow-down-thick",
    "_look_frontleft": "mdi:arrow-top-left-thick",
    "_look_frontright": "mdi:arrow-top-right-thick",
    "_look_backleft": "mdi:arrow-bottom-left-thick",
    "_look_backright": "mdi:arrow-bottom-right-thick",
    "_pan_up": "mdi:pan-up",
    "_pan_down": "mdi:pan-down",
    "_pan_left": "mdi:pan-left",
    "_pan_right": "mdi:pan-right",
}

# Key area of each icon, from flightgear.yaml; the default is 40 x 40.
FKEY = (34, 40)
SIZES = {"screenshot": FKEY, "cubemap": FKEY, "panorama": FKEY}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"pause": (28, 30), "screenshot": (32, 30), "map": (34, 34), "help": (34, 34),
       "panel": (32, 32), "chatmenu": (36, 36), "composechat": (34, 34),
       "tooltips": (34, 34), "cockpit": (38, 30), "mousemode": (30, 34),
       "cubemap": (32, 34), "panorama": (34, 30)}

# Text icons: {stem: lines}. Every line is 8 px Press Start 2P (7 px capitals).
TEXT = {
    # Autopilot locks (Ctrl+letter)
    "apaltitude": ("AP", "ALT"),
    "apglideslope": ("AP", "GS"),
    "apheading": ("AP", "HDG"),
    "apnav1": ("AP", "NAV1"),
    "appitch": ("AP", "PITCH"),
    "apterrain": ("AP", "TERR"),
    "apwing": ("AP", "WING", "LEVEL"),
    "autothrottle": ("AUTO", "THR"),
    "speedbrake": ("SPEED", "BRAKE"),
    "cheataltitude": ("+1000", "FT"),
    "headingmode": ("HDG", "MODE"),
    # HUD
    "hud": ("HUD",),
    "hudnormal": ("HUD", "1"),
    "hudalternative": ("HUD", "2"),
}
TEXT_SIZES = {"headingmode": FKEY}
# Text above a plus or a minus sign: {stem: (text, sign)}.
SIGNED = {
    "flapsdown": ("FLAP", "+"), "flapsup": ("FLAP", "-"),
    "spoilersmore": ("SPOIL", "+"), "spoilersless": ("SPOIL", "-"),
    "mixturericher": ("MIX", "+"), "mixtureleaner": ("MIX", "-"),
    "propfiner": ("PROP", "+"), "propcoarser": ("PROP", "-"),
    "magnetomore": ("MAG", "+"), "magnetoless": ("MAG", "-"),
    "visibilitymore": ("VIS", "+"), "visibilityless": ("VIS", "-"),
}
# A pictogram above one line of text: {stem: (part, text, key area)}.
STACKED = {
    "tailwheellock": ("_lock", "TAIL", (40, 40)),
    "starter": ("_flash", "START", (40, 40)),
    "visibilityreset": ("_restore", "VIS", (40, 40)),
    "cleartrims": ("_restore", "TRIM", (40, 40)),
    "hudbrightness": ("_brightness", "HUD", (40, 40)),
    "atcrepeat": ("_repeat", "ATC", (40, 40)),
    "allengines": ("_engine", "ALL", (40, 40)),
    "loadtape": ("_cassette", "LOAD", FKEY),
    "savetape": ("_cassette", "SAVE", FKEY),
    "loadpanel": ("_folder", "PANL", FKEY),
}
ENGINES = range(1, 5)
ENGINE_DIGIT_PX = 14
TEXT_PX = 8                 # Press Start 2P: exact at 8 px
LINE_GAP = 3                # px between two lines of text
SIGN_PX, SIGN_W = 18, 4     # the plus and minus signs: arm length and stroke

FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/pressstart2p/PressStart2P-Regular.ttf")

# FlightGear's application icon at release 2024.1.7 (GPL-2.0-or-later).
LOGO_URL = ("https://gitlab.com/flightgear/flightgear/-/raw/"
            "7241807173248abd838e2ab11337fbc5b2ae20b0/package/FlightGear_app_icon.svg")
LOGO_PX = 40


def _text(text: str):
    """`text` at 8 px as a 1-bit mask cropped to its ink."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(str(cnc._font(FONT_URL)), TEXT_PX)
    left, top, right, bottom = f.getbbox(text)
    im = Image.new("L", (right - left, bottom - top), 0)
    ImageDraw.Draw(im).text((-left, -top), text, font=f, fill=255)
    m = np.array(im) > 127
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _rows(parts, size, gap=LINE_GAP):
    """`parts` (masks) one below the other, each right-aligned, the last on the
    bottom edge of a `size` (w, h) canvas."""
    import numpy as np
    w, h = size
    canvas = np.zeros((h, w), bool)
    y = h
    for m in reversed(parts):
        if m.shape[1] > w or m.shape[0] > y:
            raise ValueError(f"a row of {m.shape[1]}x{m.shape[0]} px does not fit {w}x{h}")
        canvas[y - m.shape[0]:y, w - m.shape[1]:] = m
        y -= m.shape[0] + gap
    return canvas


def _sign(sign: str):
    import numpy as np
    m = np.zeros((SIGN_PX, SIGN_PX), bool)
    a = (SIGN_PX - SIGN_W) // 2
    m[a:a + SIGN_W, :] = True
    if sign == "+":
        m[:, a:a + SIGN_W] = True
    return m


def text_icons(out: Path) -> None:
    """The icons of TEXT, SIGNED and STACKED."""
    for stem, lines in TEXT.items():
        cnc._save_mask(_rows([_text(t) for t in lines], TEXT_SIZES.get(stem, (40, 40))),
                       out / f"{stem}.png")
    for stem, (text, sign) in SIGNED.items():
        cnc._save_mask(_rows([_sign(sign), _text(text)], (40, 40), gap=5), out / f"{stem}.png")
    for stem, (part, text, size) in STACKED.items():
        pic = _alpha_mask(out / f"{part}.png", (size[0], size[1] - TEXT_PX - LINE_GAP + 1))
        cnc._save_mask(_rows([pic, _text(text)], size), out / f"{stem}.png")
    print(f"  {len(TEXT) + len(SIGNED) + len(STACKED)} text icons drawn")


def composed(out: Path) -> None:
    """Brakes with L and R, gear with an arrow, engines with a number, views
    with a digit or an arrow, and the panel scroll arrows."""
    import numpy as np
    brake = _alpha_mask(out / "_brake.png", (30, 30))
    for name, letter in (("leftbrake", "L"), ("rightbrake", "R")):
        cnc._save_mask(_corner(brake, zeroad._digit(letter, 13)), out / f"{name}.png")
    tire = _alpha_mask(out / "_tire.png", (28, 28))
    for name, arrow in (("gearup", "_up"), ("geardown", "_down")):
        cnc._save_mask(_corner(tire, _alpha_mask(out / f"{arrow}.png", (16, 18))),
                       out / f"{name}.png")
    engine = _alpha_mask(out / "_engine.png", (32, 24))
    for n in ENGINES:
        cnc._save_mask(_corner(engine, zeroad._digit(str(n), ENGINE_DIGIT_PX)),
                       out / f"engine{n}.png")
    eye = _alpha_mask(out / "_eye.png", (30, 22))
    cnc._save_mask(_corner(eye, zeroad._digit("0", 14)), out / "initialview.png")
    for d in ("left", "right", "forward", "back", "frontleft", "frontright",
              "backleft", "backright"):
        cnc._save_mask(_corner(eye, _alpha_mask(out / f"_look_{d}.png", (16, 16))),
                       out / f"look{d}.png")
    for d in ("up", "down", "left", "right"):
        m = _alpha_mask(out / f"_pan_{d}.png", (30, 30))
        canvas = np.zeros((FKEY[1], FKEY[0]), bool)
        canvas[FKEY[1] - m.shape[0]:, FKEY[0] - m.shape[1]:] = m
        cnc._save_mask(canvas, out / f"panel{d}.png")
    print("  brakes, gear, engines, views and panel arrows  <- composed")


def program(out: Path) -> None:
    """program.png: FlightGear's application icon at LOGO_PX. The icon is a
    rounded tile, 128 units wide in its own drawing: a 48 unit chequered band of
    16 unit squares and a blue F on white. At 40 px a square is exactly 5 px.
    The yellow squares and the F are lit."""
    if (out / "program.png").exists():
        # Taken from the program's own art: the committed PNG is the source, and
        # an owner's edit of it must survive a re-run. Delete the file to redraw it.
        print("  program.png  <- committed asset (left as-is)")
        return
    import cairosvg
    import numpy as np
    from PIL import Image
    png = cairosvg.svg2png(bytestring=_get(LOGO_URL), output_width=1024, output_height=1024)
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    rgba = np.asarray(im).astype(int)
    r, g, b, a = (rgba[..., i] for i in range(4))
    tile = a > 250
    ys, xs = np.nonzero(tile)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    yellow = tile & (r > 180) & (g > 180) & (b < 150)
    blue = tile & (b > 150) & (r < 140)
    lit = Image.fromarray(((yellow | blue) * 255).astype(np.uint8)).crop(box)
    cnc._save_mask(np.asarray(lit.resize((LOGO_PX, LOGO_PX), Image.BOX)) > 127,
                   out / "program.png")
    print("  program.png  <- FlightGear_app_icon.svg")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    stk.flat_icons(out, ICONS, SIZES, INK)
    text_icons(out)
    composed(out)
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
