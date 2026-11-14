#!/usr/bin/env python3
"""Shared drawings for the emulator and console-port overlay sets.

An emulator maps a game pad to the keyboard. The keys show the pad control they
press, drawn 1-bit at the size the keycap shows it, so the generator copies each
PNG 1:1 (the binding's `region` equals the PNG size). The face buttons with a
letter and the START / SELECT pills come from `retroarch/fetch_icons.py`
(`ring()`, `pill()`); this file adds the controls those two cannot draw:

    stick()     one direction of an analog stick or of the N64 C buttons
    dpad()      one direction of the D-pad
    shape()     a PlayStation face button (triangle, circle, cross, square)
    numbered()  an action icon with a slot number beside it
    logo_mark() an ESC mark cut from the program's own icon
    wordmark()  an ESC mark set in a font, for a program whose art is not usable

    from polyhost.res.overlay_sources import pad_keys
"""
from __future__ import annotations

import io
from pathlib import Path

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc
from polyhost.res.overlay_sources.retroarch import fetch_icons as ra

N = ra.RING_PX                       # 32: every pad control is drawn on this square
DIRECTIONS = ("up", "right", "down", "left")
SHAPES = ("triangle", "circle", "cross", "square")


def _ring():
    """The 2 px circle `ra.ring()` draws, as a mask."""
    import numpy as np
    yy, xx = np.mgrid[0:N, 0:N]
    c = (N - 1) / 2
    d = np.hypot(yy - c, xx - c)
    return (d <= c + 0.2) & (d >= c - 2)


def _turn(mask, direction: str):
    """`mask` drawn for "up", turned to face `direction`."""
    import numpy as np
    return np.rot90(mask, -DIRECTIONS.index(direction))


def stick(direction: str, dest: Path, letter: str | None = None) -> None:
    """One direction of a stick: a ring, an arrow head at its edge pointing
    `direction`, and in the centre `letter` (L or R for the left and right stick,
    C for the C stick or C buttons) or, without a letter, a 6 px dot."""
    import numpy as np
    arrow = np.zeros((N, N), bool)
    for row in range(6):                             # tip at y 4, base 12 px wide at y 9
        arrow[4 + row, 15 - row:17 + row] = True
    m = _ring() | _turn(arrow, direction)
    if letter is None:
        yy, xx = np.mgrid[0:N, 0:N]
        m |= np.hypot(yy - 15.5, xx - 15.5) <= 3.2
    else:
        g = ra._text_mask(letter, 8)
        # 3 px away from the arrow, so the letter and the arrow do not touch.
        dy, dx = {"up": (3, 0), "down": (-3, 0), "left": (0, 3), "right": (0, -3)}[direction]
        y0, x0 = (N - g.shape[0]) // 2 + dy, (N - g.shape[1]) // 2 + dx
        m[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] |= g
    cnc._save_mask(m, dest)


def dpad(direction: str, dest: Path) -> None:
    """One direction of the D-pad: the cross as a 2 px outline with the arm that
    points `direction` filled."""
    import numpy as np
    a, b = 11, 21                                    # the arms are 10 px wide
    cross = np.zeros((N, N), bool)
    cross[1:N - 1, a:b] = True
    cross[a:b, 1:N - 1] = True
    inner = np.zeros((N, N), bool)
    inner[3:N - 3, a + 2:b - 2] = True
    inner[a + 2:b - 2, 3:N - 3] = True
    arm = np.zeros((N, N), bool)
    arm[1:a, a:b] = True
    cnc._save_mask((cross & ~inner) | _turn(arm, direction), dest)


def shape(name: str, dest: Path) -> None:
    """A PlayStation face button: the ring with the button's shape in 2 px
    lines. The four shapes are plain geometry drawn here, not Sony's artwork."""
    import numpy as np
    from PIL import Image, ImageDraw
    im = Image.new("L", (N, N), 0)
    d = ImageDraw.Draw(im)
    if name == "triangle":
        d.polygon([(15.5, 7), (24, 22), (7, 22)], outline=255, width=2)
    elif name == "circle":
        d.ellipse([8, 8, 23, 23], outline=255, width=2)
    elif name == "cross":
        d.line([(9, 9), (22, 22)], fill=255, width=2)
        d.line([(22, 9), (9, 22)], fill=255, width=2)
    elif name == "square":
        d.rectangle([9, 9, 22, 22], outline=255, width=2)
    else:
        raise ValueError(f"unknown shape {name!r}; expected one of {', '.join(SHAPES)}")
    cnc._save_mask(_ring() | (np.asarray(im) > 127), dest)


NUMBERED_SIZE = (38, 32)             # w, h of a numbered() icon
NUMBERED_ICON = 22                   # the action icon's box


def numbered(icon: Path, text: str, dest: Path) -> None:
    """`icon` (an RGBA PNG whose alpha is the shape) in the bottom-left corner
    of a NUMBERED_SIZE canvas, with `text` at 16 px in the bottom-right corner.
    Both stay below the keycap legend."""
    import numpy as np
    from PIL import Image
    w, h = NUMBERED_SIZE
    alpha = Image.open(icon).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    s = NUMBERED_ICON / max(alpha.size)
    alpha = alpha.resize((max(1, round(alpha.width * s)), max(1, round(alpha.height * s))), Image.BOX)
    a = np.asarray(alpha) > 127
    g = ra._text_mask(text, 16)
    m = np.zeros((h, w), bool)
    m[h - a.shape[0]:, :a.shape[1]] = a
    m[h - g.shape[0]:, w - g.shape[1]:] |= g
    cnc._save_mask(m, dest)


def logo_mark(dest: Path, url: str, lit: str = "alpha", cut: int = 120, box=(37, 32)) -> None:
    """An ESC mark from the program's own icon at `url` (SVG or PNG), fitted into
    `box` (w, h) and cut to 1 bit at that size. `lit` says which pixels light
    up: "alpha" every opaque pixel, "bright" the opaque pixels brighter than
    `cut` (0..255), "dark" the darker ones. Guarded: a committed mark is left
    as it is."""
    import numpy as np
    from PIL import Image
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    data = cnc._get(url)
    if url.lower().endswith(".svg"):
        import cairosvg
        data = cairosvg.svg2png(bytestring=data, output_width=512)
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    s = min(box[0] / im.width, box[1] / im.height)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.BOX)
    opaque = np.asarray(im.getchannel("A")) > 128
    luma = np.asarray(Image.alpha_composite(Image.new("RGBA", im.size, (0, 0, 0, 255)), im).convert("L"))
    if lit == "alpha":
        m = opaque
    elif lit == "bright":
        m = opaque & (luma > cut)
    elif lit == "dark":
        m = opaque & (luma < cut)
    else:
        raise ValueError(f"unknown lit {lit!r}; expected alpha, bright or dark")
    cnc._save_mask(m, dest)
    print(f"  {dest.name}  <- {url} ({lit}, {m.shape[1]} x {m.shape[0]})")


def wordmark(lines: tuple[str, ...], dest: Path, font_url: str, threshold: int = 80,
             gap: int = 2, supersample: int = 8) -> None:
    """An ESC mark of text: `lines` in the font at `font_url`, at the largest one
    size at which every line fits 70 px wide and all lines, with `gap` px between
    them, fit 38 px high, centred on the whole 72 x 40 cell. Drawn at `supersample`
    times the size and box-filtered down; a pixel is lit from grey level
    `threshold`. The same method as `fheroes2/fetch_icons.py` `program()`."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    w, h, ss = 72, 40, supersample
    path = str(cnc._font(font_url))
    for px in range(400, 40, -4):
        font = ImageFont.truetype(path, px)
        boxes = [font.getbbox(line) for line in lines]
        height = sum(b[3] - b[1] for b in boxes) + gap * ss * (len(boxes) - 1)
        if all(b[2] - b[0] <= (w - 2) * ss for b in boxes) and height <= (h - 2) * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    draw = ImageDraw.Draw(im)
    y = (h * ss - height) // 2
    for line, box in zip(lines, boxes):
        draw.text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]), line, font=font, fill=255)
        y += box[3] - box[1] + gap * ss
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > threshold, dest)
    print(f"  {dest.name}  <- {' / '.join(lines)} ({font_url.rsplit('/', 1)[1]}, {px / ss:.1f} px)")
