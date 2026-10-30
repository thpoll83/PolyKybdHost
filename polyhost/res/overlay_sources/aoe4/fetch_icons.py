#!/usr/bin/env python3
"""Fetch + render the Age of Empires IV icons (reproducible).

The key icons are flat 1-bit silhouettes from game-icons.net (CC BY 3.0) and
Font Awesome Free (CC BY 4.0), as in the Warcraft III set. Icons for an action
that Age of Empires II or Warcraft III already draw (go to the Town Center,
idle villager, idle military, control groups, chat, camera rotation) are
copied from those sets, so the keyboard stores one copy of each cell.
SOURCES.md credits each icon.

The ESC mark is the Age of Empires II mark with "IV" in place of "II"
(Liberation Serif, SIL OFL 1.1); the game's logo art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/aoe4/fetch_icons.py            # keeps drawn PNGs
    python polyhost/res/overlay_sources/aoe4/fetch_icons.py --redraw   # redraws them
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.warcraft3 import fetch_icons as wc3  # noqa: E402

HERE = Path(__file__).resolve().parent
SETS = HERE.parent

# Icons copied unchanged from another game set: {file here: "set/icons/file"}.
# Each one is bound with the same area as in its own set, so the generated cell
# is byte-identical and the keyboard stores it once.
REUSED = {
    "towncenter.png": "aoe2/icons/towncenter.png",          # H
    "idlevillager.png": "aoe2/icons/idlevillager.png",      # .
    "idlemilitary.png": "aoe2/icons/idlemilitary.png",      # ,
    "chatback.png": "aoe2/icons/chatback.png",              # Page Up
    "chatfwd.png": "aoe2/icons/chatfwd.png",                # Page Down
    "allycolours.png": "aoe2/icons/allycolours.png",        # Insert
    "flare.png": "aoe2/icons/flare.png",                    # Ctrl+E
    "gametime.png": "aoe2/icons/gametime.png",              # F11
    "pause.png": "aoe2/icons/pause.png",                    # Pause
    "lastevent.png": "warcraft3/icons/lastevent.png",       # Space
    "subgroup.png": "warcraft3/icons/subgroup.png",         # Tab
    "gamemenu.png": "warcraft3/icons/gamemenu.png",         # F10
    "save.png": "warcraft3/icons/save.png",                 # F8
    "load.png": "warcraft3/icons/load.png",                 # F9
    "chatall.png": "warcraft3/icons/chatall.png",           # Shift+Enter
    "chatallies.png": "warcraft3/icons/chatallies.png",     # Enter
    "rotateleft.png": "warcraft3/icons/rotateleft.png",     # [
    "rotateright.png": "warcraft3/icons/rotateright.png",   # ]
    **{f"group{d}.png": f"aoe2/icons/group{d}.png" for d in "0123456789"},
    **{f"groupnew{d}.png": f"aoe2/icons/groupnew{d}.png" for d in "0123456789"},
}

# New key icons, drawn flat at their key area (SIZES, default 40 x 40).
ICONS = {
    # Selection
    "milbuildings": "gi:delapouite/medieval-barracks",
    "ecobuildings": "gi:delapouite/windmill",
    "techbuildings": "gi:lorc/erlenmeyer",
    "landmarks": "gi:delapouite/greek-temple",
    # F5 and F6: Warcraft III's art for the same actions, drawn again in the
    # narrower area that keeps the F-key legend whole
    "focus": "fa:crosshairs",
    "tribute": "gi:delapouite/shaking-hands",
    "monks": "gi:delapouite/monk-face",
    "scouts": "gi:lorc/spyglass",
    "follow": "fa:video",
    "resetcamera": "fa:camera-rotate",
    "delete": "fa:trash-can",
    "gatherfood": "gi:lorc/wheat",
    "gatherwood": "gi:delapouite/log",
    "gathergold": "gi:willdabeast/gold-bar",
    "gatherstone": "gi:lorc/stone-block",
    "backtowork": "gi:lorc/hammer-nails",
}
# Parts composed by the functions below, rendered but not bound.
PARTS = {
    "_village": "gi:delapouite/village",
    "_crown": "gi:delapouite/imperial-crown",
    "_marker": "gi:delapouite/position-marker",
    "_sword": "gi:lorc/broadsword",
    "_shield": "gi:sbed/shield",
    "_frame": "fa:expand",
    "_people": "fa:people-group",
    "_farmer": "gi:delapouite/farmer",
    "_swords": "gi:lorc/crossed-swords",
}

# Key area of each icon, from aoe4.yaml; the default is 40 x 40. The F-key
# areas are the legend widths AoE2 and Warcraft III measured.
SIZES = {"milbuildings": (34, 40), "ecobuildings": (34, 40), "techbuildings": (34, 40),
         "landmarks": (30, 40), "focus": (34, 40), "tribute": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box, as in
# the Warcraft III set.
INK = {"follow": (34, 34), "resetcamera": (34, 34), "delete": (34, 34)}

# Word composites: a word over an icon, drawn 1-bit at 40 x 40.
# The IV is set in the bold face: the thin left stroke of the regular V
# disappears in the dotted pattern.
IV_FONT = "LiberationSerif-Bold.ttf"
WORD_FONT = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")
WORD_CAP = 9            # cap height of the word in px
WORD_GAP = 3            # dark rows between the word and the icon
WORDS = {
    "allidlevillagers": ("IDLE", "_farmer"),     # Ctrl+.
    "allidlemilitary": ("IDLE", "_swords"),      # Ctrl+,
    "allvillagers": ("ALL", "_farmer"),          # Ctrl+Shift+V
    "allmilitary": ("ALL", "_swords"),           # Ctrl+Shift+C
    "allunits": ("ALL", "_people"),              # Ctrl+Shift+A
}


def reuse(out: Path) -> None:
    for name, src in REUSED.items():
        shutil.copyfile(SETS / src, out / name)
    print(f"  {len(REUSED)} icons copied from the aoe2 and warcraft3 sets")


def _fit(path: Path, box):
    """The icon's ink scaled to fit `box` (w, h), 1-bit."""
    import numpy as np
    from PIL import Image
    alpha = Image.open(path).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    scale = min(box[0] / alpha.width, box[1] / alpha.height)
    alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                         Image.LANCZOS)
    return np.asarray(alpha) > 150


def _paste(canvas, m, x, y):
    canvas[y:y + m.shape[0], x:x + m.shape[1]] |= m


def flat_icons(out: Path) -> None:
    """Every new key icon as a flat 1-bit silhouette, drawn at exactly its key
    area so the generator places it 1:1 (as Warcraft III's flat_icons())."""
    import numpy as np
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        m = _fit(out / f"{stem}.png", INK.get(stem, size))
        canvas = np.zeros((size[1], size[0]), bool)
        _paste(canvas, m, size[0] - m.shape[1], size[1] - m.shape[0])
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def _word(text: str):
    """`text` in Liberation Sans Bold with a cap height of WORD_CAP px, 1-bit."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    ss = 8
    ref = ImageFont.truetype(str(WORD_FONT), 200).getbbox("H")
    f = ImageFont.truetype(str(WORD_FONT), round(200 * WORD_CAP * ss / (ref[3] - ref[1])))
    l, t, r, b = f.getbbox(text)
    im = Image.new("L", (r - l + 2 * ss, b - t + 2 * ss), 0)
    ImageDraw.Draw(im).text((ss - l, ss - t), text, font=f, fill=255)
    im = im.resize((im.width // ss, im.height // ss), Image.BOX)
    m = np.asarray(im) > 110
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def words(out: Path) -> None:
    """A word over an icon, right-aligned in a 40 x 40 area: IDLE / ALL."""
    import numpy as np
    for stem, (text, part) in WORDS.items():
        w = _word(text)
        h = 40 - w.shape[0] - WORD_GAP
        icon = _fit(out / f"{part}.png", (40, h))
        canvas = np.zeros((40, 40), bool)
        _paste(canvas, w, 40 - w.shape[1], 0)
        _paste(canvas, icon, 40 - icon.shape[1], 40 - icon.shape[0])
        cnc._save_mask(canvas, out / f"{stem}.png")
        print(f"  {stem}.png  <- {text} + {part}.png")


def _clear_around(base, top, n):
    """`top` over `base`, with `n` px of `base` cleared around `top`'s ink."""
    return (base & ~program_mark.dilate(top, n)) | top


def capital(out: Path) -> None:
    """capital.png (Ctrl+H, the capital Town Center): the village of H with a
    crown over its top-left corner."""
    import numpy as np
    village = np.zeros((40, 40), bool)
    v = _fit(out / "_village.png", (40, 40))
    _paste(village, v, 40 - v.shape[1], 40 - v.shape[0])
    crown = np.zeros((40, 40), bool)
    c = _fit(out / "_crown.png", (18, 16))
    _paste(crown, c, 40 - v.shape[1], 0)
    cnc._save_mask(_clear_around(village, crown, 2), out / "capital.png")
    print("  capital.png  <- _village.png + _crown.png")


def pings(out: Path) -> None:
    """pingattack.png and pingdefend.png (Ctrl+R, Ctrl+T): the map marker of
    the notify ping (Ctrl+E) with a sword or a shield in its lower right."""
    import numpy as np
    marker = np.zeros((40, 40), bool)
    m = _fit(out / "_marker.png", (40, 34))
    _paste(marker, m, 0, 0)
    for stem, part, box in (("pingattack", "_sword", (24, 24)), ("pingdefend", "_shield", (20, 22))):
        sym = np.zeros((40, 40), bool)
        s = _fit(out / f"{part}.png", box)
        _paste(sym, s, 40 - s.shape[1], 40 - s.shape[0])
        cnc._save_mask(_clear_around(marker, sym, 2), out / f"{stem}.png")
        print(f"  {stem}.png  <- _marker.png + {part}.png")


def select_screen(out: Path) -> None:
    """selectscreen.png (Ctrl+A, all units on the screen): people inside the
    four corners of a screen."""
    import numpy as np
    canvas = np.zeros((40, 40), bool)
    _paste(canvas, _fit(out / "_frame.png", (40, 40)), 0, 0)
    p = _fit(out / "_people.png", (26, 22))
    _paste(canvas, p, (40 - p.shape[1]) // 2, (40 - p.shape[0]) // 2)
    cnc._save_mask(canvas, out / "selectscreen.png")
    print("  selectscreen.png  <- _frame.png + _people.png")


def subgroup_back(out: Path) -> None:
    """subgroupback.png (Ctrl+Tab, cycle backwards): Tab's cycle arrows
    mirrored, so they turn the other way."""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(out / "subgroup.png").convert("RGBA").getchannel("A")) > 127
    cnc._save_mask(a[:, ::-1], out / "subgroupback.png")
    print("  subgroupback.png  <- subgroup.png mirrored")


def groups_add(out: Path) -> None:
    """groupadd<N>.png (Shift+digit, add the selection to the group): AoE2's
    group picture with Warcraft III's ringed plus."""
    import numpy as np
    from PIL import Image
    for d in "0123456789":
        a = Image.open(out / f"group{d}.png").convert("RGBA").getchannel("A")
        g = np.asarray(a.crop(a.getbbox())) > 127
        aoe2._save_cell(wc3._with_ring_plus(g), out / f"groupadd{d}.png")
    print("  groupadd0..9.png  <- group<N>.png + a ringed plus")


def program(out: Path) -> None:
    """program.png: AoE2's mark with a dotted "IV" behind "Age of Empires"."""
    import numpy as np
    W, H = program_mark.W, program_mark.H
    iv = np.zeros((H, W), bool)
    g = program_mark.text("IV", IV_FONT, 56)
    if g.shape[1] > W - 4:                      # IV is wider than II: fit 68 px
        px = int(56 * (W - 4) / g.shape[1])
        g = program_mark.text("IV", IV_FONT, px)
    g = g[:H, :W]
    program_mark.place(iv, g, W // 2, (H - g.shape[0]) // 2)
    yy, xx = np.mgrid[0:H, 0:W]
    light = ((xx % 2) == 0) & ((yy % 2) == 0)
    lines = [program_mark.text("Age", program_mark.TITLE_FONT, 14), program_mark.of_line(),
             program_mark.text("Empires", program_mark.TITLE_FONT, 14)]
    words_ = np.zeros((H, W), bool)
    y = (H - sum(line.shape[0] for line in lines)) // 2
    for line in lines:
        program_mark.place(words_, line[:, :W], W // 2, y)
        y += line.shape[0]
    cnc._save_mask((iv & light & ~program_mark.dilate(words_, 1)) | words_, out / "program.png")
    print("  program.png  <- Age of Empires over a dotted IV")


def main(argv) -> int:
    redraw = "--redraw" in argv
    out = HERE / "icons"
    out.mkdir(exist_ok=True)
    reuse(out)
    cnc.render({**ICONS, **PARTS}, out)
    flat_icons(out)
    drawn = {"program.png": program, "capital.png": capital, "pingattack.png": pings,
             "pingdefend.png": pings, "selectscreen.png": select_screen,
             "subgroupback.png": subgroup_back, "groupadd0.png": groups_add}
    for name in WORDS:
        drawn[f"{name}.png"] = words
    done = set()
    for name, fn in drawn.items():
        if fn in done:
            continue
        if not redraw and (out / name).exists():
            print(f"  {name}  <- committed asset (left as is)")
            continue
        fn(out)
        done.add(fn)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
