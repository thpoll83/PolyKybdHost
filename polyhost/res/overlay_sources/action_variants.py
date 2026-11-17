#!/usr/bin/env python3
"""Variants of one icon for keys that do a related but different action.

Maintainer's rule (2026-11-15): two keys of one app share an image only when
they do the same thing. "Next channel" and "Previous channel", "Paste" and
"Paste special", "Close tab" and "Close tab, select other side" are different
actions, so each needs its own picture. These helpers make that picture from
the icon the first key already uses, so the family still reads as one:

* ``arrowed``  -- the icon in the lower left, a solid triangle at the top right
  (``up``, ``down``, ``left``, ``right``). The geometry of the Eclipse and Zed
  ``_badge`` helpers, so these read as one family with those.
* ``tagged``   -- the icon in the upper left, a short bold word at the bottom
  right ("ALL", "BG", "PDF").
* ``combined`` -- the icon in the upper left, a second icon at the lower right
  on a cleared margin.
* ``mirrored`` -- the icon flipped left to right.
* ``flipped``  -- the icon flipped top to bottom.

Every output is WHITE on transparent at ``PX`` px, drawn at ``SS`` times and
reduced with LANCZOS, so a spec in ``mode: auto`` lights the opaque pixels. The
base may be dark art (Fluent, Material) or light art (the reclaimed drawings):
``_ink`` reads either.

The callers guard each output (``guarded``), so a hand edit survives a re-run.
To redraw one, delete its PNG first.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

PX = 96
SS = 4
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def _ink(path: Path) -> Image.Image:
    """The ink of an icon as an L mask at its own size, cropped to its box.

    Dark art on transparent: alpha times darkness. Light art on transparent:
    alpha. An opaque icon: darkness."""
    im = Image.open(path).convert("RGBA")
    arr = np.asarray(im).astype(np.float32)
    alpha = arr[..., 3]
    luma = arr[..., :3] @ np.array([0.2989, 0.5870, 0.1140], np.float32)
    if alpha.min() >= 250:
        ink = 255.0 - luma
    else:
        on = alpha > 127
        dark = on.any() and float(luma[on].mean()) < 128
        ink = alpha * (1.0 - luma / 255.0) if dark else alpha
    m = Image.fromarray(np.clip(ink, 0, 255).astype(np.uint8), "L")
    box = m.getbbox()
    return m.crop(box) if box else m


def _fit(path: Path, box: int) -> Image.Image:
    ink = _ink(path)
    k = box / max(ink.size)
    return ink.resize((max(1, round(ink.width * k)), max(1, round(ink.height * k))),
                      Image.LANCZOS)


def _canvas():
    u = PX * SS
    m = Image.new("L", (u, u), 0)
    return u, m, ImageDraw.Draw(m)


def _save(m: Image.Image, path: Path) -> None:
    a = m.resize((PX, PX), Image.LANCZOS)
    white = Image.new("L", (PX, PX), 255)
    Image.merge("RGBA", (white, white, white, a)).save(path)


def arrowed(base: Path, path: Path, direction: str) -> None:
    """``base`` in the lower-left 72 %, a solid triangle in the top-right 30 %."""
    u, m, d = _canvas()
    g = _fit(base, int(u * 0.72))
    m.paste(g, ((int(u * 0.72) - g.width) // 2, u - g.height))
    x0, y0, x1, y1 = int(u * 0.70), 0, u - 1, int(u * 0.30)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    pts = {"up": [(x0, y1), (x1, y1), (cx, y0)],
           "down": [(x0, y0), (x1, y0), (cx, y1)],
           "right": [(x0, y0), (x0, y1), (x1, cy)],
           "left": [(x1, y0), (x1, y1), (x0, cy)]}[direction]
    d.polygon(pts, fill=255)
    _save(m, path)


def tagged(base: Path, path: Path, text: str) -> None:
    """``base`` in the upper left, ``text`` in bold at the bottom right on a
    cleared margin. The font size is fixed, so every tag of a family has the
    same letter height."""
    u, m, d = _canvas()
    g = _fit(base, int(u * 0.66))
    m.paste(g, (0, 0))
    font = ImageFont.truetype(BOLD, int(u * (0.42 if len(text) <= 2 else 0.34)))
    l, t, r, b = d.textbbox((0, 0), text, font=font, anchor="rb")
    w, h = r - l, b - t
    pad = int(u * 0.05)
    d.rectangle([u - w - 2 * pad, u - h - 2 * pad, u, u], fill=0)
    d.text((u, u), text, font=font, fill=255, anchor="rb")
    _save(m, path)


def combined(base: Path, badge: Path, path: Path) -> None:
    """``base`` in the upper-left 68 %, ``badge`` in the lower-right 46 % on a
    cleared margin."""
    u, m, d = _canvas()
    g = _fit(base, int(u * 0.68))
    m.paste(g, (0, 0))
    b = _fit(badge, int(u * 0.46))
    bx, by = u - b.width, u - b.height
    pad = int(u * 0.06)
    d.rectangle([bx - pad, by - pad, u, u], fill=0)
    m.paste(b, (bx, by))
    _save(m, path)


def mirrored(base: Path, path: Path) -> None:
    """``base`` flipped left to right, centred on the canvas."""
    u, m, _ = _canvas()
    g = ImageOps.mirror(_fit(base, u))
    m.paste(g, ((u - g.width) // 2, (u - g.height) // 2))
    _save(m, path)


def flipped(base: Path, path: Path) -> None:
    """``base`` flipped top to bottom, centred on the canvas."""
    u, m, _ = _canvas()
    g = ImageOps.flip(_fit(base, u))
    m.paste(g, ((u - g.width) // 2, (u - g.height) // 2))
    _save(m, path)


def guarded(path: Path, draw, what: str) -> None:
    """Run ``draw(path)`` only when ``path`` does not exist yet."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        draw(path)
        print(f"  {path.name}  <- {what}")


def make(out: Path, table: dict) -> None:
    """Draw every entry of ``table`` into ``out``, guarded.

    ``table`` maps an output name to ``("arrow", base, direction)``,
    ``("tag", base, text)``, ``("combine", base, badge)``, ``("mirror", base)``
    or ``("flip", base)``. Names are file names in ``out``; a base may be a
    path relative to ``out``."""
    for name, spec in table.items():
        kind, base, *rest = spec
        b = out / base
        if kind == "arrow":
            guarded(out / name, lambda p, b=b, r=rest: arrowed(b, p, r[0]), f"{base} + {rest[0]} arrow")
        elif kind == "tag":
            guarded(out / name, lambda p, b=b, r=rest: tagged(b, p, r[0]), f"{base} + '{rest[0]}'")
        elif kind == "combine":
            guarded(out / name, lambda p, b=b, r=rest: combined(b, out / r[0], p), f"{base} + {rest[0]}")
        elif kind == "mirror":
            guarded(out / name, lambda p, b=b: mirrored(b, p), f"{base} mirrored")
        elif kind == "flip":
            guarded(out / name, lambda p, b=b: flipped(b, p), f"{base} flipped")
        else:
            raise ValueError(kind)
