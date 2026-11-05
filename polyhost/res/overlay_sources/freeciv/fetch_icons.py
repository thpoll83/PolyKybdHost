#!/usr/bin/env python3
"""Fetch + render the Freeciv and Civilization icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0)
and game-icons.net (CC BY 3.0), as in the OpenTTD set. SOURCES.md credits each
icon. Each icon is drawn at exactly its key area, so the generator places it
1:1. A few icons are composed here: the connect orders (the terrain work with a
chain link), the battle groups (crossed sabres with the group number), the
"go and ..." orders and three zoom steps (a magnifier with a small text).

The ESC marks are text in Cinzel (SIL OFL 1.1): FREECIV, FREECIV + 21, CIV II
and CIV I. No logo art of Freeciv, Freeciv21, MicroProse or Firaxis is used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/freeciv/fetch_icons.py

The key icons are re-rendered on every run; the output does not change between
runs. The ESC marks are written only when their PNG is missing, so a hand edit
to a committed mark is kept.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402

# Every key icon: stem -> "fa:<name>" (Font Awesome Free 6.5.2, solid) or
# "gi:<author>/<name>" (game-icons.net).
ICONS = {
    # Unit orders (all clients)
    "build_city": "fa:building-flag",
    "road": "fa:road",
    "irrigate": "fa:faucet-drip",
    "cultivate": "fa:tractor",
    "mine": "gi:delapouite/mine-wagon",
    "plant": "fa:tree",
    "transform": "fa:mountain-sun",
    "convert": "fa:arrow-right-arrow-left",
    "clean": "fa:broom",
    "pillage": "fa:fire",
    "fortify": "fa:shield-halved",
    "fortress": "gi:delapouite/castle",
    "airbase": "fa:plane-arrival",
    "sentry": "fa:eye",
    "unsentry": "fa:bell",
    "goto": "fa:route",
    "return_city": "fa:arrow-right-to-city",
    "goto_city": "fa:map-location-dot",
    "explore": "fa:compass",
    "auto_worker": "fa:robot",
    "patrol": "fa:arrows-left-right",
    "wait": "fa:hourglass-half",
    "done": "fa:check",
    "load": "fa:right-to-bracket",
    "unload": "fa:right-from-bracket",
    "unload_all": "fa:truck-ramp-box",
    "home_city": "fa:house",
    "upgrade": "fa:circle-up",
    "disband": "fa:user-xmark",
    "do_action": "fa:hand-pointer",
    "paradrop": "fa:parachute-box",
    "nuke": "fa:bomb",
    "fallout": "fa:radiation",
    # Selection and view
    "select_single": "fa:user",
    "select_tile": "fa:users",
    "select_type_tile": "fa:people-group",
    "select_type_cont": "fa:earth-africa",
    "select_type_all": "fa:globe",
    "center": "fa:crosshairs",
    "capital": "fa:landmark-dome",
    "end_turn": "fa:forward-step",
    "zoom_in": "fa:magnifying-glass-plus",
    "zoom_out": "fa:magnifying-glass-minus",
    "chat": "fa:comment",
    # Reports (function keys)
    "map_view": "fa:map",
    "units_report": "fa:person-military-rifle",
    "nations": "fa:flag",
    "cities": "fa:city",
    "economy": "fa:coins",
    "research": "fa:flask",
    "wonders": "fa:landmark",
    "top_cities": "fa:trophy",
    "messages": "fa:envelope",
    "demographics": "fa:chart-column",
    "spaceship": "fa:rocket",
    # Government and game
    "tax": "fa:scale-balanced",
    "policies": "fa:sliders",
    "revolution": "fa:hand-fist",
    "find_city": "fa:magnifying-glass-location",
    "save": "fa:floppy-disk",
    "quit": "fa:power-off",
    "worklists": "fa:list-ol",
    "rally": "fa:flag-checkered",
    "infra": "fa:trowel-bricks",
    "editor": "fa:pen-ruler",
    # Map overlays
    "grid": "fa:table-cells",
    "borders": "fa:vector-square",
    "city_names": "fa:tag",
    "city_prod": "fa:industry",
    "trade_routes": "fa:money-bill-transfer",
    "outlines": "fa:draw-polygon",
    "city_output": "fa:wheat-awn",
    "city_growth": "fa:seedling",
    "native_tiles": "fa:shoe-prints",
    # Qt client and Freeciv21
    "delayed_goto": "fa:clock",
    "delayed_exec": "fa:play",
    "clear_orders": "fa:eraser",
    "trade_plan": "fa:handshake",
    "auto_caravan": "gi:delapouite/caravan",
    "quick_airlift": "fa:plane",
    "lock": "fa:lock",
    "adv_select": "fa:filter",
    "fullbar": "fa:bars-progress",
    "minimap": "fa:image",
    "units_sel": "fa:layer-group",
    "fullscreen": "fa:expand",
    "combat_info": "fa:burst",
    # Civilization II and Civilization I
    "activate": "fa:circle-play",
    "throne": "gi:delapouite/throne-king",
    "load_game": "fa:folder-open",
    "options": "fa:gear",
    "graphic_options": "fa:display",
    "report_options": "fa:table-list",
    "retire": "fa:person-walking-arrow-right",
    "council": "fa:users-rectangle",
    "pieces": "fa:chess-pawn",
    "hidden_terrain": "fa:eye-slash",
    "attitude": "fa:face-smile",
    "score": "fa:ranking-star",
    "intelligence": "fa:user-secret",
    "world_map": "fa:earth-americas",
    "luxury": "fa:champagne-glasses",
}

# Key area (w, h) of each icon; the default is 40 x 40. The function keys use
# the legend widths that the AoE2 and OpenTTD sets measured: F1 to F3 and F8
# 34 x 40, F4 to F7 30 x 40, F9 to F12 40 x 40.
SIZES = {
    "map_view": (34, 40), "units_report": (34, 40), "nations": (34, 40),
    "cities": (30, 40), "economy": (30, 40), "research": (30, 40),
    "wonders": (30, 40), "top_cities": (34, 40), "combat_info": (34, 40),
    "attitude": (30, 40), "intelligence": (34, 40),
}
# Icons used on a second key with a narrower area:
# stem -> (source stem, area). F1 "City status" in Civilization I and II.
NARROW = {"city_status": ("cities", (34, 40))}

# The box (w, h) the ink of a Font Awesome icon fills in a 40 x 40 area.
# Solid icons read heavier than game-icons.net line art, so they are smaller.
FA_BOX = (34, 34)
GI_BOX = (38, 38)
# Single icons that read heavier or lighter than the rest: their own box.
INK = {"done": (30, 30), "end_turn": (28, 30), "save": (30, 30), "options": (30, 30),
       "lock": (26, 32), "quit": (32, 32), "chat": (32, 32), "patrol": (36, 28),
       "convert": (36, 28), "zoom_in": (32, 32), "zoom_out": (32, 32)}

# Connect orders (Ctrl+R/L/M/I): the terrain work, with a chain link above.
CONNECT = {"connect_road": "fa:road", "connect_rail": "fa:train",
           "connect_maglev": "fa:train-subway", "connect_irrigation": "fa:faucet-drip"}
LINK = "fa:link"
# "Go and ..." orders (Qt, Freeciv21): the target, with the route icon above.
GO_AND = {"go_build": "fa:building-flag", "go_join": "fa:people-roof"}
ROUTE = "fa:route"
# Zoom steps with a small text above the magnifier (Civilization II, Qt).
ZOOM_TEXT = {"zoom_max": ("fa:magnifying-glass-plus", "MAX"),
             "zoom_std": ("fa:magnifying-glass", "1:1"),
             "zoom_mid": ("fa:magnifying-glass-minus", "MID")}
# Battle groups 1 to 4 on F1 to F4: crossed sabres with the group number.
# Shift selects (no mark), Ctrl assigns ("="), Ctrl+Shift appends ("+").
SWORDS = "gi:lorc/crossed-sabres"
GROUP_AREA = {"1": (34, 40), "2": (34, 40), "3": (34, 40), "4": (30, 40)}

# ESC marks: (file, lines). Each line is (text, cap height in px, centre y).
MARK_FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
                 "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf")
MARK_WEIGHT = 700                          # the Bold instance of the variable font
MARKS = {
    "program_freeciv.png": [("FREECIV", 70, 20, 20)],
    "program_freeciv21.png": [("FREECIV", 70, 16, 10), ("21", 40, 19, 29)],
    "program_civ2.png": [("CIV II", 70, 30, 20)],
    "program_civ1.png": [("CIV I", 70, 30, 20)],
}
SS = 8                                     # supersampling factor for drawn text
THRESHOLD = 100                            # grey level (0..255) from which a text pixel is lit


def _alpha(path: Path):
    from PIL import Image
    a = Image.open(path).convert("RGBA").getchannel("A")
    return a.crop(a.getbbox())


def _fit(path: Path, box: tuple[int, int], threshold: int = 150):
    """The icon's ink scaled to fit `box` (w, h), 1-bit: lit from alpha
    `threshold` (0..255)."""
    import numpy as np
    from PIL import Image
    a = _alpha(path)
    k = min(box[0] / a.width, box[1] / a.height)
    a = a.resize((max(1, round(a.width * k)), max(1, round(a.height * k))), Image.LANCZOS)
    return np.asarray(a) > threshold


def _corner(m, size: tuple[int, int]):
    """`m` in the bottom-right corner of a `size` (w, h) canvas."""
    import numpy as np
    canvas = np.zeros((size[1], size[0]), bool)
    canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
    return canvas


def _box(stem: str, spec: str, size: tuple[int, int]) -> tuple[int, int]:
    if stem in INK:
        return INK[stem]
    w, h = GI_BOX if spec.startswith("gi:") else FA_BOX
    return min(w, size[0]), min(h, size[1])


def flat_icons(raw: Path, out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette at exactly its key area."""
    for stem, spec in ICONS.items():
        size = SIZES.get(stem, (40, 40))
        cnc._save_mask(_corner(_fit(raw / f"{stem}.png", _box(stem, spec, size)), size),
                       out / f"{stem}.png")
    for stem, (src, size) in NARROW.items():
        box = _box(src, ICONS[src], size)
        cnc._save_mask(_corner(_fit(raw / f"{src}.png", box), size), out / f"{stem}.png")
    print(f"  {len(ICONS) + len(NARROW)} key icons drawn flat")


def _text(text: str, cap: int):
    """`text` in DejaVu Sans Bold with a cap height of `cap` px, 1-bit, cropped."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    path = str(cnc._font(cnc.DIGIT_FONT_URL))
    ref = ImageFont.truetype(path, 200).getbbox("H")
    f = ImageFont.truetype(path, round(200 * cap * SS / (ref[3] - ref[1])))
    b = f.getbbox(text)
    im = Image.new("L", (b[2] - b[0] + 2 * SS, b[3] - b[1] + 2 * SS), 0)
    ImageDraw.Draw(im).text((SS - b[0], SS - b[1]), text, font=f, fill=255)
    m = np.asarray(im.resize((im.width // SS, im.height // SS), Image.BOX)) > 110
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _put(canvas, m, x: int, y: int) -> None:
    """OR `m` into `canvas` with its top-left corner at (x, y)."""
    canvas[y:y + m.shape[0], x:x + m.shape[1]] |= m


def _clear(canvas, m, x: int, y: int, gap: int = 2) -> None:
    """Draw `m` at (x, y) with `gap` px cleared around it."""
    from polyhost.res.overlay_sources.aoe2 import program_mark
    import numpy as np
    layer = np.zeros_like(canvas)
    _put(layer, m, x, y)
    canvas &= ~program_mark.dilate(layer, gap)
    canvas |= layer


def composed(raw: Path, out: Path) -> None:
    """The connect orders, the "go and ..." orders and the zoom steps: an icon
    in the lower part of a 40 x 40 area with a small mark above it."""
    import numpy as np
    for stem in CONNECT:
        m = _corner(_fit(raw / f"{stem}.png", (30, 26)), (40, 40))
        _clear(m, _fit(raw / "_link.png", (18, 12)), 2, 0)
        cnc._save_mask(m, out / f"{stem}.png")
    for stem in GO_AND:
        m = _corner(_fit(raw / f"{stem}.png", (30, 26)), (40, 40))
        _clear(m, _fit(raw / "_route.png", (14, 12)), 2, 0)
        cnc._save_mask(m, out / f"{stem}.png")
    for stem, (_spec, word) in ZOOM_TEXT.items():
        m = _corner(_fit(raw / f"{stem}.png", (28, 28)), (40, 40))
        t = _text(word, 8)
        _clear(m, t, 40 - t.shape[1], 0)
        cnc._save_mask(m, out / f"{stem}.png")
    print(f"  {len(CONNECT) + len(GO_AND) + len(ZOOM_TEXT)} composed icons drawn")


def battle_groups(raw: Path, out: Path) -> None:
    """bg_select<N>.png (Shift+F<N>), bg_assign<N>.png (Ctrl+F<N>) and
    bg_append<N>.png (Ctrl+Shift+F<N>): crossed sabres at the bottom right,
    the group number at the top left of the area, and "=" or "+" at the top
    right for assign and append."""
    import numpy as np
    # Lit from alpha 80, not 150, so the thin blades keep their width.
    swords = _fit(raw / "_swords.png", (26, 26), threshold=80)
    marks = {"select": None, "assign": _text("=", 8), "append": _text("+", 9)}
    for n, size in GROUP_AREA.items():
        digit = _text(n, 14)
        for kind, mark in marks.items():
            m = _corner(swords, size)
            _clear(m, digit, 0, 0)
            if mark is not None:
                _clear(m, mark, size[0] - mark.shape[1], 1)
            cnc._save_mask(m, out / f"bg_{kind}{n}.png")
    print("  bg_select1..4, bg_assign1..4, bg_append1..4  <- crossed sabres + number")


def _cinzel(text: str, max_w: int, max_h: int):
    """`text` in Cinzel Bold at the largest size that fits max_w x max_h px."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    path = str(cnc._font(MARK_FONT_URL))
    for px in range(600, 40, -4):
        f = ImageFont.truetype(path, px)
        f.set_variation_by_axes([MARK_WEIGHT])
        b = f.getbbox(text)
        if b[2] - b[0] <= max_w * SS and b[3] - b[1] <= max_h * SS:
            break
    im = Image.new("L", (b[2] - b[0] + 2 * SS, b[3] - b[1] + 2 * SS), 0)
    ImageDraw.Draw(im).text((SS - b[0], SS - b[1]), text, font=f, fill=255)
    m = np.asarray(im.resize((im.width // SS, im.height // SS), Image.BOX)) > THRESHOLD
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def marks(out: Path) -> None:
    """The ESC marks, each over the whole 72 x 40 cell, the lines centred."""
    import numpy as np
    for name, lines in MARKS.items():
        path = out / name
        if path.exists():
            print(f"  {name}  <- committed asset (left as-is)")
            continue
        canvas = np.zeros((40, 72), bool)
        for text, max_w, max_h, cy in lines:
            m = _cinzel(text, max_w, max_h)
            _put(canvas, m, round(36 - m.shape[1] / 2), round(cy - m.shape[0] / 2))
        cnc._save_mask(canvas, path)
        print(f"  {name}  <- {' / '.join(t for t, *_ in lines)} (Cinzel Bold)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        cnc.render({**ICONS, **CONNECT, **GO_AND,
                    **{stem: spec for stem, (spec, _) in ZOOM_TEXT.items()},
                    "_link": LINK, "_route": ROUTE, "_swords": SWORDS}, raw)
        flat_icons(raw, out)
        composed(raw, out)
        battle_groups(raw, out)
    marks(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
