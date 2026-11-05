#!/usr/bin/env python3
"""Fetch + render the Civilization IV icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0)
and game-icons.net (CC BY 3.0), as in the OpenTTD set. SOURCES.md credits
each icon. The ESC mark is the text CIV IV set in Cinzel (SIL OFL 1.1). No
Firaxis art is used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/civ4/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.openttd import fetch_icons as ottd  # noqa: E402

# One icon per key. "fa:" is Font Awesome Free 6.5.2 solid, "gi:" game-icons.net.
ICONS = {
    # Advisors and screens (F1 to F12, Shift+F7, Alt+F1)
    "domestic": "fa:city",
    "financial": "fa:coins",
    "civics": "fa:landmark",
    "foreign": "fa:handshake-simple",
    "military": "gi:lorc/crossed-swords",
    "technology": "fa:flask",
    "religion": "fa:place-of-worship",
    "corporation": "fa:briefcase",
    "victory": "fa:trophy",
    "info": "fa:chart-column",
    "capital": "fa:star",
    "globe": "fa:earth-americas",
    "civilopedia": "fa:book-open",
    "freecolony": "fa:flag",
    # Turn
    "skip": "fa:forward-step",
    "endturn": "fa:hourglass-end",
    "forceendturn": "fa:forward-fast",
    "wait": "fa:clock",
    # Unit orders
    "foundcity": "fa:building-flag",
    "fortify": "fa:shield-halved",
    "sentry": "fa:binoculars",
    "heal": "fa:shield-heart",
    "loadunit": "fa:right-to-bracket",
    "pillage": "fa:fire",
    "ping": "fa:bullseye",
    "routeto": "fa:route",
    "goto": "fa:location-dot",
    "automate": "fa:robot",
    "automoves": "fa:circle-play",
    "airlift": "fa:plane",
    "explore": "fa:compass",
    "improvecity": "fa:person-digging",
    "mine": "gi:lorc/mining",
    "road": "fa:road",
    "farm": "fa:tractor",
    "workshop": "gi:lorc/anvil",
    "cottage": "fa:house-chimney",
    "quarry": "fa:cubes-stacked",
    "fort": "fa:chess-rook",
    "preserve": "fa:tree",
    "offshore": "gi:delapouite/oil-rig",
    "unload": "fa:person-walking-arrow-right",
    "delete": "fa:trash-can",
    "cancel": "fa:ban",
    # Selection
    "centre": "fa:crosshairs",
    "selecttype": "fa:people-group",
    "selectwounded": "fa:heart-pulse",
    "selectcity": "fa:house-flag",
    "cycleworkers": "fa:helmet-safety",
    "lastunit": "fa:backward-step",
    # View
    "grid": "fa:table-cells",
    "baremap": "fa:map",
    "yields": "gi:lorc/wheat",
    "resources": "fa:gem",
    "enemyunits": "fa:eye",
    "ortho": "fa:cube",
    "flymodes": "fa:video",
    "rotleft": "fa:rotate-left",
    "rotright": "fa:rotate-right",
    "flying": "fa:paper-plane",
    "mousefly": "fa:computer-mouse",
    "topdown": "fa:arrows-down-to-line",
    # Game
    "save": "fa:floppy-disk",
    "load": "fa:folder-open",
    "options": "fa:gear",
    "retire": "fa:door-open",
    "worldbuilder": "fa:mountain-sun",
    "halloffame": "fa:medal",
    "espionage": "fa:user-secret",
    "diplomacy": "fa:user-tie",
    "details": "fa:id-card",
    "gamedetails": "fa:circle-info",
    "sign": "fa:signs-post",
    "chatteam": "fa:comment",
    "chatall": "fa:bullhorn",
    "eventlog": "fa:list",
}

# Sources of the composed icons, rendered as `_<stem>.png` and not drawn on a key.
PARTS = {"_bolt": "fa:bolt", "_person": "fa:person", "_city": "fa:city",
         "_unload": "fa:person-walking-arrow-right", "_cancel": "fa:ban",
         "_robot": "fa:robot"}

# Key area of each icon, from civ4_bts.yaml; the default is 40 x 40.
SIZES = {"domestic": (34, 40), "financial": (34, 40), "civics": (34, 40), "freecolony": (34, 40),
         "foreign": (30, 40), "military": (30, 40), "technology": (30, 40),
         "religion": (30, 40), "corporation": (30, 40), "quicksave": (30, 40),
         "victory": (34, 40), "quickload": (34, 40), "chatteam": (30, 40),
         "chatall": (30, 40), "eventlog": (30, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"domestic": (34, 32), "financial": (30, 30), "civics": (30, 30), "freecolony": (28, 30),
       "foreign": (30, 26), "technology": (26, 30), "corporation": (28, 26),
       "victory": (30, 30), "info": (32, 30), "capital": (32, 32), "globe": (32, 32),
       "civilopedia": (36, 30), "skip": (28, 30), "endturn": (24, 32), "forceendturn": (34, 30),
       "wait": (32, 32), "goto": (24, 32), "automate": (36, 30), "automoves": (32, 32),
       "explore": (32, 32), "fort": (26, 32), "delete": (28, 32), "cancel": (32, 32),
       "centre": (34, 34), "selectwounded": (34, 30), "selectcity": (34, 32),
       "cycleworkers": (34, 30), "lastunit": (28, 30), "grid": (32, 30), "baremap": (34, 30),
       "resources": (34, 30), "enemyunits": (36, 28), "ortho": (30, 32), "flymodes": (36, 28),
       "rotleft": (32, 32), "rotright": (32, 32), "flying": (34, 34), "mousefly": (22, 32),
       "save": (30, 30), "load": (36, 30), "options": (32, 32), "retire": (36, 32),
       "worldbuilder": (36, 32), "espionage": (30, 34), "diplomacy": (28, 34),
       "details": (36, 28), "gamedetails": (32, 32), "chatteam": (30, 30),
       "chatall": (30, 28), "eventlog": (30, 28), "unload": (36, 32),
       "foundcity": (36, 32), "fortify": (28, 32), "sentry": (34, 30), "heal": (30, 32),
       "loadunit": (32, 30), "pillage": (28, 32), "ping": (32, 32), "routeto": (34, 32),
       "road": (34, 30), "farm": (36, 30), "workshop": (36, 28)}

# Composed icons: a glyph with a mark, or a glyph drawn twice.
# stem -> (glyph, mark, key area). A mark is "=", "ALL", "bolt", "robot", ">" or "<".
BADGED = {"gototype": ("goto", "=", (40, 40)), "gotoall": ("goto", "ALL", (40, 40)),
          "quicksave": ("save", "bolt", (30, 40)), "quickload": ("load", "bolt", (34, 40)),
          "nextcity": ("_city", ">", (40, 40)), "prevcity": ("_city", "<", (40, 40)),
          "nextunit": ("_person", ">", (40, 40)), "prevunit": ("_person", "<", (40, 40)),
          "unloadall": ("_unload", "ALL", (40, 40)), "cancelall": ("_cancel", "ALL", (40, 40)),
          "network": ("road", "robot", (40, 40))}
TWICE = {"savegroup": "save"}

# The ESC mark: CIV IV in Cinzel Bold (SIL OFL 1.1), centred on the whole cell.
MARK_FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
                 "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf")
MARK_TEXT = "CIV IV"
MARK_BOX = (70, 30)                          # the largest ink box the text may fill, px
MARK_SS = 8                                  # supersampling factor for drawn icons
MARK_THRESHOLD = 100                         # grey level (0..255) from which a mark pixel is lit


def _missing(path: Path) -> bool:
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return False
    return True


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key area
    so the generator places it 1:1. The icons in INK fill a smaller box in the
    bottom-right corner of that area."""
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        m = ottd._fit(out / f"{stem}.png", INK.get(stem, size))
        cnc._save_mask(ottd._corner(m, size), out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def _text(text: str, cap: int):
    """`text` in DejaVu Sans Bold with a cap height of `cap` px, 1-bit, cropped."""
    return ottd._badge_text(text, cap)


def _chevron(right: bool, h: int = 13):
    """A filled triangle pointing right or left, `h` px high."""
    w = (h + 1) // 2 + 1
    m = ottd._draw([[(0, 0), (w, h / 2), (0, h)]], (w, h))
    return m if right else m[:, ::-1]


def _mark(kind: str):
    if kind == "bolt":
        return ottd._fit(Path(OUT) / "_bolt.png", (10, 15))
    if kind == "robot":
        return ottd._fit(Path(OUT) / "_robot.png", (16, 13))
    if kind in "<>":
        return _chevron(kind == ">")
    if kind == "=":
        import numpy as np
        m = np.zeros((9, 11), bool)
        m[1:4, :] = True
        m[6:9, :] = True
        return m
    return _text(kind, 8)


def badged(out: Path) -> None:
    """The glyph in the bottom-left of the key area and the mark in the top-right
    corner, with 2 px clear between them."""
    import numpy as np
    for stem, (glyph, kind, size) in BADGED.items():
        w, h = size
        g = ottd._fit(out / f"{glyph}.png", (w - 10, h - 8))
        gh, gw = g.shape
        base = np.zeros((h, w), bool)
        base[h - gh:, :gw] = g
        mk = _mark(kind)
        mh, mw = mk.shape
        badge = np.zeros((h, w), bool)
        badge[0:mh, w - mw:] = mk
        cnc._save_mask((base & ~program_mark.dilate(badge, 2)) | badge, out / f"{stem}.png")
    print(f"  {', '.join(f'{s}.png' for s in BADGED)}  <- glyph + mark")


def twice(out: Path) -> None:
    """The glyph twice, the back copy 13 px up and to the right, 2 px clear
    around the front copy (as OpenTTD's close-all icon)."""
    import numpy as np
    for stem, src in TWICE.items():
        w = ottd._fit(out / f"_{src}_src.png", (24, 24))
        h, ww = w.shape
        back = np.zeros((40, 40), bool)
        front = np.zeros((40, 40), bool)
        back[40 - h - 13:40 - 13, 40 - ww:] = w
        front[40 - h:, 40 - ww - 13:40 - 13] = w
        cnc._save_mask((back & ~program_mark.dilate(front, 2)) | front, out / f"{stem}.png")
    print(f"  {', '.join(f'{s}.png' for s in TWICE)}  <- the glyph twice")


def program(out: Path) -> None:
    """program.png: CIV IV in Cinzel Bold at the largest size whose ink fits
    MARK_BOX, centred on the whole 72x40 cell."""
    path = out / "program.png"
    if not _missing(path):
        return
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font_path = str(cnc._font(MARK_FONT_URL))
    w, h, ss = 72, 40, MARK_SS
    for px in range(600, 40, -2):
        font = ImageFont.truetype(font_path, px)
        font.set_variation_by_name("Bold")
        b = font.getbbox(MARK_TEXT)
        if b[2] - b[0] <= MARK_BOX[0] * ss and b[3] - b[1] <= MARK_BOX[1] * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text(((w * ss - (b[2] - b[0])) // 2 - b[0],
                             (h * ss - (b[3] - b[1])) // 2 - b[1]), MARK_TEXT,
                            font=font, fill=255)
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD, path)
    print(f"  program.png  <- {MARK_TEXT} (Cinzel Bold, {(b[3] - b[1]) // ss} px high)")


OUT = Path(__file__).resolve().parent / "icons"


def main() -> int:
    out = OUT
    sources = {**ICONS, **PARTS, **{f"_{s}_src": ICONS[s] for s in set(TWICE.values())}}
    cnc.render(sources, out)
    badged(out)                      # before flat_icons, which redraws the sources
    twice(out)
    flat_icons(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
