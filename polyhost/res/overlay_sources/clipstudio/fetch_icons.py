#!/usr/bin/env python3
"""Fetch + render the Clip Studio Paint shortcut icons (reproducible).

Most keys use the Photoshop set (`../photoshop/icons`, the spec's `icon_dir`)
where the tool or command is the same. This script writes only the icons that
set has no picture for:

* Microsoft Fluent UI System Icons (MIT) and Material Symbols (Apache-2.0,
  `ms:` names) through `icon_fetch.fluent`;
* copies of icons other sets already draw for the same action
  (`icon_fetch.borrow`), so the overlay icon library stores each one once;
* a few drawn glyphs (white on transparent, `mode: alpha`) for the Clip Studio
  commands no icon set has: transparent colour, delete outside selection,
  reselect, opacity, brush density and particle density;
* the program mark (ESC). Celsys's logo is proprietary and Simple Icons has
  no `clipstudiopaint` entry, so the mark is a drawn substitute: a pen nib in a
  rounded tile. It is not the Celsys logo.

Drawn glyphs and the program mark are guarded: a committed file is left as it
is, so a hand edit survives a re-run.

    pip install cairosvg
    PYTHONPATH=. python polyhost/res/overlay_sources/clipstudio/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

RENDER_PX = 96
SS = 4
WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)

# Fluent folder names, or `ms:<name>` for Material Symbols.
FLUENT = {
    # --- tools ---
    "rotateview": "Arrow Rotate Clockwise",
    "selectlayer": "Cursor Click",
    "lighttable": "ms:view_timeline",
    "blend": "Drop",
    "correctline": "Pen Sparkle",
    "prevtool": "Arrow Previous",
    "nexttool": "Arrow Next",
    "refermultiple": "ms:layers",
    # --- view / window ---
    "rotateleft": "Arrow Rotate Counterclockwise",
    "palettes": "Panel Left",
    "tutorials": "Hat Graduation",
    "snapruler": "ms:square_foot",
    "snapspecial": "ms:architecture",
    "snapgrid": "ms:grid_on",
    "togglespecial": "Toggle Right",
    # --- file / edit ---
    "quit": "Arrow Exit",
    "erase": "Delete",
    "pasteinplace": "ms:content_paste_go",
    "csptransform": "ms:transform",
    "shortcutset": "Keyboard",
    "modkeyset": "Keyboard Shift",
    # --- layer ---
    "newfolder": "Folder Add",
    "ungroup": "Folder Arrow Up",
    "mergesel": "ms:merge",
    "mergevis": "Eye",
    "layerabove": "Arrow Circle Up",
    "layerbelow": "Arrow Circle Down",
    "layercolor": "ms:filter_b_and_w",
}

# One drawing per action, shared with the set that drew it first.
BORROWED = {
    "settings.png": "webapps",       # Preferences (Fluent Settings)
    "pp_clipmask.png": "webapps",    # Clip to layer below (Photopea's clipping mask)
    "nextdoc.png": "acrobat",        # Next canvas (ms:tab)
    "prevdoc.png": "acrobat",        # Previous canvas (ms:tab_move)
}


def _canvas():
    u = RENDER_PX * SS
    img = Image.new("RGBA", (u, u), CLEAR)
    return img, ImageDraw.Draw(img), u


def _save(img: Image.Image, path: Path) -> None:
    img.resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def _checker(d, box, n, u):
    """Fill every other square of an n x n grid inside `box` (transparency)."""
    x0, y0, x1, y1 = box
    sw, sh = (x1 - x0) / n, (y1 - y0) / n
    for i in range(n):
        for j in range(n):
            if (i + j) % 2 == 0:
                d.rectangle([x0 + i * sw, y0 + j * sh, x0 + (i + 1) * sw, y0 + (j + 1) * sh],
                            fill=WHITE)


def _draw_transparent(path: Path) -> None:
    """Switch drawing colour / transparent colour (C): a solid square in front
    of a checkered (transparent) square."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    back = (0.38 * u, 0.38 * u, 0.84 * u, 0.84 * u)
    d.rectangle(back, outline=WHITE, width=w)
    _checker(d, (back[0] + w, back[1] + w, back[2] - w, back[3] - w), 4, u)
    d.rectangle([0.14 * u, 0.14 * u, 0.50 * u, 0.50 * u], fill=CLEAR)
    d.rectangle([0.16 * u, 0.16 * u, 0.48 * u, 0.48 * u], fill=WHITE)
    _save(img, path)


def _dashed_rect(d, box, w, dash):
    x0, y0, x1, y1 = box
    x = x0
    while x < x1:
        d.line([(x, y0), (min(x + dash, x1), y0)], fill=WHITE, width=w)
        d.line([(x, y1), (min(x + dash, x1), y1)], fill=WHITE, width=w)
        x += 2 * dash
    y = y0
    while y < y1:
        d.line([(x0, y), (x0, min(y + dash, y1))], fill=WHITE, width=w)
        d.line([(x1, y), (x1, min(y + dash, y1))], fill=WHITE, width=w)
        y += 2 * dash


def _draw_outsidesel(path: Path) -> None:
    """Delete outside selection (Shift+Del): a lit frame with an empty dashed
    selection inside it."""
    img, d, u = _canvas()
    d.rectangle([0.10 * u, 0.16 * u, 0.90 * u, 0.84 * u], fill=WHITE)
    d.rectangle([0.30 * u, 0.34 * u, 0.70 * u, 0.66 * u], fill=CLEAR)
    _save(img, path)


def _draw_reselect(path: Path) -> None:
    """Reselect (Ctrl+Shift+D): a dashed selection with a circular arrow."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    _dashed_rect(d, (0.10 * u, 0.14 * u, 0.62 * u, 0.62 * u), w, u * 0.08)
    cx, cy, r = 0.68 * u, 0.68 * u, 0.20 * u
    d.arc([cx - r, cy - r, cx + r, cy + r], start=100, end=380, fill=WHITE, width=w)
    # arrow head at the arc's start (pointing down-left)
    d.polygon([(cx - 0.02 * u, cy + r - 0.10 * u), (cx - 0.02 * u, cy + r + 0.10 * u),
               (cx - 0.16 * u, cy + r)], fill=WHITE)
    _save(img, path)


def _sign(d, cx, cy, s, w, plus):
    d.line([(cx - s, cy), (cx + s, cy)], fill=WHITE, width=w)
    if plus:
        d.line([(cx, cy - s), (cx, cy + s)], fill=WHITE, width=w)


def _draw_opacity(path: Path, plus: bool) -> None:
    """Opacity -/+ (Ctrl+[ / Ctrl+]): a half-checkered disc with a minus or plus."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    box = [0.08 * u, 0.24 * u, 0.60 * u, 0.76 * u]
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse(box, fill=255)
    chk = Image.new("RGBA", img.size, CLEAR)
    dc = ImageDraw.Draw(chk)
    if plus:
        dc.rectangle(box, fill=WHITE)
    else:
        _checker(dc, box, 5, u)
    img.paste(chk, (0, 0), mask)
    d.ellipse(box, outline=WHITE, width=w)
    _sign(d, 0.80 * u, 0.50 * u, 0.12 * u, int(u * 0.06), plus)
    _save(img, path)


def _draw_density(path: Path, plus: bool) -> None:
    """Brush density -/+ (Ctrl+Shift+O / P): a row of brush-tip circles, spaced
    apart or overlapping, with a minus or plus."""
    img, d, u = _canvas()
    w = int(u * 0.05)
    r = 0.14 * u
    n, step = (2, 0.36 * u) if not plus else (4, 0.12 * u)
    x = 0.06 * u + r
    for _ in range(n):
        d.ellipse([x - r, 0.50 * u - r, x + r, 0.50 * u + r], outline=WHITE, width=w)
        x += step
    _sign(d, 0.86 * u, 0.50 * u, 0.11 * u, int(u * 0.07), plus)
    _save(img, path)


def _draw_particles(path: Path, plus: bool) -> None:
    """Particle density -/+ (Ctrl+Shift+K / L): a few or many spray dots, with a
    minus or plus."""
    img, d, u = _canvas()
    pts = [(0.14, 0.24), (0.50, 0.30), (0.28, 0.56), (0.56, 0.74), (0.12, 0.82)]
    if plus:
        pts += [(0.32, 0.14), (0.62, 0.50), (0.34, 0.36), (0.14, 0.52),
                (0.40, 0.84), (0.46, 0.58), (0.60, 0.14)]
    r = 0.06 * u
    for px, py in pts:
        d.ellipse([px * u - r, py * u - r, px * u + r, py * u + r], fill=WHITE)
    _sign(d, 0.86 * u, 0.50 * u, 0.11 * u, int(u * 0.07), plus)
    _save(img, path)


def _draw_csp_mark(path: Path) -> None:
    """Program mark: a filled rounded tile with a pen nib knocked out (a drawing
    app). A substitute, NOT the Celsys logo. 256 px, white on transparent."""
    size = 256
    u = size * SS
    img = Image.new("RGBA", (u, u), CLEAR)
    d = ImageDraw.Draw(img)
    pad = int(u * 0.06)
    d.rounded_rectangle([pad, pad, u - pad, u - pad], radius=int(u * 0.18), fill=WHITE)
    # pen nib pointing down: a pointed shield shape, with a slit and a vent hole
    cx = u / 2
    top, shoulder, tip = 0.18 * u, 0.50 * u, 0.86 * u
    hw = 0.24 * u
    d.polygon([(cx - hw * 0.62, top), (cx + hw * 0.62, top), (cx + hw, shoulder),
               (cx, tip), (cx - hw, shoulder)], fill=CLEAR)
    # the slit and the vent hole are tile colour again
    d.line([(cx, 0.48 * u), (cx, tip - 0.02 * u)], fill=WHITE, width=int(u * 0.04))
    vr = 0.055 * u
    d.ellipse([cx - vr, 0.44 * u - vr, cx + vr, 0.44 * u + vr], fill=WHITE)
    img.resize((size, size), Image.LANCZOS).save(path)


DRAWN = {
    "transparentcolor": _draw_transparent,
    "outsidesel": _draw_outsidesel,
    "reselect": _draw_reselect,
    "opacitydec": lambda p: _draw_opacity(p, False),
    "opacityinc": lambda p: _draw_opacity(p, True),
    "densitydec": lambda p: _draw_density(p, False),
    "densityinc": lambda p: _draw_density(p, True),
    "particledec": lambda p: _draw_particles(p, False),
    "particleinc": lambda p: _draw_particles(p, True),
    "clipstudio": _draw_csp_mark,
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out, render_px=RENDER_PX)
    icon_fetch.borrow(BORROWED, out)
    for stem, fn in DRAWN.items():
        p = out / f"{stem}.png"
        if p.exists():
            print(f"  {p.name}  <- committed asset (left as-is)")
        else:
            fn(p)
            print(f"  {p.name}  <- custom (drawn)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
