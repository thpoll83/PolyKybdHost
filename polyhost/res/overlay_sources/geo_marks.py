#!/usr/bin/env python3
"""Shared source for **constructed marks**: logos rebuilt from their geometry.

Some apps have neither a shippable logo nor a shape any of the other mark
sources can express. Blackmagic's DaVinci Resolve and Atlassian's Confluence are
both like that — the real logos are proprietary, but each is built from a plain
geometric recipe (a ring of drops; a pair of rotated hooks) that can be *drawn*
rather than copied. A drawn mark owes nothing to the original artwork and still
reads as the app at 37x32 px.

Peer of the other mark sources:

    the app's own mark, monochrome + CC0 -> brand_marks
    the app is a document/page           -> doc_mark   (framed + labelled)
    a lettered suite product             -> rect_mark  (framed letters)
    the logo is a geometric construction -> geo_marks  (this file)
    anything else                        -> program_marks (drawn letter tile)

Marks are authored **1:1** at the cell region so the generator never rescales
them, and are drawn supersampled then Lanczos-downscaled — PIL's `ImageDraw`
has no antialiasing, so a curve drawn straight at 37x32 comes out ragged.

    from polyhost.res.overlay_sources import geo_marks
    geo_marks.ensure_resolve(out / "resolve.png")

`ensure_*()` is a guard: a committed file is left alone so a hand-tuned mark
survives a re-run.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# Same cell region as the framed marks (`rect_mark`), so the program icons in a
# set share a footprint.
CELL_W, CELL_H = 37, 32
SS = 8                      # supersample factor for the draw
THRESH = 110                # 1-bit cut after the downscale: no grey survives


def _emit(big: Image.Image, dest: Path) -> None:
    small = big.resize((CELL_W, CELL_H), Image.LANCZOS).point(
        lambda v: 255 if v > THRESH else 0)
    Image.merge("RGBA", (small,) * 3 + (small,)).save(dest)


# --------------------------------------------------------------------------- #
# DaVinci Resolve: a ring with three drops
# --------------------------------------------------------------------------- #
def render_resolve(dest: Path, bulb: float = 0.20, ring: float = 0.52,
                   angles: tuple[int, int, int] = (90, 210, 330)) -> None:
    """A 2px ring enclosing three teardrops spaced 120 degrees apart.

    Each drop points its **tip inwards**, and sits clear of both the ring and
    the centre — a drop that reaches either end reads as a solid blob once it is
    thresholded to 1 bit. `bulb` is the bulb radius and `ring` the drop-centre
    orbit, both as a fraction of the ring radius. `angles` places the drops
    (maths convention, but y grows downward on the canvas): the default puts
    one drop at the top and two below it.
    """
    W, H = CELL_W * SS, CELL_H * SS
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, H / 2
    R = min(W, H) / 2 - SS                       # ring radius, 1px of air
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=255, width=2 * SS)

    rb = R * bulb                                 # bulb radius
    orbit = R * ring                              # bulb centre distance
    tip = orbit - rb * 2.1                        # tip stops short of the centre
    for a_deg in angles:
        a = math.radians(a_deg)
        ux, uy = math.cos(a), -math.sin(a)        # outward unit vector
        bx, by = cx + orbit * ux, cy + orbit * uy
        tx, ty = cx + tip * ux, cy + tip * uy
        # Teardrop = bulb + the triangle spanning its tangents to the tip.
        px, py = -uy, ux                          # perpendicular
        d.ellipse([bx - rb, by - rb, bx + rb, by + rb], fill=255)
        d.polygon([(bx + rb * px, by + rb * py),
                   (bx - rb * px, by - rb * py), (tx, ty)], fill=255)
    _emit(img, dest)


def ensure_resolve(dest: Path, **kw) -> None:
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    render_resolve(dest, **kw)
    print(f"  {dest.name}  <- drawn ring + 3 drops")


# --------------------------------------------------------------------------- #
# Confluence: two rotated hooks
# --------------------------------------------------------------------------- #
# A sans face with a genuinely curved J — a face whose J is a straight stem with
# a clipped foot (DejaVu) renders as two bars, not two hooks.
_SANS = (
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/opentype/tlwg/Loma-Bold.otf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


def _hook(px: int, dilate: int) -> Image.Image:
    """A vertically-mirrored J, thickened past the Bold weight."""
    for p in _SANS:
        if Path(p).exists():
            font = ImageFont.truetype(p, px)
            break
    else:
        raise RuntimeError(f"no curved sans face found; looked in {_SANS}")
    probe = ImageDraw.Draw(Image.new("L", (px * 3, px * 3)))
    l, t, r, b = probe.textbbox((0, 0), "J", font=font)
    img = Image.new("L", (r - l + px, b - t + px), 0)
    ImageDraw.Draw(img).text((px // 2 - l, px // 2 - t), "J", font=font, fill=255)
    # No Black/Heavy weight is installed, so the stroke is grown by dilation.
    for _ in range(dilate):
        img = img.filter(ImageFilter.MaxFilter(3))
    img = ImageOps.flip(img)
    return img.crop(img.getbbox())


def render_confluence(dest: Path, px: int = 180, dilate: int = 8,
                      gap: float = 0.22) -> None:
    """Two mirrored J's, rotated 70 and 250 degrees counter-clockwise.

    Each hook is pushed out from the centre **along its own rotation axis**, so
    the space between them runs across the other diagonal. That offset axis is
    the only control over where the space lands: the pair is 180-degree
    symmetric by construction, so mirroring the glyph horizontally (or flipping
    the sign of the offset) merely swaps which hook is which and returns a
    pixel-identical image.
    """
    W, H = CELL_W * SS, CELL_H * SS
    img = Image.new("L", (W, H), 0)
    hook = _hook(px, dilate)
    d = min(W, H) * gap
    for ang in (70, 250):
        r = hook.rotate(ang, resample=Image.BICUBIC, expand=True)
        a = math.radians(ang)
        img.paste(r, (int(W / 2 + d * math.cos(a) - r.width / 2),
                      int(H / 2 - d * math.sin(a) - r.height / 2)), r)
    _emit(img, dest)


def ensure_confluence(dest: Path, **kw) -> None:
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    render_confluence(dest, **kw)
    print(f"  {dest.name}  <- drawn hook pair")
