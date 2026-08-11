#!/usr/bin/env python3
"""Custom-drawn glyphs for the **non-linear video editor** overlays.

The signature timeline operations of an NLE — blade, mark in/out, overwrite,
append, ripple delete, trim, snapping — have no counterpart in Fluent or
Material (both are UI/productivity sets), and the nearest generic glyph actively
misleads: a scissors reads as clipboard-*cut*, a trash can as delete-*file*, a
download arrow as *export*. So these eight are drawn here, in one consistent
weight, and shared by the DaVinci Resolve and Premiere Pro sets.

All are **white on transparent** at 96x96 -> render with `mode: alpha`.

Drawn at 4x and LANCZOS-downscaled; strokes are >=6% of the unit so they survive
the 1-bit threshold at the ~40x34 icon region of a 72x40 keycap.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

PX = 96
SS = 4
WHITE = (255, 255, 255, 255)


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    u = PX * SS
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), u


def _save(img: Image.Image, path: Path) -> None:
    img.resize((PX, PX), Image.LANCZOS).save(path)


def _block(d, x0, y0, x1, y1, u, fill=True):
    r = int(u * 0.035)
    if fill:
        d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=WHITE)
    else:
        d.rounded_rectangle([x0, y0, x1, y1], radius=r, outline=WHITE, width=int(u * 0.055))


def blade(path: Path) -> None:
    """A clip split in two by the playhead — the razor/blade op."""
    img, d, u = _canvas()
    top, bot = int(u * 0.34), int(u * 0.70)
    _block(d, int(u * 0.06), top, int(u * 0.44), bot, u, fill=False)
    _block(d, int(u * 0.56), top, int(u * 0.94), bot, u, fill=False)
    # playhead: stem through the gap + a head on top
    cx, w = u // 2, int(u * 0.030)
    d.rectangle([cx - w, int(u * 0.20), cx + w, int(u * 0.84)], fill=WHITE)
    h = int(u * 0.075)
    d.polygon([(cx - h, int(u * 0.10)), (cx + h, int(u * 0.10)), (cx, int(u * 0.24))], fill=WHITE)
    _save(img, path)


def _mark(path: Path, incoming: bool) -> None:
    img, d, u = _canvas()
    top, bot = int(u * 0.28), int(u * 0.76)
    w = int(u * 0.060)
    if incoming:
        bx0, bx1, ex = int(u * 0.40), int(u * 0.92), int(u * 0.20)
        arm = int(u * 0.13)
    else:
        bx0, bx1, ex = int(u * 0.08), int(u * 0.60), int(u * 0.80)
        arm = -int(u * 0.13)
    _block(d, bx0, top, bx1, bot, u, fill=True)
    # the [ or ] bracket marking the point
    d.rectangle([ex - w // 2, top - int(u * 0.06), ex + w // 2, bot + int(u * 0.06)], fill=WHITE)
    for y in (top - int(u * 0.06), bot + int(u * 0.06) - w):
        x0, x1 = sorted((ex, ex + arm))
        d.rectangle([x0, y, x1, y + w], fill=WHITE)
    _save(img, path)


def mark_in(path: Path) -> None:
    """`[` bracket against the head of a clip."""
    _mark(path, incoming=True)


def mark_out(path: Path) -> None:
    """`]` bracket against the tail of a clip."""
    _mark(path, incoming=False)


def overwrite(path: Path) -> None:
    """Arrow dropping ONTO a track — replaces what is under it."""
    img, d, u = _canvas()
    cx = u // 2
    w = int(u * 0.055)
    d.rectangle([cx - w, int(u * 0.10), cx + w, int(u * 0.46)], fill=WHITE)
    h = int(u * 0.13)
    d.polygon([(cx - h, int(u * 0.42)), (cx + h, int(u * 0.42)), (cx, int(u * 0.60))], fill=WHITE)
    _block(d, int(u * 0.08), int(u * 0.70), int(u * 0.92), int(u * 0.92), u, fill=True)
    _save(img, path)


def append(path: Path) -> None:
    """A new block added at the END of the track."""
    img, d, u = _canvas()
    top, bot = int(u * 0.34), int(u * 0.70)
    _block(d, int(u * 0.04), top, int(u * 0.40), bot, u, fill=True)
    _block(d, int(u * 0.44), top, int(u * 0.62), bot, u, fill=True)
    # dashed outline slot at the tail + a plus
    _block(d, int(u * 0.68), top, int(u * 0.96), bot, u, fill=False)
    cx, cy, s, w = int(u * 0.82), (top + bot) // 2, int(u * 0.075), int(u * 0.035)
    d.rectangle([cx - s, cy - w, cx + s, cy + w], fill=WHITE)
    d.rectangle([cx - w, cy - s, cx + w, cy + s], fill=WHITE)
    _save(img, path)


def ripple_delete(path: Path) -> None:
    """A block removed and the rest pulled LEFT to close the gap."""
    img, d, u = _canvas()
    top, bot = int(u * 0.32), int(u * 0.68)
    _block(d, int(u * 0.04), top, int(u * 0.34), bot, u, fill=True)
    # the removed block: outline + X
    x0, x1 = int(u * 0.40), int(u * 0.66)
    _block(d, x0, top, x1, bot, u, fill=False)
    m = int(u * 0.045)
    d.line([(x0 + m, top + m), (x1 - m, bot - m)], fill=WHITE, width=int(u * 0.045))
    d.line([(x1 - m, top + m), (x0 + m, bot - m)], fill=WHITE, width=int(u * 0.045))
    # left-pointing arrow: the ripple
    ay = (top + bot) // 2
    d.rectangle([int(u * 0.78), ay - int(u * 0.025), int(u * 0.96), ay + int(u * 0.025)], fill=WHITE)
    h = int(u * 0.085)
    d.polygon([(int(u * 0.72), ay), (int(u * 0.84), ay - h), (int(u * 0.84), ay + h)], fill=WHITE)
    _save(img, path)


def trim(path: Path) -> None:
    """Two edit-point handles facing each other — trim mode."""
    img, d, u = _canvas()
    top, bot = int(u * 0.26), int(u * 0.78)
    w = int(u * 0.065)
    for x, arm in ((int(u * 0.34), -int(u * 0.15)), (int(u * 0.66), int(u * 0.15))):
        d.rectangle([x - w // 2, top, x + w // 2, bot], fill=WHITE)
        for y in (top, bot - w):
            x0, x1 = sorted((x, x + arm))
            d.rectangle([x0, y, x1, y + w], fill=WHITE)
    cy = (top + bot) // 2
    d.rectangle([int(u * 0.44), cy - int(u * 0.03), int(u * 0.56), cy + int(u * 0.03)], fill=WHITE)
    _save(img, path)


def snap(path: Path) -> None:
    """A horseshoe magnet — snapping on/off (neither Fluent nor Material has one).

    Built as an annulus (filled outer half-disc + legs, then the inner half-disc
    and the gap between the legs erased) rather than a stroked arc: a stroke wide
    enough to survive the 1-bit downscale closes the opening and the glyph reads
    as a solid blob instead of a magnet.
    """
    img, d, u = _canvas()
    ox0, oy0, ox1, oy1 = int(u * 0.12), int(u * 0.14), int(u * 0.88), int(u * 0.90)
    band = int(u * 0.19)
    ix0, iy0, ix1, iy1 = ox0 + band, oy0 + band, ox1 - band, oy1 - band
    cy, foot = (oy0 + oy1) // 2, int(u * 0.84)

    d.pieslice([ox0, oy0, ox1, oy1], 180, 360, fill=WHITE)
    d.rectangle([ox0, cy, ox1, foot], fill=WHITE)
    d.pieslice([ix0, iy0, ix1, iy1], 180, 360, fill=(0, 0, 0, 0))
    d.rectangle([ix0, cy, ix1, foot + 1], fill=(0, 0, 0, 0))
    # notch the pole tips so the two legs read as separate poles
    for x0 in (ox0, ix1):
        d.rectangle([x0, foot - int(u * 0.07), x0 + band, foot - int(u * 0.04)],
                    fill=(0, 0, 0, 0))
    _save(img, path)


def _arrow_h(d, u, x0, x1, y, both: bool) -> None:
    """Horizontal arrow from x0->x1 (double-headed when `both`)."""
    t, h = int(u * 0.022), int(u * 0.060)
    lo, hi = min(x0, x1), max(x0, x1)
    d.rectangle([lo, y - t, hi, y + t], fill=WHITE)
    d.polygon([(hi + h, y), (hi - h, y - h), (hi - h, y + h)], fill=WHITE)
    if both:
        d.polygon([(lo - h, y), (lo + h, y - h), (lo + h, y + h)], fill=WHITE)


def ripple_edit(path: Path) -> None:
    """Trim one clip's edge; everything downstream SHIFTS to follow."""
    img, d, u = _canvas()
    top, bot = int(u * 0.22), int(u * 0.58)
    _block(d, int(u * 0.06), top, int(u * 0.46), bot, u, fill=True)
    _block(d, int(u * 0.52), top, int(u * 0.94), bot, u, fill=False)
    # the edited edge
    d.rectangle([int(u * 0.47), top - int(u * 0.05), int(u * 0.51), bot + int(u * 0.05)], fill=WHITE)
    # the downstream shift
    _arrow_h(d, u, int(u * 0.56), int(u * 0.86), int(u * 0.80), both=False)
    _save(img, path)


def roll_edit(path: Path) -> None:
    """Move the edge BETWEEN two clips; total duration is unchanged.

    Both blocks are OUTLINED, not filled: two filled blocks separated by a 6%
    gap merge into a single bar once the 1-bit downscale is applied, and the
    glyph stops reading as "two clips sharing an edge".
    """
    img, d, u = _canvas()
    top, bot = int(u * 0.22), int(u * 0.58)
    _block(d, int(u * 0.04), top, int(u * 0.46), bot, u, fill=False)
    _block(d, int(u * 0.54), top, int(u * 0.96), bot, u, fill=False)
    d.rectangle([int(u * 0.46), top - int(u * 0.09), int(u * 0.54), bot + int(u * 0.09)], fill=WHITE)
    _arrow_h(d, u, int(u * 0.32), int(u * 0.68), int(u * 0.82), both=True)
    _save(img, path)


def track_select(path: Path) -> None:
    """Everything on the track from here RIGHTWARD is selected."""
    img, d, u = _canvas()
    top, bot = int(u * 0.30), int(u * 0.68)
    _block(d, int(u * 0.04), top, int(u * 0.26), bot, u, fill=False)
    _block(d, int(u * 0.40), top, int(u * 0.64), bot, u, fill=True)
    _block(d, int(u * 0.70), top, int(u * 0.96), bot, u, fill=True)
    _arrow_h(d, u, int(u * 0.40), int(u * 0.86), int(u * 0.16), both=False)
    _save(img, path)


def slip(path: Path) -> None:
    """Shift the clip's CONTENT inside fixed in/out points."""
    img, d, u = _canvas()
    top, bot = int(u * 0.28), int(u * 0.72)
    _block(d, int(u * 0.18), top, int(u * 0.82), bot, u, fill=False)
    # fixed edges
    for x in (int(u * 0.10), int(u * 0.90)):
        d.rectangle([x - int(u * 0.025), top - int(u * 0.08), x + int(u * 0.025),
                     bot + int(u * 0.08)], fill=WHITE)
    # content slides inside
    _arrow_h(d, u, int(u * 0.32), int(u * 0.68), (top + bot) // 2, both=True)
    _save(img, path)


def slide(path: Path) -> None:
    """Move the whole clip along the track; the neighbours absorb it."""
    img, d, u = _canvas()
    top, bot = int(u * 0.22), int(u * 0.60)
    _block(d, int(u * 0.04), top, int(u * 0.28), bot, u, fill=False)
    _block(d, int(u * 0.34), top, int(u * 0.66), bot, u, fill=True)
    _block(d, int(u * 0.72), top, int(u * 0.96), bot, u, fill=False)
    _arrow_h(d, u, int(u * 0.34), int(u * 0.66), int(u * 0.82), both=True)
    _save(img, path)


ALL = {
    "blade": blade,
    "markin": mark_in,
    "markout": mark_out,
    "overwrite": overwrite,
    "append": append,
    "rippledelete": ripple_delete,
    "trim": trim,
    "snap": snap,
    "rippleedit": ripple_edit,
    "rolledit": roll_edit,
    "slip": slip,
    "slide": slide,
    "trackselect": track_select,
}


def draw_all(out_dir: Path, names: list[str] | None = None) -> int:
    """Draw the named glyphs (default: all). Never clobbers a committed file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    picked = names or list(ALL)
    for n in picked:
        p = out_dir / f"{n}.png"
        if p.exists():
            print(f"  {n}.png  <- committed asset (left as-is)")
            continue
        ALL[n](p)
        print(f"  {n}.png  <- custom (drawn: nle_glyphs.{n})")
    return len(picked)
