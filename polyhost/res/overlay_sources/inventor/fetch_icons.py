#!/usr/bin/env python3
"""Fetch + render the Autodesk Inventor shortcut icons (reproducible).

Every command Inventor shares with another CAD set uses that set's file,
copied byte for byte (`BORROW`, `BORROW_AS`), so one action has one glyph
across the CAD sets. The rest are Material Symbols (Apache-2.0) through `ms:`
names.

Drawn here, 32x32 at 1 bit (black on transparent, so the spec's `luma` mode
lights the black pixels and the generator places them 1:1): the four work
features, a plane, an axis, a point and a grounded point.

The ESC mark is drawn too, because the Inventor logo is an Autodesk trademark
and no copy of the product icon could be fetched: a rounded tile with the
letter I (a plain bar) knocked out and an isometric cube outline on the right,
in the style of the AutoCAD set's mark. White on transparent, so the binding
renders it with `program_icon_mode: alpha`. Every drawn file is guarded: a
committed copy is left as it is.

    pip install cairosvg Pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/inventor/fetch_icons.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

HERE = Path(__file__).resolve().parent

FLUENT = {
    "showconstraints": "ms:link",
    "hideconstraints": "ms:link_off",
    "dimhud": "ms:input",
    "sketchplane": "ms:flip_to_back",
    "balloon": "ms:counter_1",
    "createcomp": "ms:add_box",
    "placecomp": "ms:place_item",
    "imate": "ms:extension",
    "revolve": "ms:360",
    "sketch2d": "ms:draw",
    "text": "ms:text_fields",
}

# Same action, same file name as another set: byte-identical copies.
BORROW = {
    "circle.png": "fusion",
    "dimension.png": "fusion",
    "extrude.png": "fusion",
    "fillet.png": "fusion",
    "hole.png": "fusion",
    "line.png": "fusion",
    "move.png": "fusion",
    "prevws.png": "fusion",
    "nextws.png": "fusion",
    "visibility.png": "fusion",
    "selcycle.png": "autocad",
    "infer.png": "autocad",
    "osnap.png": "autocad",
    "ortho.png": "tekla",
    "isometric.png": "freecad",
    "horizontal.png": "freecad",
    "hand.png": "photoshop",
    "zoom.png": "photoshop",
    "orbit.png": "effectcraft",
}

# Same glyph as another set under another file name: {ours: (app, theirs)}.
BORROW_AS = {
    "prevview.png": ("tekla", "zoomprev.png"),
    "slice.png": ("tekla", "clipplane.png"),
}

LIT = (0, 0, 0, 255)
CLEAR = (0, 0, 0, 0)
WHITE = (255, 255, 255, 255)


def _borrow_as(out: Path) -> int:
    for name, (app, src) in sorted(BORROW_AS.items()):
        dest = out / name
        if dest.exists():
            print(f"  {name}  <- committed asset (left as-is)")
        else:
            shutil.copyfile(HERE.parent / app / "icons" / src, dest)
            print(f"  {name}  <- copied from {app}/icons/{src}")
    return len(BORROW_AS)


def _dashdot(d: ImageDraw.ImageDraw, a, b, dash=7, gap=3, dot=2) -> None:
    """A centre line from a to b: long dash, gap, short dash, gap."""
    (x0, y0), (x1, y1) = a, b
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    t, pattern, i = 0.0, (dash, gap, dot, gap), 0
    while t < length:
        seg = min(pattern[i % 4], length - t)
        if i % 2 == 0:
            d.line([(round(x0 + ux * t), round(y0 + uy * t)),
                    (round(x0 + ux * (t + seg)), round(y0 + uy * (t + seg)))],
                   fill=LIT, width=2)
        t += seg
        i += 1


def _work_feature(path: Path, kind: str) -> None:
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    img = Image.new("RGBA", (32, 32), CLEAR)
    d = ImageDraw.Draw(img)
    if kind == "plane":
        d.polygon([(10, 6), (31, 6), (22, 27), (1, 27)], outline=LIT, width=2)
    elif kind == "axis":
        _dashdot(d, (2, 30), (30, 2))
    elif kind == "point":
        d.line([(16, 2), (16, 30)], fill=LIT, width=2)
        d.line([(2, 16), (30, 16)], fill=LIT, width=2)
        d.ellipse([10, 10, 22, 22], fill=CLEAR)
        d.ellipse([12, 12, 20, 20], fill=LIT)
    elif kind == "grounded":
        d.ellipse([11, 2, 21, 12], fill=LIT)
        d.rectangle([15, 12, 16, 20], fill=LIT)
        d.rectangle([4, 21, 27, 22], fill=LIT)
        d.rectangle([8, 25, 23, 26], fill=LIT)
        d.rectangle([12, 29, 19, 30], fill=LIT)
    img.save(path)
    print(f"  {path.name}  <- drawn work {kind}")


SIZE = 256
SS = 4


def _mark(path: Path) -> None:
    """Rounded tile, letter I knocked out, isometric cube outline at lower right."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    u = SIZE * SS
    pad = int(u * 0.055)
    img = Image.new("RGBA", (u, u), CLEAR)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([pad, pad, u - pad, u - pad], radius=int(u * 0.16), fill=WHITE)

    # The letter I as a plain bar: a font's I is too thin to survive 32 px.
    d.rectangle([int(u * 0.16), int(u * 0.20), int(u * 0.30), int(u * 0.80)], fill=CLEAR)

    # Isometric cube outline, cut out of the tile.
    cxu, cyu, r = int(u * 0.65), int(u * 0.50), int(u * 0.25)
    h = int(r * 0.5)
    top, ul, ur = (cxu, cyu - r), (cxu - r, cyu - h), (cxu + r, cyu - h)
    mid = (cxu, cyu)
    ll, lr, bot = (cxu - r, cyu + h), (cxu + r, cyu + h), (cxu, cyu + r)
    w = int(u * 0.07)
    for a, b in [(top, ur), (ur, lr), (lr, bot), (bot, ll), (ll, ul), (ul, top),
                 (ul, mid), (ur, mid), (mid, bot)]:
        d.line([a, b], fill=CLEAR, width=w)
    for p in (top, ul, ur, mid, ll, lr, bot):
        d.ellipse([p[0] - w // 2, p[1] - w // 2, p[0] + w // 2, p[1] + w // 2], fill=CLEAR)
    img.resize((SIZE, SIZE), Image.LANCZOS).save(path)
    print(f"  {path.name}  <- drawn program mark")


def main() -> int:
    out = HERE / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    n += _borrow_as(out)
    for kind in ("plane", "axis", "point", "grounded"):
        _work_feature(out / f"work{kind}.png", kind)
    _mark(out / "inventor.png")
    print(f"Wrote {n} icons (+ 4 drawn and the program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
