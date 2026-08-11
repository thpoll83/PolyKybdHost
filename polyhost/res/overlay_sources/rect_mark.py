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

# Region the bindings place the mark in (bottom-right, `margin: 0`). 80% of the
# original 46x40 — the full-height frame crowded the keycap and left the
# firmware-drawn legend no air.
CELL_W, CELL_H = 37, 32
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


PAD = BORDER + 2


def _fits(d: ImageDraw.ImageDraw, letters: str, size: int, serif: bool,
          avail_w: int, avail_h: int):
    f = _font(size, serif)
    left, t, r, b = d.textbbox((0, 0), letters, font=f)
    return (f, left, t, r - left, b - t) if (r - left) <= avail_w and (b - t) <= avail_h else None


def shared_size(words: list[str], serif: bool = False, shade: int = 0) -> int:
    """Largest point size at which EVERY word in `words` clears the frame.

    A family should be set at one size — a per-word fit made 'Ai' tower over
    'Pr' purely because it is narrower, which reads as a different mark rather
    than a sibling.
    """
    probe = ImageDraw.Draw(Image.new("L", (CELL_W, CELL_H)))
    avail_w, avail_h = CELL_W - shade - 2 * PAD, CELL_H - shade - 2 * PAD
    for size in range(40, 8, -1):
        if all(_fits(probe, w, size, serif, avail_w, avail_h) for w in words):
            return size
    raise RuntimeError(f"no size fits all of {words} in {CELL_W}x{CELL_H}")


def render(dest: Path, letters: str, serif: bool = False, shade: int = 0,
           shade_dir: str = "br", size: int | None = None) -> tuple[int, int]:
    """Draw `letters` inside a 2px rectangle, 1:1 at the cell region.

    `serif` picks the serif face (a brand whose letter *is* a serif). `shade`
    extrudes the frame by that many px — a 1-bit stand-in for a drop shadow,
    drawn as TWO adjacent edges only (`shade_dir` "br" = right+bottom, "tl" =
    left+top) so it reads as depth rather than as a second box. `size` pins the
    point size instead of fitting it, so a family can share one.

    Returns (used_width, used_height) of the text so a caller can assert it
    actually cleared the frame.
    """
    img = Image.new("L", (CELL_W, CELL_H), 0)
    d = ImageDraw.Draw(img)
    tl = shade_dir == "tl"
    # Face rect, inset from whichever corner the shade extrudes towards.
    x0, y0 = (shade, shade) if tl else (0, 0)
    x1, y1 = (CELL_W - 1, CELL_H - 1) if tl else (CELL_W - 1 - shade, CELL_H - 1 - shade)
    for k in range(1, shade + 1):
        if tl:                                   # left + top, offset up-left
            d.line([(x0 - k, y0 - k), (x0 - k, y1 - k)], fill=255)
            d.line([(x0 - k, y0 - k), (x1 - k, y0 - k)], fill=255)
        else:                                    # right + bottom, offset down-right
            d.line([(x1 + k, y0 + k), (x1 + k, y1 + k)], fill=255)
            d.line([(x0 + k, y1 + k), (x1 + k, y1 + k)], fill=255)
    d.rectangle([x0, y0, x1, y1], outline=255, width=BORDER)

    avail_w, avail_h = x1 - x0 + 1 - 2 * PAD, y1 - y0 + 1 - 2 * PAD
    best = None
    if size is not None:
        best = _fits(d, letters, size, serif, avail_w, avail_h)
        if best is None:
            raise RuntimeError(f"{letters!r} does not fit at pinned size {size}")
    else:
        for s_ in range(40, 8, -1):
            best = _fits(d, letters, s_, serif, avail_w, avail_h)
            if best:
                break
    if best is None:
        raise RuntimeError(f"{letters!r} does not fit the {CELL_W}x{CELL_H} frame")
    f, left, t, tw, th = best
    d.text((x0 + PAD + (avail_w - tw) // 2 - left, y0 + PAD + (avail_h - th) // 2 - t),
           letters, fill=255, font=f)

    a = img.point(lambda v: 255 if v > 110 else 0)   # 1-bit: no grey survives
    Image.merge("RGBA", (a,) * 3 + (a,)).save(dest)
    return tw, th


def ensure(dest: Path, letters: str, serif: bool = False, shade: int = 0,
           shade_dir: str = "br", size: int | None = None) -> None:
    """Draw `letters` unless `dest` is already committed (never clobber a tune)."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    tw, th = render(dest, letters, serif, shade, shade_dir, size)
    print(f"  {dest.name}  <- rect mark '{letters}' ({tw}x{th}px in a {CELL_W}x{CELL_H} frame)")
