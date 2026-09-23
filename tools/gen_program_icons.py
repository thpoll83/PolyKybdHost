#!/usr/bin/env python3
"""Generate the shipped ESC program marks in `polyhost/res/icons/program/`.

    python tools/gen_program_icons.py            # write them
    python tools/gen_program_icons.py --check    # fail if the committed files drift

⚠️ THE `--check` MODE IS THE POINT. A generated artifact has no counterpart to
`cmp` against -- the only question that catches its rot is "does its generator
still resolve its input", and nothing asks that on its own. `finder.png` is
derived from a VENDORED copy of mdi's mark under `src/` for exactly that reason:
re-fetching it from the CDN at generate time would make this script depend on a
pin that has already dropped brands once (see app_icons.CDN_VERSION).

Constraints every mark here is drawn under, all from polyhost/services/svg_raster:
  * `<path d=...>` only -- no strokes, no <rect>/<circle>, NO TRANSFORMS, no
    groups, filled with the NONZERO winding rule. A hole is a sub-path wound the
    opposite way to the shape around it.
  * ⚠️ A zero-radius arc degrades to a LINE (SVG 1.1 F.6.2; `_arc_to_cubics`
    returns [("L", x1, y1)] when rx == 0, ry == 0, or the endpoints coincide),
    so an arc back to the point you are already on is a NO-OP segment: the
    sub-path never traces the outline and the winding fills the shape solid.
    An arc also takes SEVEN parameters (rx ry rot large-arc sweep x y).
  * ⚠️ Aspect ratio decides rendered SIZE: `render_overlay` fits the LONGEST
    side to the 38 px box, so a portrait icon comes out narrow.
  * ⚠️ Stroke widths are viewBox units and the scale is 38/24 = 1.583, so
    t=1.4 draws 2.2 px and t=2.0 draws 3.2 px. 2.0 reads heavy on the panel.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.dirname(HERE)
sys.path.insert(0, HOME)

import numpy as np                                                  # noqa: E402
from PIL import Image, ImageFilter                                  # noqa: E402

from polyhost.services import svg_raster                            # noqa: E402
from polyhost.services.app_icons import (PANEL_H, PANEL_W,          # noqa: E402
                                         PROGRAM_ICON_BOX,
                                         PROGRAM_ICON_DIR, SUPERSAMPLE)

KAPPA = 0.5522847498            # circle-to-cubic constant
STROKE = 1.4                    # 2.2 px at the shipping 38 px box

# Bayer 4x4, normalised 0..1. Ordered rather than error-diffused ON PURPOSE: a
# Floyd-Steinberg field has no repeating cell, so two petals at nearby levels
# read as the same noise and the distinction you paid for is lost.
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                  [3, 11, 1, 9], [15, 7, 13, 5]], dtype=float) / 16.0


# --------------------------------------------------------------------------
# path helpers
# --------------------------------------------------------------------------
def rrect(x0, y0, x1, y1, r, cw=True):
    """Rounded-rectangle sub-path. `cw` picks the winding direction, which is
    what makes an inner copy cut a hole instead of filling one."""
    if cw:
        seq = [f"M{x0 + r} {y0}", f"L{x1 - r} {y0}", f"A{r} {r} 0 0 1 {x1} {y0 + r}",
               f"L{x1} {y1 - r}", f"A{r} {r} 0 0 1 {x1 - r} {y1}",
               f"L{x0 + r} {y1}", f"A{r} {r} 0 0 1 {x0} {y1 - r}",
               f"L{x0} {y0 + r}", f"A{r} {r} 0 0 1 {x0 + r} {y0}", "Z"]
    else:
        seq = [f"M{x0 + r} {y0}", f"A{r} {r} 0 0 0 {x0} {y0 + r}",
               f"L{x0} {y1 - r}", f"A{r} {r} 0 0 0 {x0 + r} {y1}",
               f"L{x1 - r} {y1}", f"A{r} {r} 0 0 0 {x1} {y1 - r}",
               f"L{x1} {y0 + r}", f"A{r} {r} 0 0 0 {x1 - r} {y0}", "Z"]
    return " ".join(seq)


def frame(x0, y0, x1, y1, r, t=STROKE):
    return (rrect(x0, y0, x1, y1, r, True) + " " +
            rrect(x0 + t, y0 + t, x1 - t, y1 - t, max(0.1, r - t * 0.5), False))


def bar(x0, y0, w, h):
    return f"M{x0} {y0} h{w} v{h} h{-w} Z"


def svg_text(name: str, d: str) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<title>{name}</title><path fill="currentColor" d="{d}"/></svg>\n')


def rasterise(text: str, size: int):
    cov = svg_raster.rasterise(text, size, size)
    return None if cov is None else (cov * 255).astype("uint8")


def place(small, tw, th):
    """A `tw` x `th` boolean block flush right and vertically centred on the panel."""
    mask = np.zeros((PANEL_H, PANEL_W), dtype=bool)
    ox, oy = PANEL_W - tw, max(0, (PANEL_H - th) // 2)
    mask[oy:oy + th, ox:ox + tw] = small
    return mask


def fit(hi, box):
    """Crop `hi` to its ink and scale so the longest side is `box`."""
    rows, cols = np.flatnonzero(hi.any(1)), np.flatnonzero(hi.any(0))
    ink = Image.fromarray(
        (hi[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1] * 255).astype("uint8"))
    scale = min(box / ink.width, box / ink.height)
    tw, th = max(1, round(ink.width * scale)), max(1, round(ink.height * scale))
    return np.array(ink.resize((tw, th), Image.LANCZOS)) > 128, tw, th


# --------------------------------------------------------------------------
# terminal -- a screen ring, a chevron prompt and a cursor bar
# --------------------------------------------------------------------------
def terminal_svg() -> str:
    return svg_text("terminal", " ".join([
        frame(1.0, 3.8, 23.0, 20.2, 2.4),
        "M6.6 8.3 L11.0 12.0 L6.6 15.7 L6.6 13.9 L8.9 12.0 L6.6 10.1 Z",
        bar(12.6, 14.8, 5.4, 1.5),
    ]))


# --------------------------------------------------------------------------
# notes -- a notebook, rendered at a SMALLER box than the other marks
# --------------------------------------------------------------------------
# ⚠️ box 34, not 38, because "less wide AND less tall" is otherwise unreachable
# (see the README). A smaller box needs FATTER strokes in viewBox units to land
# on the same pixel count: at 34 the scale is 34/24 = 1.42 against 38/24 = 1.58,
# so a 1.2-unit rule falls from 1.9 px to 1.7 and antialiasing breaks it into
# dashes. These are 1.5.
NOTES_BOX = 34


def notes_mask():
    # frame(3.2, 2.5, 20.8, 21.5, r=1.9, t=1.25) leaves an INNER rect of
    # (4.45, 3.75)-(19.55, 20.25). The header band is FLUSH to that: an inset
    # band reads as a fourth ruled line that got fat, not as a header.
    text = svg_text("notes", " ".join([
        frame(3.2, 2.5, 20.8, 21.5, 1.9, t=1.25),
        bar(4.45, 3.75, 15.1, 3.1),
        bar(6.8, 9.6, 10.4, 1.5),
        bar(6.8, 13.0, 10.4, 1.5),
        bar(6.8, 16.4, 6.2, 1.5),
    ]))
    # ⚠️ Rendered through `app_icons.render_overlay` itself rather than a local
    # copy of its steps. Thresholding the supersampled alpha to a bool BEFORE
    # the downscale, instead of after, moves 89 px -- the shipped mask has to be
    # exactly what the renderer would have produced, or the preview that was
    # signed off is not the file that ships.
    from polyhost.services.app_icons import render_overlay
    with tempfile.NamedTemporaryFile("w", suffix=".svg", encoding="utf-8",
                                     delete=False) as handle:
        handle.write(text)
        path = handle.name
    try:
        return render_overlay(path, box=NOTES_BOX)
    finally:
        os.unlink(path)


# --------------------------------------------------------------------------
# photos -- a pinwheel of tilted, overlapping ellipses, one grey each
# --------------------------------------------------------------------------
# ⚠️ Levels are INTERLEAVED, not a monotonic sweep. Painted 16,14,12,... two
# neighbouring petals differ by one sixteenth and read as the same grey; this
# pairs every bright petal with a dark one.
PETAL_LEVELS = [v / 16 for v in (16, 8, 14, 6, 12, 5, 10, 3)]

# ⚠️ OVERLAP IS THE SENSITIVE PARAMETER, not the tilt. At dist 4.8 with a=6.0
# every petal crosses the hub, eight of them pile onto each other and the flower
# reads as a crumpled blob. Petals must CLEAR the centre (dist > a) so only
# their flanks meet.
PETAL = dict(a=5.2, b=2.6, dist=6.0, tilt_deg=45.0)


def ellipse_path(cx, cy, a, b, tilt):
    """An ellipse as four cubics, rotated `tilt` radians CLOCKWISE on screen.

    Baked into the coordinates because svg_raster honours no transform
    attribute -- a `transform="rotate(...)"` is parsed away and every petal
    lands on top of the first one.
    """
    c, s = math.cos(tilt), math.sin(tilt)

    def at(px, py):
        return cx + px * c - py * s, cy + px * s + py * c

    ka, kb = a * KAPPA, b * KAPPA
    nodes = [(a, 0), (a, kb), (ka, b), (0, b), (-ka, b), (-a, kb),
             (-a, 0), (-a, -kb), (-ka, -b), (0, -b), (ka, -b), (a, -kb)]
    p = [at(x, y) for x, y in nodes]
    d = "M%.2f %.2f" % p[0]
    for i in range(4):
        d += " C%.2f %.2f %.2f %.2f %.2f %.2f" % (
            p[1 + i * 3] + p[2 + i * 3] + p[(3 + i * 3) % 12])
    return d + " Z"


def photos_mask(levels=PETAL_LEVELS, box=PROGRAM_ICON_BOX, **kw):
    geom = dict(PETAL, **kw)
    n, size = len(levels), box * SUPERSAMPLE
    petals = []
    for i in range(n):
        theta = 2 * math.pi * i / n
        cx = 12 + geom["dist"] * math.cos(theta)
        cy = 12 + geom["dist"] * math.sin(theta)
        petals.append(rasterise(svg_text("petal", ellipse_path(
            cx, cy, geom["a"], geom["b"],
            theta + math.radians(geom["tilt_deg"]))), size))

    # ⚠️ Every petal is cropped and scaled by the UNION's bounding box. Fitting
    # each one to the box on its own would scale each differently and the
    # rosette would fall apart.
    union = np.zeros((size, size), dtype="uint8")
    for p in petals:
        union = np.maximum(union, p)
    rows, cols = np.flatnonzero((union > 0).any(1)), np.flatnonzero((union > 0).any(0))
    y0, y1, x0, x1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    scale = min(box / (x1 - x0), box / (y1 - y0))
    tw, th = max(1, round((x1 - x0) * scale)), max(1, round((y1 - y0) * scale))

    reps = (th // 4 + 2, tw // 4 + 2)
    field = np.tile(BAYER, reps)[:th, :tw]
    plate = np.zeros((th, tw), dtype=bool)
    for petal, level in zip(petals, levels):
        small = np.array(Image.fromarray(petal[y0:y1, x0:x1])
                         .resize((tw, th), Image.LANCZOS))
        ink = small > 128
        inner = np.array(Image.fromarray((ink * 255).astype("uint8"))
                         .filter(ImageFilter.MinFilter(3))) > 128
        # REPLACE rather than OR, so an overlapping petal OCCLUDES the one below
        # instead of merging greys with it, then a solid 1 px rim on top so the
        # petal keeps a readable edge at any fill density.
        # ⚠️ A DARK separator instead of this white rim was tried and REFUTED:
        # with petals this overlapped each new rim carves into its neighbour,
        # ink falls 620 -> 310 px and the flower comes apart into scattered
        # fragments. The merging it was meant to fix is solved by interleaving
        # the LEVELS instead -- see PETAL_LEVELS.
        plate[ink] = (field < level)[ink]
        plate[ink & ~inner] = True
    return place(plate, tw, th)


# --------------------------------------------------------------------------
# finder -- mdi's own mark, every stroke thinned
# --------------------------------------------------------------------------
# ⚠️ The mdi Finder is NOT a solid plate with the face knocked out -- it is
# already line work: a thick ring plus thick eyes and smile. Treating it as a
# plate (outline it, fill the enclosed interior) produces a solid white square.
# "Too heavy" here means stroke WIDTH, so the fix is a proportional thinning.
#
# ⚠️ Thinning runs at HIGH RESOLUTION and downsamples after. Eroding the
# finished 38 px mask takes a whole pixel off every stroke at once, which is
# about a third of an eye and the eyes vanish.
#
# 0.75 px per side is the sweet spot, measured: 0.50 -> 538 px of ink (still
# heavy), 0.75 -> 364 px (level with terminal's 340, nose and split intact),
# 1.00 -> 273 px but the nose zigzag and the vertical split have broken into
# dashes, 1.25 -> a bare frame and two dots.
FINDER_SRC = os.path.join(PROGRAM_ICON_DIR, "src", "mdi-apple-finder.svg")
FINDER_SHAVE = 0.75
OVERSAMPLE = 8                  # thin in eighths of a final pixel


def thinned_mask(svg_path, shave=FINDER_SHAVE, box=PROGRAM_ICON_BOX):
    """`svg_path` with every stroke `shave` final-pixels narrower per side."""
    with open(svg_path, encoding="utf-8") as fh:
        text = fh.read()
    hi = rasterise(text, box * OVERSAMPLE) > 128
    radius = max(0, int(round(shave * OVERSAMPLE)))
    if radius:
        hi = np.array(Image.fromarray((hi * 255).astype("uint8"))
                      .filter(ImageFilter.MinFilter(2 * radius + 1))) > 128
    small, tw, th = fit(hi, box)
    return place(small, tw, th)


# --------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="compare against the committed files instead of writing")
    args = parser.parse_args(argv)

    products = {
        "terminal.svg": terminal_svg().encode("utf-8"),
        "notes.png": _png_bytes(notes_mask()),
        "photos.png": _png_bytes(photos_mask()),
        "finder.png": _png_bytes(thinned_mask(FINDER_SRC)),
    }

    drifted = []
    for name, payload in products.items():
        path = os.path.join(PROGRAM_ICON_DIR, name)
        if args.check:
            try:
                with open(path, "rb") as fh:
                    committed = fh.read()
            except OSError as exc:
                drifted.append("%s: %s" % (name, exc))
                continue
            state = "ok" if committed == payload else "DRIFTED"
            if state != "ok":
                drifted.append(name)
            print("%-14s %s" % (name, state))
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(payload)
            print("%-14s written" % name)
    if drifted:
        print("\nRegenerate with: python tools/gen_program_icons.py")
        return 1
    return 0


def _png_bytes(mask) -> bytes:
    import io
    buffer = io.BytesIO()
    Image.fromarray((mask * 255).astype("uint8"), "L").convert("1").save(
        buffer, "PNG", optimize=True)
    return buffer.getvalue()


if __name__ == "__main__":
    raise SystemExit(main())
