#!/usr/bin/env python3
"""Variant glyphs for the terminal program sets: one base icon, told apart.

Two keys of one app share an image only when they do the same thing
(maintainer, 2026-11-15). Where an app has two keys for related but different
actions ("Copy" and "Copy (single)", "Resize pane up" and "Resize pane left"),
the variant is the base icon with something added:

* `worded()`: the base icon over a short word ("WORD", "CPU", "1/2").
* `side_word()`: the base icon on the left, a short word or digit on the right.
* `badged()`: the base icon at the upper left, a second icon (or an arrow) at
  the lower right on a cleared margin.
* `arrowed()`: the base icon over a heavy arrow (left, right, up or down).

Every drawing is made 1-bit at the size of the binding's region (40 x 36 or
36 x 32), white on transparent with hard alpha, so `fit: contain` places it
1:1 and no rescale blurs a 1 px gap. The base icon's shape is its alpha
channel, so dark Fluent / Material renders and white drawn icons both work.

The fetch scripts of the terminal folders (tui, tui_file_managers, aicli,
aichat, putty, wezterm, windowsterminal, lazygit) call these through
`dcc_glyphs.guarded()`, so a committed PNG is left as it is.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
CUT = 110          # alpha cut after the LANCZOS reduction
WORD_PX = 12       # Liberation Sans Bold size of a word (caps 9 px)


def _mask(path: Path, box: tuple[int, int], top: float = 1.0) -> np.ndarray:
    """The ink of an icon (its alpha) cropped to its bounding box and fitted
    into ``box`` (w, h), as a bool array. ``top`` < 1 keeps only that upper
    fraction of the ink, to drop the word under a glyph-over-word icon."""
    a = Image.open(path).convert("RGBA").getchannel("A")
    bb = a.getbbox()
    if bb:
        a = a.crop(bb)
    if top < 1.0:
        a = a.crop((0, 0, a.width, round(a.height * top)))
        a = a.crop(a.getbbox())
    # A source already at keycap size (pixel art) is never enlarged: an
    # enlarged 1-bit glyph turns into blobs.
    s = min(1.0, box[0] / a.width, box[1] / a.height)
    w, h = max(1, round(a.width * s)), max(1, round(a.height * s))
    return np.asarray(a.resize((w, h), Image.LANCZOS)) > CUT


def _word(text: str, max_w: int, px: int = WORD_PX) -> np.ndarray:
    """``text`` in Liberation Sans Bold, shrunk until it fits ``max_w``."""
    while True:
        font = ImageFont.truetype(BOLD, px)
        x0, y0, x1, y1 = font.getbbox(text)
        if x1 - x0 <= max_w or px <= 7:
            break
        px -= 1
    img = Image.new("L", (x1 - x0 + 2, y1 - y0 + 2), 0)
    ImageDraw.Draw(img).text((1 - x0, 1 - y0), text, fill=255, font=font)
    m = np.asarray(img) > 110
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _arrow(direction: str, w: int, h: int, t: int = 4) -> np.ndarray:
    """A heavy arrow filling (w, h), pointing ``direction``."""
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    if direction in ("left", "right"):
        head = min(h // 2, w // 2)
        y = h // 2
        if direction == "right":
            d.rectangle([0, y - t // 2, w - head, y - t // 2 + t - 1], fill=255)
            d.polygon([(w - 1, y), (w - 1 - head, y - head), (w - 1 - head, y + head)], fill=255)
        else:
            d.rectangle([head, y - t // 2, w - 1, y - t // 2 + t - 1], fill=255)
            d.polygon([(0, y), (head, y - head), (head, y + head)], fill=255)
    else:
        head = min(w // 2, h // 2)
        x = w // 2
        if direction == "down":
            d.rectangle([x - t // 2, 0, x - t // 2 + t - 1, h - head], fill=255)
            d.polygon([(x, h - 1), (x - head, h - 1 - head), (x + head, h - 1 - head)], fill=255)
        else:
            d.rectangle([x - t // 2, head, x - t // 2 + t - 1, h - 1], fill=255)
            d.polygon([(x, 0), (x - head, head), (x + head, head)], fill=255)
    return np.asarray(img) > 127


def _paste(canvas: np.ndarray, m: np.ndarray, x: int, y: int) -> None:
    canvas[y:y + m.shape[0], x:x + m.shape[1]] |= m


def _clear(canvas: np.ndarray, m: np.ndarray, x: int, y: int, pad: int) -> None:
    """Clear a ``pad`` px margin around the ink of ``m`` placed at (x, y)."""
    h, w = canvas.shape
    grown = np.zeros((m.shape[0] + 2 * pad, m.shape[1] + 2 * pad), bool)
    for dy in range(2 * pad + 1):
        for dx in range(2 * pad + 1):
            grown[dy:dy + m.shape[0], dx:dx + m.shape[1]] |= m
    y0, x0 = y - pad, x - pad
    sy, sx = max(0, -y0), max(0, -x0)
    ey, ex = min(grown.shape[0], h - y0), min(grown.shape[1], w - x0)
    canvas[y0 + sy:y0 + ey, x0 + sx:x0 + ex] &= ~grown[sy:ey, sx:ex]


def _save(canvas: np.ndarray, path: Path) -> None:
    a = (canvas * 255).astype(np.uint8)
    Image.merge("RGBA", (Image.fromarray(a),) * 4).save(path)


def worded(base: Path, word: str, path: Path, size=(40, 36), top: float = 1.0) -> None:
    """``base`` over ``word``: the word at the bottom (9 px caps), the icon
    fitted into the space above with a 2 px gap. ``top``: see `_mask`."""
    w, h = size
    canvas = np.zeros((h, w), bool)
    t = _word(word, w)
    _paste(canvas, t, (w - t.shape[1]) // 2, h - t.shape[0])
    g = _mask(base, (w, h - t.shape[0] - 2), top)
    _paste(canvas, g, (w - g.shape[1]) // 2, 0)
    _save(canvas, path)


def side_word(base: Path, word: str, path: Path, size=(40, 36), word_px: int = 20) -> None:
    """``base`` on the left, ``word`` (a digit or two letters) on the right,
    both centred on the cell's height."""
    w, h = size
    canvas = np.zeros((h, w), bool)
    t = _word(word, w // 2 - 2, px=word_px)
    _paste(canvas, t, w - t.shape[1], (h - t.shape[0]) // 2)
    g = _mask(base, (w - t.shape[1] - 3, h))
    _paste(canvas, g, 0, (h - g.shape[0]) // 2)
    _save(canvas, path)


def badged(base: Path, badge, path: Path, size=(40, 36), frac: float = 0.55) -> None:
    """``base`` fitted into the upper left 78 % of the cell, ``badge`` (an
    icon path, or "left"/"right"/"up"/"down" for an arrow) into ``frac`` of the
    cell height at the lower right, with 2 px cleared around it."""
    w, h = size
    canvas = np.zeros((h, w), bool)
    g = _mask(base, (int(w * 0.78), int(h * 0.78)))
    _paste(canvas, g, 0, 0)
    bs = int(h * frac)
    if isinstance(badge, str):
        b = _arrow(badge, bs, bs)
    else:
        b = _mask(badge, (bs, bs))
    bx, by = w - b.shape[1], h - b.shape[0]
    _clear(canvas, b, bx, by, 2)
    _paste(canvas, b, bx, by)
    _save(canvas, path)


def arrowed(base: Path, direction: str, path: Path, size=(40, 36)) -> None:
    """``base`` over a heavy arrow pointing ``direction`` (left or right)."""
    w, h = size
    canvas = np.zeros((h, w), bool)
    ah = 11
    a = _arrow(direction, w - 6, ah)
    _paste(canvas, a, 3, h - ah)
    g = _mask(base, (w, h - ah - 2))
    _paste(canvas, g, (w - g.shape[1]) // 2, 0)
    _save(canvas, path)
