#!/usr/bin/env python3
"""Shared drawn glyphs for the 3D and VFX sets (3ds Max, Cinema 4D, Nuke,
Substance 3D Painter).

Neither Fluent nor Material has a glyph for "front view", "top view" or "lock
the X axis", and these apps bind them to single keys. They are drawn here once,
so every set that binds the same view or axis shows the same pixels and the
overlay icon library stores the glyph once.

Also here: three composites built from an icon that already exists in an
``icons/`` folder:

* ``slashed``    -- the icon with a diagonal stroke across it ("hide X").
* ``with_arrow`` -- the icon with a heavy arrow under it ("next / previous X").
* ``with_badge`` -- the icon reduced to the upper left, a second icon in the
  lower right ("tool + particles", "clone + absolute source").

Every glyph is BLACK on transparent at ``PX`` px, the same convention as
Blender's drawn icons, so a spec in ``mode: luma`` renders it like a Material
icon. Draws are supersampled ``SS`` times and reduced with LANCZOS.

The callers guard each output (a committed PNG is left as it is), so a hand
edit survives a re-run. To redraw one, delete its PNG first.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PX = 96
SS = 4
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def _canvas() -> tuple[int, Image.Image, ImageDraw.ImageDraw]:
    u = PX * SS
    m = Image.new("L", (u, u), 0)
    return u, m, ImageDraw.Draw(m)


def _save_mask(m: Image.Image, path: Path) -> None:
    """Write a coverage mask (255 = ink) as black on transparent, PX x PX."""
    a = np.asarray(m.resize((PX, PX), Image.LANCZOS)).astype(np.uint8)
    rgba = np.zeros((PX, PX, 4), np.uint8)
    rgba[..., 3] = a
    Image.fromarray(rgba, "RGBA").save(path)


def _ink(path: Path) -> Image.Image:
    """The ink of an icon PNG as an L mask, at PX x PX: alpha where the icon is
    dark on transparent, so Material, Fluent and the drawn glyphs all work."""
    im = Image.open(path).convert("RGBA").resize((PX, PX), Image.LANCZOS)
    rgb = np.asarray(im)[..., :3].astype(np.float32).mean(axis=2)
    alpha = np.asarray(im)[..., 3].astype(np.float32)
    ink = alpha * (1.0 - rgb / 255.0)
    return Image.fromarray(np.clip(ink, 0, 255).astype(np.uint8), "L")


def _fit_ink(path: Path, box: int) -> Image.Image:
    """The ink of ``path`` cropped to its bounding box and scaled to fit a
    ``box`` square, keeping its aspect ratio. Icon sets pad their glyphs, and
    a composite of padded glyphs comes out too small."""
    ink = _ink(path)
    ink = ink.crop(ink.getbbox() or (0, 0, PX, PX))
    k = box / max(ink.size)
    return ink.resize((max(1, round(ink.width * k)), max(1, round(ink.height * k))),
                      Image.LANCZOS)


# ------------------------------------------------------------------ view cubes
def _cube_points(u: int, mirror: bool):
    """Corners of a cube in oblique projection: the front square at the lower
    left, the back square shifted up and to the right (left when mirrored)."""
    s, k = 0.52 * u, 0.22 * u
    x0, y0 = 0.10 * u, 0.36 * u
    front = [(x0, y0), (x0 + s, y0), (x0 + s, y0 + s), (x0, y0 + s)]
    back = [(x + k, y - k) for x, y in front]
    if mirror:
        front = [(u - x, y) for x, y in front]
        back = [(u - x, y) for x, y in back]
    return front, back


def view_cube(path: Path, face: str) -> None:
    """A wire cube with one face filled: ``front``, ``top``, ``right``,
    ``left``, or ``none`` for the plain orthographic cube."""
    u, m, d = _canvas()
    front, back = _cube_points(u, mirror=(face == "left"))
    w = int(u * 0.045)
    if face == "front":
        d.polygon(front, fill=255)
    elif face == "top":
        d.polygon([front[0], front[1], back[1], back[0]], fill=255)
    elif face in ("right", "left"):
        d.polygon([front[1], back[1], back[2], front[2]], fill=255)
    for a, b in zip(front, front[1:] + front[:1]):
        d.line([a, b], fill=255, width=w)
    for a, b in zip(back, back[1:] + back[:1]):
        d.line([a, b], fill=255, width=w)
    for a, b in zip(front, back):
        d.line([a, b], fill=255, width=w)
    _save_mask(m, path)


# ------------------------------------------------------------------ axis letters
def axis_letter(path: Path, letters: str) -> None:
    """The axis name in bold over a short arrow, e.g. ``X`` or ``XY``."""
    u, m, d = _canvas()
    f = ImageFont.truetype(BOLD, int(u * (0.62 if len(letters) == 1 else 0.48)))
    d.text((u * 0.50, u * 0.40), letters, fill=255, font=f, anchor="mm")
    y, t, h = int(u * 0.84), int(u * 0.035), int(u * 0.10)
    x0, x1 = int(u * 0.16), int(u * 0.86)
    d.rectangle([x0, y - t, x1 - h, y + t], fill=255)
    d.polygon([(x1, y), (x1 - h, y - h), (x1 - h, y + h)], fill=255)
    _save_mask(m, path)


# ------------------------------------------------------------------ composites
def slashed(base: Path, path: Path) -> None:
    """``base`` with a diagonal stroke from top left to bottom right, cleared on
    both sides so the stroke reads against the icon."""
    u, m, d = _canvas()
    icon = _fit_ink(base, int(u * 0.86))
    m.paste(icon, ((u - icon.width) // 2, (u - icon.height) // 2))
    a, b = (0.10 * u, 0.10 * u), (0.90 * u, 0.90 * u)
    d.line([a, b], fill=0, width=int(u * 0.17))
    d.line([a, b], fill=255, width=int(u * 0.07))
    _save_mask(m, path)


def with_arrow(base: Path, path: Path, forward: bool) -> None:
    """``base`` reduced to the upper part, a heavy arrow under it pointing right
    (``forward``) or left."""
    u, m, d = _canvas()
    icon = _fit_ink(base, int(u * 0.62))
    m.paste(icon, ((u - icon.width) // 2, int(u * 0.04)))
    y, t, h = int(u * 0.86), int(u * 0.05), int(u * 0.13)
    x0, x1 = int(u * 0.14), int(u * 0.86)
    if forward:
        d.rectangle([x0, y - t, x1 - h, y + t], fill=255)
        d.polygon([(x1, y), (x1 - h, y - h), (x1 - h, y + h)], fill=255)
    else:
        d.rectangle([x0 + h, y - t, x1, y + t], fill=255)
        d.polygon([(x0, y), (x0 + h, y - h), (x0 + h, y + h)], fill=255)
    _save_mask(m, path)


def with_badge(base: Path, badge: Path, path: Path) -> None:
    """``base`` fitted into 68 % of the square at the upper left, ``badge`` into
    44 % at the lower right on a cleared margin, so the two read as one tool
    with an option."""
    u, m, d = _canvas()
    icon = _fit_ink(base, int(u * 0.68))
    m.paste(icon, (0, 0))
    bs = int(u * 0.44)
    b = _fit_ink(badge, bs)
    bx, by = u - b.width, u - b.height
    pad = int(u * 0.06)
    d.rectangle([bx - pad, by - pad, u, u], fill=0)
    m.paste(b, (bx, by))
    _save_mask(m, path)


# ------------------------------------------------------------------ ESC marks
def trace_mark(icon: Image.Image, path: Path, px: int = 32, luma: int = 128,
               lit: str = "dark") -> None:
    """An app icon as a ``px`` x ``px`` 1-bit ESC mark, WHITE on transparent
    (the spec renders it with ``program_icon_mode: alpha``).

    The icon is composited over white, contain-fitted into the square with
    LANCZOS and cut at ``luma``: ``lit="dark"`` lights the pixels at ``luma`` or
    darker, ``lit="light"`` the lighter ones that are also opaque. Drawn at the
    keycap size, so the generator places it 1:1.
    """
    icon = icon.convert("RGBA")
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    src = white.convert("L")
    k = px / max(src.size)
    size = (max(1, round(src.width * k)), max(1, round(src.height * k)))
    fitted = src.resize(size, Image.LANCZOS)
    alpha = icon.split()[3].resize(size, Image.LANCZOS)
    sq = Image.new("L", (px, px), 255)
    sq_a = Image.new("L", (px, px), 0)
    off = ((px - size[0]) // 2, (px - size[1]) // 2)
    sq.paste(fitted, off)
    sq_a.paste(alpha, off)
    v, al = np.asarray(sq), np.asarray(sq_a)
    on = (v <= luma) if lit == "dark" else ((v > luma) & (al > 128))
    a = (on * 255).astype(np.uint8)
    Image.fromarray(np.dstack([a, a, a, a]), "RGBA").save(path)


def svg_icon(url: str, px: int = 256) -> Image.Image:
    """Fetch an SVG and render it at ``px`` x ``px``."""
    import io
    import urllib.request
    import cairosvg
    req = urllib.request.Request(url, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        svg = r.read()
    png = cairosvg.svg2png(bytestring=svg, output_width=px, output_height=px)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def guarded(path: Path, draw, what: str) -> None:
    """Run ``draw(path)`` only when ``path`` does not exist yet."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        draw(path)
        print(f"  {path.name}  <- {what}")
