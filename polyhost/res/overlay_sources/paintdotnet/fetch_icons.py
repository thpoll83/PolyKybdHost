#!/usr/bin/env python3
"""Fetch + render the paint.net shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** via `icon_fetch`. Two
tool glyphs Fluent has no match for -- the gradient ramp and the clone stamp --
are drawn here; both are signature paint.net tools whose nearest Fluent glyph
would say the wrong thing. The ESC **program mark** is the shared license-clean
letter tile (`../program_marks.py`) reading "PN": paint.net's own icon is its
project artwork, and a bare "P" would collide with the Microsoft Paint overlay.

Shortcuts come from paint.net's OWN documentation (Keyboard & Mouse Commands),
so this is the documented set rather than a third-party summary. See SOURCES.md.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/paintdotnet/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import program_marks  # noqa: E402

FLUENT = {
    # --- file ---
    "new":     "Document Add",
    "open":    "Folder Open",
    "save":    "Save",
    "saveas":  "Save Edit",
    "saveall": "Save Multiple",
    "close":   "Document Dismiss",
    "print":   "Print",
    # --- edit ---
    "undo":       "Arrow Undo",
    "redo":       "Arrow Redo",
    "cut":        "Cut",
    "copy":       "Copy",
    "copymerged": "Layer Diagonal",
    "paste":      "Clipboard Paste",
    "pastelayer": "Layer Diagonal Add",
    "pasteimage": "Image Copy",
    "selectall":  "Select All On",
    "deselect":   "Select All Off",
    "invertsel":  "Border All",
    # --- view / zoom ---
    "zoomin":     "Zoom In",
    "zoomout":    "Zoom Out",
    "zoomwindow": "Zoom Fit",
    "zoomsel":    "Crop Interim",
    "actualsize": "Ratio One To One",
    # --- image ---
    "crop":     "Crop",
    "resize":   "Resize Image",
    "canvas":   "Slide Size",
    "rotatecw": "Rotate Right",
    "rotateccw": "Rotate Left",
    "flatten":  "Layer",
    # --- layers ---
    "newlayer":   "Layer Diagonal Add",
    "duplayer":   "Document Multiple",
    "dellayer":   "Delete",
    "mergedown":  "Arrow Between Down",
    "layervis":   "Eye",
    "rotatezoom": "Arrow Rotate Clockwise",
    "layerprops": "Options",
    "layerabove": "Arrow Up",
    "layerbelow": "Arrow Down",
    "toplayer":    "Arrow Upload",
    "bottomlayer": "Arrow Download",
    # --- adjustments ---
    "autolevel":  "Wand",
    "blackwhite": "Circle Half Fill",
    "brightness": "Brightness High",
    "curves":     "Data Line",
    "huesat":     "Color",
    "invertalpha": "Scan Type",
    "invertcolors": "Color Background",
    "levels":     "Data Histogram",
    "posterize":  "Filter",
    "sepia":      "Weather Sunny",
    "repeateffect": "Arrow Repeat All",
    # --- tools ---
    "rectselect": "Select Object",
    "lasso":      "Lasso",
    "movesel":    "Drag",
    "zoomtool":   "Search",
    "pan":        "Hand Right",
    "brush":      "Paint Brush",
    "pencil":     "Pen",
    "eraser":     "Eraser",
    "bucket":     "Paint Bucket",
    "picker":     "Eyedropper",
    "recolor":    "Color Line",
    "text":       "Text T",
    "linecurve":  "Line",
    "shapes":     "Shapes",
    # --- windows / colours ---
    "toolswin":   "Options",
    "historywin": "History",
    "layerswin":  "Layer Diagonal",
    "colorswin":  "Color",
    "swapcolors": "Arrow Swap",
    # --- tabs ---
    "nextimage": "Arrow Right",
    "previmage": "Arrow Left",
}


def _canvas(ss: int = 4, px: int = 96):
    u = px * ss
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), u


def _draw_gradient(path: Path) -> None:
    """Gradient tool: a framed square filled with a coarse light-to-dark ramp.

    ⚠️ Drawn rather than sourced. Fluent's nearest candidates say the wrong
    thing -- `Circle Half Fill` is a two-tone disc (used here for Black & White)
    and `Color Fill` is the paint bucket. A gradient is a RAMP, and at 1 bit it
    has to be a *dither* ramp: a smooth alpha gradient thresholds to a hard edge
    and reads as two flat blocks. White on transparent -> `mode: alpha`.
    """
    img, d, u = _canvas()
    w = int(u * 0.05)
    l, t, r, b = u * 0.14, u * 0.14, u * 0.86, u * 0.86
    d.rectangle([l, t, r, b], outline=(255, 255, 255, 255), width=w)
    # Coarse ordered dither: column density falls off left to right, drawn as
    # whole cells so it survives the 40px downscale as texture rather than grey.
    cell = int(u * 0.06)
    x0, y0 = l + w, t + w
    cols = int((r - w - x0) // cell)
    rows = int((b - w - y0) // cell)
    for cx in range(cols):
        # 4 -> 0 lit rows per 4-row group, left (solid) to right (empty)
        keep = 4 - round(4 * cx / max(1, cols - 1))
        for cy in range(rows):
            if (cy % 4) < keep:
                d.rectangle([x0 + cx * cell, y0 + cy * cell,
                             x0 + (cx + 1) * cell - 1, y0 + (cy + 1) * cell - 1],
                            fill=(255, 255, 255, 255))
    img.resize((96, 96), Image.LANCZOS).save(path)


def _draw_clonestamp(path: Path) -> None:
    """Clone stamp: the tool's own silhouette -- a stamp with a handle.

    ⚠️ Drawn rather than sourced: Fluent has no stamp at all (`Stamp`,
    `Clone`, `Stamp Checkmark` all 404), and the tempting substitutes are both
    wrong -- `Copy` reads as copy-to-clipboard and `Fingerprint` as identity.
    White on transparent -> `mode: alpha`.
    """
    img, d, u = _canvas()
    white = (255, 255, 255, 255)
    # base plate
    d.rounded_rectangle([u * 0.14, u * 0.76, u * 0.86, u * 0.88],
                        radius=int(u * 0.03), fill=white)
    # pad
    d.rounded_rectangle([u * 0.22, u * 0.56, u * 0.78, u * 0.72],
                        radius=int(u * 0.04), fill=white)
    # neck
    d.polygon([(u * 0.38, u * 0.56), (u * 0.62, u * 0.56),
               (u * 0.57, u * 0.30), (u * 0.43, u * 0.30)], fill=white)
    # handle knob
    d.rounded_rectangle([u * 0.36, u * 0.14, u * 0.64, u * 0.30],
                        radius=int(u * 0.06), fill=white)
    img.resize((96, 96), Image.LANCZOS).save(path)


# ⚠️ The four brush-width keys all pointed at Fluent's `Line Horizontal 1` and
# rendered as the SAME plain bar -- `[` / `]` / Ctrl+`[` / Ctrl+`]` were
# indistinguishable from each other AND from `O` (line/curve), five cells with
# one picture. Nothing in the generator can see that: every one of them drew a
# perfectly good glyph. Only the preview showed it.
#
# So the step is drawn: a bar whose THICKNESS states the direction, over the
# signed step itself. Both halves are needed -- thickness alone does not say
# which way, and a number alone does not say what it is the width OF.
_BW_CELL = (40, 36)          # the binding's region; see the kill glyphs in the
_BW_SS = 8                   # putty overlay for why this is in cell pixels
_BW_FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def _brush_width(path: Path, *, wider: bool, step: int) -> None:
    cw, ch = _BW_CELL
    w, h = cw * _BW_SS, ch * _BW_SS
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    thick = (9 if wider else 3) * _BW_SS
    d.rectangle([6 * _BW_SS, 4 * _BW_SS - thick / 2,
                 34 * _BW_SS, 4 * _BW_SS + thick / 2], fill=white)
    font = ImageFont.truetype(_BW_FONT, int(21 * _BW_SS))
    d.text((w / 2, 24 * _BW_SS), f"{'+' if wider else '-'}{step}",
           fill=white, font=font, anchor="mm")
    img.resize((cw * 4, ch * 4), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)

    # ⚠️ Guarded like every hand-editable asset here: a committed PNG wins.
    for name, wider, step in (("brushdec1", False, 1), ("brushinc1", True, 1),
                              ("brushdec5", False, 5), ("brushinc5", True, 5)):
        p = out / f"{name}.png"
        if p.exists():
            print(f"  {name}.png  <- committed asset (left as-is)")
        else:
            _brush_width(p, wider=wider, step=step)
            print(f"  {name}.png  <- custom (drawn: bar + {'+' if wider else '-'}{step})")
        n += 1

    # ⚠️ Guarded so a re-run never clobbers a hand-tuned glyph, like every other
    # drawn asset in this tree: once committed, the PNG is the source of truth.
    for name, fn, what in (("gradient", _draw_gradient, "dithered ramp in a frame"),
                           ("clonestamp", _draw_clonestamp, "stamp with a handle")):
        p = out / f"{name}.png"
        if p.exists():
            print(f"  {name}.png  <- committed asset (left as-is)")
        else:
            fn(p)
            print(f"  {name}.png  <- custom (drawn: {what})")
        n += 1

    program_marks.ensure(out / "paintdotnet.png", "PN")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
