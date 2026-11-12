#!/usr/bin/env python3
"""Fetch + render the SketchUp shortcut icons (reproducible).

Every tool SketchUp shares with another CAD or drawing set uses that set's
file, copied byte for byte (`BORROW`, `BORROW_AS`), so one action has one
glyph across the sets. The rest are Material Symbols (Apache-2.0) through `ms:`
names.

The ESC mark is the SketchUp logo from forums.sketchup.com's favicon (the
sketchup.com favicon is the Trimble globe), fitted into 32x32 and reduced to
1 bit (dark pixels lit), white on transparent for `program_icon_mode: alpha`.
It is guarded: a committed sketchup.png is left as it is.

    pip install cairosvg Pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/sketchup/fetch_icons.py
"""
from __future__ import annotations

import io
import shutil
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

HERE = Path(__file__).resolve().parent

MARK_URL = "https://www.google.com/s2/favicons?domain=forums.sketchup.com&sz=256"
MARK_PX = 32
MARK_DARK_LUMA = 170   # pixels darker than this (the blue logo) are lit

FLUENT = {
    "select": "ms:arrow_selector_tool",
    "search": "ms:search",
    "zoomextents": "ms:zoom_out_map",
    "photomatch": "ms:photo_camera",
    "backedges": "ms:line_style",      # same spec as fusion construction.png
}

# Same action, same file name as another set: byte-identical copies.
BORROW = {
    "line.png": "fusion",
    "rectangle.png": "fusion",
    "circle.png": "fusion",
    "move.png": "fusion",
    "presspull.png": "fusion",
    "offset.png": "fusion",
    "measure.png": "fusion",
    "rotate.png": "blender",
    "scale.png": "blender",
    "arc.png": "visio",
    "lasso.png": "illustrator",
    "eraser.png": "illustrator",
    "bucket.png": "paintdotnet",
    "hand.png": "photoshop",
    "orbit.png": "effectcraft",
    "zoom.png": "photoshop",
}

# Same glyph as another set under another file name: {ours: (app, theirs)}.
BORROW_AS = {
    "component.png": ("autocad", "blocks.png"),
}


def _borrow_as(out: Path) -> int:
    for name, (app, src) in sorted(BORROW_AS.items()):
        dest = out / name
        if dest.exists():
            print(f"  {name}  <- committed asset (left as-is)")
        else:
            shutil.copyfile(HERE.parent / app / "icons" / src, dest)
            print(f"  {name}  <- copied from {app}/icons/{src}")
    return len(BORROW_AS)


def _mark(path: Path) -> None:
    """The SketchUp favicon contain-fitted into MARK_PX square, dark pixels lit."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    req = urllib.request.Request(MARK_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    icon = icon.crop(icon.getbbox())
    side = max(icon.size)
    square = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    square.alpha_composite(icon, ((side - icon.width) // 2, (side - icon.height) // 2))
    white = Image.new("RGBA", square.size, "white")
    white.alpha_composite(square)
    a = white.convert("L").resize((MARK_PX, MARK_PX), Image.LANCZOS).point(
        lambda v: 255 if v < MARK_DARK_LUMA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(path)
    print(f"  {path.name}  <- SketchUp favicon, 1-bit, dark pixels lit")


def main() -> int:
    out = HERE / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    n += _borrow_as(out)
    _mark(out / "sketchup.png")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
