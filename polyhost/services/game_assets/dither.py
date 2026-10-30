"""Turn a grey image into a 1-bit keycap icon: fit, dither the inside, light the outline.

Used by the shipped C&C unit renders (`res/overlay_sources/cnc_remastered/wz_units.py`)
and by the runtime reader of the game's own sprites (`westwood_td/reader.py`), so both
look alike.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter


def edge(a: np.ndarray) -> np.ndarray:
    """The pixels of `a` that touch the outside in one of the four axis directions."""
    p = np.pad(a, 1)
    return a & ~(p[2:, 1:-1] & p[:-2, 1:-1] & p[1:-1, 2:] & p[1:-1, :-2])


def dilate(m: np.ndarray, n: int) -> np.ndarray:
    """`m` grown by `n` px in the four axis directions per step, as
    scipy.ndimage.binary_dilation does with its default cross."""
    out = m.copy()
    for _ in range(n):
        grown = out.copy()
        grown[1:, :] |= out[:-1, :]
        grown[:-1, :] |= out[1:, :]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        out = grown
    return out


def keycap(img, cover, size, blur=0.4, floor=0.15, mirror=False,
           lo_p=3, hi_p=97, curve=0.0, sharpen=0.0, outline=True, gamma=1.0, levels=0):
    """Fit `img` (grey, 0..1) inside `size` (w, h), dither the inside and light
    the 1 px outline of `cover` (with `outline` False, dither all of `cover`).

    `lo_p`/`hi_p` are the percentiles stretched to black and white. `curve` > 0
    adds an S-curve that pushes mid-tones to black or white, and `sharpen` > 0 an
    unsharp mask before the dither; both give small sprites firmer shapes.
    `gamma` < 1 lightens the mid-tones. `levels` 3 replaces the error diffusion
    with three flat levels: unlit, a 50 % checker, lit. The defaults reproduce
    the shipped Warzone renders byte for byte."""
    ys, xs = np.nonzero(cover)
    img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    cover = cover[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if mirror:
        img, cover = img[:, ::-1], cover[:, ::-1]
    s = min(size[0] / img.shape[1], size[1] / img.shape[0])
    size = (max(1, round(img.shape[1] * s)), max(1, round(img.shape[0] * s)))
    gi = Image.fromarray((img * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur / s))
    gi = gi.resize(size, Image.LANCZOS)
    if sharpen:
        gi = gi.filter(ImageFilter.UnsharpMask(radius=1.5, percent=int(sharpen * 100), threshold=0))
    g = np.asarray(gi, float) / 255
    a = np.asarray(Image.fromarray((cover * 255).astype(np.uint8)).resize(size, Image.LANCZOS)) > 127
    lo, hi = np.percentile(g[a], lo_p), np.percentile(g[a], hi_p)
    g = np.clip((g - lo) / max(hi - lo, 1e-6), 0, 1) ** gamma
    if curve:
        k = 1 + 4 * curve
        g = 0.5 + np.tanh((g - 0.5) * k) / (2 * np.tanh(0.5 * k))
    out = edge(a) if outline else np.zeros_like(a)
    inside = a & ~out
    v = np.where(inside, floor + (1 - floor) * g, 0)
    if levels == 3:
        yy, xx = np.mgrid[0:v.shape[0], 0:v.shape[1]]
        fill = (v > 2 / 3) | ((v > 1 / 3) & ((yy + xx) % 2 == 0))
    elif levels:
        raise ValueError(f"levels must be 0 or 3, not {levels}")
    else:
        fill = np.asarray(Image.fromarray((v * 255).astype(np.uint8)).convert("1")) > 0
    return out | (fill & inside)


def with_plus(mask: np.ndarray, size: int = 13, bar: int = 3, top: bool = False,
              seam: int = 3) -> np.ndarray:
    """A plus (Ctrl: create group, set bookmark) in the bottom-right corner, or
    the top-right with `top`, with `seam` px of clear space around it."""
    h, w = mask.shape
    p = np.zeros((h, w), bool)
    cy, cx = (size // 2 if top else h - size // 2 - 1), w - size // 2 - 1
    p[cy - bar // 2:cy + bar // 2 + 1, cx - size // 2:cx + size // 2 + 1] = True
    p[cy - size // 2:cy + size // 2 + 1, cx - bar // 2:cx + bar // 2 + 1] = True
    return (mask & ~dilate(p, seam)) | p


def _disc(h, w, cy, cx, r):
    yy, xx = np.mgrid[0:h, 0:w]
    disc = (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r
    return disc, disc & dilate(~disc, 1)


def with_mark(mask: np.ndarray, kind: str, size: int = 13) -> np.ndarray:
    """`mask` (a control group) with a modifier mark in the bottom-right corner,
    the group cleared 2 px around it: "ring" a plus in a ring (Ctrl+Shift: add
    to the group), "box" a plus in a square (Shift: add the group to the
    selection), "sight" a ring with four ticks (Alt: jump to the group)."""
    if kind not in ("ring", "box", "sight"):
        raise ValueError(f"unknown mark {kind!r}")
    h, w = mask.shape
    r = size // 2
    cy, cx = h - r - 3, w - r - 3                  # the ring (radius r + 1) inside the cell
    plus = np.zeros((h, w), bool)
    plus[cy - 1:cy + 2, cx - r + 2:cx + r - 1] = True
    plus[cy - r + 2:cy + r - 1, cx - 1:cx + 2] = True
    if kind == "ring":
        area, ring = _disc(h, w, cy, cx, r + 1)
        m = ring | plus
    elif kind == "box":
        area = np.zeros((h, w), bool)
        area[cy - r:cy + r + 1, cx - r:cx + r + 1] = True
        m = (area & dilate(~area, 1)) | plus
    else:
        area, ring = _disc(h, w, cy, cx, r - 1)
        m = ring.copy()
        m[cy, cx - r:cx - r + 4] = m[cy, cx + r - 3:cx + r + 1] = True
        m[cy - r:cy - r + 4, cx] = m[cy + r - 3:cy + r + 1, cx] = True
        area = area | m
    return (mask & ~dilate(area, 2)) | m


def scale2x(m: np.ndarray) -> np.ndarray:
    """EPX / Scale2x on a boolean image: doubles it and rounds the stair-steps."""
    p = np.pad(m, 1, mode="edge")
    up, right, left, down = p[:-2, 1:-1], p[1:-1, 2:], p[1:-1, :-2], p[2:, 1:-1]
    out = np.zeros((m.shape[0] * 2, m.shape[1] * 2), bool)
    out[0::2, 0::2] = np.where((left == up) & (left != down) & (up != right), up, m)
    out[0::2, 1::2] = np.where((up == right) & (up != left) & (right != down), right, m)
    out[1::2, 0::2] = np.where((down == left) & (down != right) & (left != up), left, m)
    out[1::2, 1::2] = np.where((right == down) & (right != up) & (down != left), down, m)
    return out
