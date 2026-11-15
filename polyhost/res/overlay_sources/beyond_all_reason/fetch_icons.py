#!/usr/bin/env python3
"""Fetch + render the Beyond All Reason icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0) and
game-icons.net (CC BY 3.0), as in the 0 A.D. and StarCraft II sets. Drawn here:
the camera anchors (a pin with the number cut out), the icons with a plus or a
minus (volume, game speed, build spacing, attack range, field of view) and the
control groups (one unit per digit, with a mark per modifier). SOURCES.md
credits each. The ESC mark is BAR set in Audiowide (SIL OFL 1.1); the game's
own logo and art are not used.

The functions flat(), numbered_pins(), plus_minus() and wordmark() take their
tables as arguments; the KeeperFX and Widelands sets call them too.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/beyond_all_reason/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_icons  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.fheroes2 import fetch_icons as fheroes2  # noqa: E402
from polyhost.res.overlay_sources.warcraft3 import fetch_icons as wc3  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402
from polyhost.services.game_assets import dither  # noqa: E402

ICONS = {
    # Orders (the plain layer; Shift queues the same order)
    "attack": "fa:crosshairs",
    "manualfire": "fa:bolt",
    "reclaim": "fa:recycle",
    "fight": "gi:lorc/crossed-swords",
    "stop": "fa:hand",
    "patrol": "fa:route",
    "loadunits": "fa:arrow-right-to-bracket",
    "unloadunits": "fa:arrow-right-from-bracket",
    "cloak": "fa:ghost",
    "firestate": "fa:gun",
    "movestate": "fa:shoe-prints",
    "restore": "fa:trowel",
    "skipcommand": "fa:forward-step",
    "guard": "fa:shield-halved",
    "gatherwait": "fa:people-group",
    "repair": "fa:wrench",
    "settarget": "fa:bullseye",
    "repeat": "fa:repeat",
    "resurrect": "fa:heart-pulse",
    "wait": "fa:hourglass-half",
    "facingccw": "fa:arrow-rotate-left",
    "facingcw": "fa:arrow-rotate-right",
    # Orders on the Ctrl and Alt layers
    "areaattack": "fa:burst",
    "selfdestruct": "fa:bomb",
    "canceltarget": "fa:ban",
    "cancellast": "fa:delete-left",
    "factoryguard": "fa:industry",
    "targetunits": "fa:location-crosshairs",
    "queuemode": "fa:list-ol",
    # Blueprints (Alt)
    "blueprintplace": "fa:stamp",
    "blueprintcreate": "fa:pen-ruler",
    "blueprintdelete": "fa:trash-can",
    "blueprintprev": "fa:angles-left",
    "blueprintnext": "fa:angles-right",
    # Selection
    "sametypeview": "fa:clone",
    "sametypemap": "fa:map-location-dot",
    "selectall": "fa:earth-europe",
    "selecthalf": "fa:circle-half-stroke",
    "idletransports": "fa:helicopter",
    "waitingunits": "fa:user-clock",
    "damaged": "fa:heart-crack",
    "commander": "fa:user-astronaut",
    "idlebuilder": "fa:helmet-safety",
    "groupunset": "fa:users-slash",
    "autogroupremove": "fa:user-minus",
    # Information, camera and display
    "unitstats": "fa:circle-info",
    "gameinfo": "fa:list",
    "lastmessage": "gi:lorc/ringing-bell",
    "pathmap": "fa:road",
    "metalmap": "fa:gem",
    "heightmap": "fa:mountain",
    "hideinterface": "fa:eye-slash",
    "options": "fa:gear",
    "widgets": "fa:list-check",
    "screenshot": "fa:camera",
    "cameraup": "fa:angles-up",
    "cameradown": "fa:angles-down",
    "cameraflip": "fa:rotate",
    "drawinmap": "fa:pencil",
    # Chat, sound and the game
    "chat": "gi:delapouite/chat-bubble",
    "allychat": "gi:lorc/conversation",
    "specchat": "fa:binoculars",
    "mute": "fa:volume-xmark",
    "forcestart": "fa:flag-checkered",
}

# Icons with a plus (the first stem) or a minus (the second) in the corner,
# drawn by plus_minus(): {base stem: (source, plus stem, minus stem)}.
PLUS_MINUS = {
    "_volume": ("fa:volume-low", "volumeup", "volumedown"),
    "_speed": ("fa:forward", "speedup", "slowdown"),
    "_spacing": ("fa:arrows-left-right", "spacingup", "spacingdown"),
    "_range": ("fa:ruler", "rangeup", "rangedown"),
    "_fov": ("fa:eye", "fovup", "fovdown"),
}

# The camera anchors (F1 to F4): a pin with the number cut out of its head.
PIN = "fa:location-dot"
ANCHORS = (1, 2, 3, 4)

# Control groups: one unit per digit, drawn once at full height.
GROUP_UNITS = {
    "1": "delapouite/battle-mech",
    "2": "lorc/tank",
    "3": "delapouite/jet-fighter",
    "4": "delapouite/submarine",
    "5": "delapouite/spider-bot",
    "6": "delapouite/missile-launcher",
    "7": "delapouite/helicopter",
    "8": "delapouite/walking-turret",
    "9": "delapouite/mecha-head",
    "0": "delapouite/bulldozer",
}
# The mark each modifier adds to a group (dither.with_plus / with_mark): Ctrl
# set, Shift add the group to the selection, Ctrl+Shift add the selection to
# the group, Ctrl+Alt toggle the group in the selection, Alt auto group.
GROUP_MARKS = {"groupset": "plus", "groupselectadd": "ring", "groupadd": "box",
               "grouptoggle": "disc", "autogroup": "sight"}

# Key area of each icon, from beyond_all_reason.yaml; the default is 40 x 40.
# The F-key areas use the legend widths measured for Age of Empires II.
SIZES = {"lastmessage": (34, 40), "pathmap": (34, 40), "metalmap": (34, 40),
         "heightmap": (34, 40), "hideinterface": (34, 40), "options": (30, 40),
         "widgets": (30, 40), "screenshot": (30, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"chat": (34, 34), "stop": (34, 36), "cloak": (32, 34), "selfdestruct": (34, 34),
       "unitstats": (32, 32), "canceltarget": (32, 32), "settarget": (34, 34),
       "selecthalf": (32, 32), "selectall": (34, 34), "damaged": (34, 34),
       "metalmap": (30, 30), "options": (30, 30), "screenshot": (30, 30),
       "blueprintdelete": (30, 34), "manualfire": (30, 36), "areaattack": (36, 36)}

# The ESC mark is set in Audiowide (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/audiowide/Audiowide-Regular.ttf")
MARK_LINES = ("BAR",)
MARK_SS = 8                 # supersampling factor for the ESC mark
MARK_THRESHOLD = 100        # grey level (0..255) from which a pixel is lit


def flat(icons, sizes, ink, out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key area
    (`sizes`, default 40 x 40) so the generator places it 1:1. The icons in
    `ink` fill a smaller box in the bottom-right corner of that area."""
    for stem in icons:
        size = sizes.get(stem, (40, 40))
        cnc._save_mask(_placed(out / f"{stem}.png", size, ink.get(stem, size)), out / f"{stem}.png")
    print(f"  {len(icons)} key icons drawn flat")


def _placed(src: Path, size, box):
    """The ink of `src` scaled into `box`, bottom-right in a `size` canvas."""
    import numpy as np
    m = fheroes2._alpha_mask(src, box)
    canvas = np.zeros((size[1], size[0]), bool)
    canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
    return canvas


def plus_minus(table, out: Path) -> None:
    """For each row of `table`: the base icon in the top-left 30 x 30 of a
    40 x 40 area, with a plus (first stem) or a minus (second stem) in the
    bottom-right corner."""
    import numpy as np
    for base, (source, plus, minus) in table.items():
        m = _placed(out / f"{base}.png", (40, 40), (30, 30))
        shifted = np.zeros_like(m)
        shifted[:34, :34] = m[6:, 6:]                # the base moved to the top-left
        cnc._save_mask(aoe2._with_plus(shifted), out / f"{plus}.png")
        cnc._save_mask(zeroad._with_minus(shifted), out / f"{minus}.png")
        print(f"  {plus}.png, {minus}.png  <- {source} + a plus / a minus")


def numbered_pins(src: Path, numbers, stem: str, set_stem: str | None, out: Path,
                  size=(34, 40)) -> None:
    """<stem><N>.png: the location pin with N cut out of its head, in a `size`
    area. <set_stem><N>.png: the same pin moved up and left by 5 px with a plus
    in the corner. The pin's own hole is filled first, so the digit has the
    whole head."""
    import numpy as np
    for n in numbers:
        pin = zeroad._fill_holes(_placed(src, size, (24, 32)))
        ys, xs = np.nonzero(pin)
        g = zeroad._digit(str(n), 13)
        cy = ys.min() + 12                           # the centre of the round head
        cx = (xs.min() + xs.max() + 1) // 2
        y0, x0 = cy - g.shape[0] // 2, cx - g.shape[1] // 2
        pin[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] &= ~g
        cnc._save_mask(pin, out / f"{stem}{n}.png")
        if set_stem:
            moved = np.zeros_like(pin)
            moved[:-5, :-5] = pin[5:, 5:]
            cnc._save_mask(aoe2._with_plus(moved), out / f"{set_stem}{n}.png")
    print(f"  {stem}<N>.png{' and ' + set_stem + '<N>.png' if set_stem else ''}"
          f"  <- the pin with {', '.join(str(n) for n in numbers)}")


def groups(out: Path) -> None:
    """group<N>.png (select) and one marked copy per modifier (GROUP_MARKS)."""
    import numpy as np
    for digit in GROUP_UNITS:
        g = wc3._single(out / f"_unit{digit}.png")
        canvas = np.zeros((aoe2.GROUP_H, aoe2.GROUP_W), bool)
        canvas[aoe2.GROUP_H - g.shape[0]:, aoe2.GROUP_W - g.shape[1]:] = g
        aoe2._save_cell(canvas, out / f"group{digit}.png")
        for stem, mark in GROUP_MARKS.items():
            marked = dither.with_plus(canvas) if mark == "plus" else dither.with_mark(canvas, mark)
            aoe2._save_cell(marked, out / f"{stem}{digit}.png")
        print(f"  group{digit}.png and {len(GROUP_MARKS)} marked copies  <- _unit{digit}.png")


def wordmark(lines, font_url: str, out: Path, threshold: int, gap: int = 2,
             ss: int = MARK_SS) -> None:
    """program.png: `lines`, all at the largest one size at which each fits
    70 px wide and all, `gap` px apart, fit 38 px high, centred on the whole
    72x40 cell. Drawn at `ss` times the size and box-filtered down; a pixel is
    lit from grey `threshold` of 255."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    w, h = 72, 40
    path = str(cnc._font(font_url))
    for px in range(400, 40, -4):
        font = ImageFont.truetype(path, px)
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
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > threshold, out / "program.png")
    print(f"  program.png  <- {' / '.join(lines)} ({font_url.rsplit('/', 1)[1]}, {px / ss:.1f} px)")


def main() -> int:
    import numpy as np
    out = Path(__file__).resolve().parent / "icons"
    parts = {"_pin": PIN, **{base: row[0] for base, row in PLUS_MINUS.items()}}
    cnc.render({**ICONS, **parts}, out)
    game_icons.render({f"_unit{d}": n for d, n in GROUP_UNITS.items()}, out, render_px=256)
    flat(ICONS, SIZES, INK, out)
    # Shift+Tab (add the commander to the selection): the commander with a plus.
    commander = _placed(out / "commander.png", (40, 40), (30, 34))
    moved = np.zeros_like(commander)
    moved[:-5, :-5] = commander[5:, 5:]
    cnc._save_mask(aoe2._with_plus(moved), out / "commanderadd.png")
    plus_minus(PLUS_MINUS, out)
    numbered_pins(out / "_pin.png", ANCHORS, "anchor", "anchorset", out)
    groups(out)
    for stem in [*parts, *(f"_unit{d}" for d in GROUP_UNITS)]:
        (out / f"{stem}.png").unlink()
    wordmark(MARK_LINES, FONT_URL, out, MARK_THRESHOLD)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
