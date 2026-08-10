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

import io
import math
import time
import urllib.error
import urllib.request
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
# The J's hook decides the whole mark, and the candidate faces span a real
# range. Measured on a 200px J (hook overhang past the stem, box width/height),
# over ten sans faces rendered as the finished mark and compared side by side:
#
#     Rubik         w/h 0.82  overhang 0.07   barely hooks -> two thick slabs
#     DejaVu Sans   w/h 0.37  overhang 0.43   straight stem -> reads as a BAR
#     Lato          w/h 0.48  overhang 0.60   <- the pick
#     FreeSans      w/h 0.62  overhang 0.67   hook curls right over -> too curvy
#
# Lato is **not** a system font, so it is fetched (OFL, from google/fonts) the
# same way brand_marks fetches its SVGs. That is only needed to *regenerate* the
# mark: `ensure_confluence` leaves a committed PNG alone, so a normal run of the
# fetch script touches no network for it. `_SANS` is the offline fallback, in
# preference order — it changes the mark, so it is a last resort, not an equal.
_HOOK_TTF = ("https://raw.githubusercontent.com/google/fonts/main/"
             "ofl/lato/Lato-Bold.ttf")
_SANS = (
    "/usr/share/fonts/opentype/tlwg/Loma-Bold.otf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
)


def _hook_font(px: int) -> ImageFont.FreeTypeFont:
    try:
        for i in range(4):                       # raw.githubusercontent 403s/resets
            try:
                data = urllib.request.urlopen(urllib.request.Request(
                    _HOOK_TTF, headers={"User-Agent": "polykybd"}), timeout=30).read()
                return ImageFont.truetype(io.BytesIO(data), px)
            except (urllib.error.URLError, OSError):
                if i == 3:
                    raise
                time.sleep(2 ** i)
    except Exception as e:                       # noqa: BLE001 - offline is not fatal
        for p in _SANS:
            if Path(p).exists():
                print(f"  ! Lato unavailable ({e}); falling back to {Path(p).name} "
                      f"- the mark WILL differ from the committed one")
                return ImageFont.truetype(p, px)
        raise RuntimeError(f"no sans face available; {_HOOK_TTF} failed and "
                           f"none of {_SANS} exist") from e
    raise AssertionError("unreachable")


def _hook(px: int, dilate: int, trim: int) -> Image.Image:
    """A J, thickened past Bold, trimmed at the top, then vertically mirrored.

    `trim` cuts rows off the **top of the J** — the free end of its stem — so
    the stem shortens and the hook keeps its full curl. It is in **final output
    pixels** (scaled by `SS` here), not rows of this drawing.

    ⚠️ The trim happens **before** `ImageOps.flip`, and that ordering is the
    whole point: after the flip the hook sits at the top, so trimming there cuts
    the hook instead of the stem — the opposite end. Do not fold this step into
    the post-flip crop.
    """
    font = _hook_font(px)
    probe = ImageDraw.Draw(Image.new("L", (px * 3, px * 3)))
    l, t, r, b = probe.textbbox((0, 0), "J", font=font)
    img = Image.new("L", (r - l + px, b - t + px), 0)
    ImageDraw.Draw(img).text((px // 2 - l, px // 2 - t), "J", font=font, fill=255)
    # No Black/Heavy weight is available, so the stroke is grown by dilation.
    for _ in range(dilate):
        img = img.filter(ImageFilter.MaxFilter(3))
    if trim:
        img = img.crop(img.getbbox())            # still J-side up
        img = img.crop((0, trim * SS, img.width, img.height))
    img = ImageOps.flip(img)
    return img.crop(img.getbbox())


def render_confluence(dest: Path, px: int = 180, dilate: int = 8,
                      gap: float = -0.22, trim: int = 3,
                      converge: int = 2, drop: int = 2) -> None:
    """Two mirrored J's, rotated 70 and 250 degrees counter-clockwise.

    `trim` cuts rows off the top of each J — the free end of its stem —
    **before** it is mirrored and rotated, so the stem shortens and the hook
    keeps its curl. It is counted in **final output pixels**, not in the glyph's
    own rows: the mark is drawn `SS`x supersampled, so a row of the drawing is
    an eighth of an output pixel and trimming three of those would be invisible.

    `converge` then nudges each hook back towards the centre in **x only**, in
    the same final-pixel unit, tightening the pair horizontally without
    disturbing the diagonal the gap runs along. `drop` lowers whichever hook
    sits **above** the centre by that many pixels, closing the pair vertically
    from one side only.

    ⚠️ `drop` is at its ceiling at 2: at 3 the two hooks touch and flood into a
    single blob, losing the two-element reading entirely. Re-check with a
    connected-component count (it must stay 2), not by eye — the merge costs
    only a pixel or so of ink, so it does not show up as a size change.

    Each hook is displaced from the centre **along its own rotation axis**, and
    `gap` is SIGNED: the sign is what chooses which side of the pair the space
    falls on. It is the equivalent of padding the glyph box on the left rather
    than the right before rotating — the rotation turns that padding into a
    displacement along the rotated x-axis, so the two paddings differ by 180
    degrees.

    ⚠️ The two signs are genuinely different images (verified by hash), even
    though each one is *individually* 180-degree symmetric. Do not assume the
    symmetry collapses them — it does not, because the 180 rotation swaps the
    two hooks as well as the two positions.
    """
    W, H = CELL_W * SS, CELL_H * SS
    img = Image.new("L", (W, H), 0)
    hook = _hook(px, dilate, trim)
    d = min(W, H) * gap
    for ang in (70, 250):
        r = hook.rotate(ang, resample=Image.BICUBIC, expand=True)
        a = math.radians(ang)
        dx, dy = d * math.cos(a), -d * math.sin(a)
        # Pull each hook back towards the centre in x only, AFTER it is placed.
        # Sign-driven rather than a fixed +/-, so it stays "inwards" for either
        # `gap` sign; it closes the pair horizontally without touching the
        # diagonal the gap runs along.
        dx -= math.copysign(converge * SS, dx) if dx else 0
        # Nudge whichever hook sits above the centre downwards. Selected by the
        # sign of its own y offset (negative = higher up the canvas), so it
        # follows the upper hook rather than being pinned to one rotation angle.
        if dy < 0:
            dy += drop * SS
        img.paste(r, (int(W / 2 + dx - r.width / 2),
                      int(H / 2 + dy - r.height / 2)), r)
    _emit(img, dest)


def ensure_confluence(dest: Path, **kw) -> None:
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    render_confluence(dest, **kw)
    print(f"  {dest.name}  <- drawn hook pair")
