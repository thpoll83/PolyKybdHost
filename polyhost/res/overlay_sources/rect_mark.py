#!/usr/bin/env python3
"""Shared **suite-product marks**: a 2px rectangle with the product's letters
inside — `Ps`, `Ai`, `Pr`, `Ae`.

This is the house treatment for the Adobe apps. They are a *family*, and the
thing that identifies one is its two-letter code, so the mark is deliberately
plain: a uniform frame plus the letters, with nothing else competing. Adobe's
real logos are proprietary and cannot ship here; the letter pair is the app's
own naming, not its trademark styling — no rounded-square gradient, no brand
colours, no attempt to resemble the product tile.

Peer of the other mark sources:

    the app's own mark, monochrome + CC0 -> brand_marks
    the app is a document/page           -> doc_mark   (framed + labelled)
    a lettered suite product             -> rect_mark  (this file)
    anything else                        -> program_marks (drawn letter tile)

Marks are authored **1:1** at the cell region, so the generator never rescales
them and the 2px frame stays exactly 2px. Anything authored large and squashed
loses the frame to rounding — the same lesson the LibreOffice marks recorded.

    from polyhost.res.overlay_sources import rect_mark
    rect_mark.ensure(out / "premiere.png", "Pr")

`ensure()` is a guard: a committed file is left alone so a hand-tuned mark
survives a re-run.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Region the Adobe bindings place the mark in (bottom-right, `margin: 0`).
CELL_W, CELL_H = 46, 40
BORDER = 2

_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)
# Serif face, for marks whose brand letter is a serif (Notion's N).
_SERIF = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
)


def _font(size: int, serif: bool = False) -> ImageFont.FreeTypeFont:
    fam = _SERIF if serif else _FONTS
    for p in fam:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    raise RuntimeError(f"no bold face found; looked in {fam}")


def render(dest: Path, letters: str, serif: bool = False,
           shade: int = 0) -> tuple[int, int]:
    """Draw `letters` inside a 2px rectangle, 1:1 at the cell region.

    `serif` picks the serif face (a brand whose letter *is* a serif). `shade`
    extrudes the frame by that many px down-right — a 1-bit stand-in for a drop
    shadow, drawn as right+bottom edges only so it reads as depth rather than as
    a second box.

    Returns (used_width, used_height) of the text so a caller can assert it
    actually cleared the frame.
    """
    img = Image.new("L", (CELL_W, CELL_H), 0)
    d = ImageDraw.Draw(img)
    x1, y1 = CELL_W - 1 - shade, CELL_H - 1 - shade
    if shade:
        # Extruded right + bottom edges, offset down-right from the face.
        for k in range(1, shade + 1):
            d.line([(x1 + k, y1 + k), (x1 + k, 1 + k)], fill=255)
            d.line([(1 + k, y1 + k), (x1 + k, y1 + k)], fill=255)
    d.rectangle([0, 0, x1, y1], outline=255, width=BORDER)

    # Largest size whose ink clears the frame by >= 2px on every side. Measured
    # rather than guessed: the two-letter pairs differ in width ('Ai' is much
    # narrower than 'Pr'), so one hardcoded size would either clip or float.
    pad = BORDER + 2
    avail_w, avail_h = x1 + 1 - 2 * pad, y1 + 1 - 2 * pad
    best = None
    for size in range(40, 8, -1):
        f = _font(size, serif)
        l, t, r, b = d.textbbox((0, 0), letters, font=f)
        if (r - l) <= avail_w and (b - t) <= avail_h:
            best = (f, l, t, r - l, b - t)
            break
    if best is None:
        raise RuntimeError(f"{letters!r} does not fit the {CELL_W}x{CELL_H} frame")
    f, l, t, tw, th = best
    d.text((pad + (avail_w - tw) // 2 - l, pad + (avail_h - th) // 2 - t),
           letters, fill=255, font=f)

    a = img.point(lambda v: 255 if v > 110 else 0)   # 1-bit: no grey survives
    Image.merge("RGBA", (a,) * 3 + (a,)).save(dest)
    return tw, th


def ensure(dest: Path, letters: str, serif: bool = False, shade: int = 0) -> None:
    """Draw `letters` unless `dest` is already committed (never clobber a tune)."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    tw, th = render(dest, letters, serif, shade)
    print(f"  {dest.name}  <- rect mark '{letters}' ({tw}x{th}px in a {CELL_W}x{CELL_H} frame)")
