"""Pixel-exact 1-bit icons for the agent cards.

⚠️ Not drawn with PIL's ellipse/arc and not scaled: at 19 px and 1 bit those come
out lopsided and ragged (first hardware test, 2026-11-10). Each shape is a mask
from a distance test at pixel centres, so a circle is symmetric on both axes, and
the glyphs inside are placed pixel by pixel.
"""
from __future__ import annotations

import math

SIZE = 19          # odd, so there is a centre pixel
_C = SIZE // 2     # 9


def _grid(fn):
    import numpy as np
    out = np.zeros((SIZE, SIZE), dtype=bool)
    for y in range(SIZE):
        for x in range(SIZE):
            out[y, x] = fn(x - _C, y - _C)
    return out


def _disk(r):
    return _grid(lambda dx, dy: dx * dx + dy * dy <= (r + 0.5) ** 2)


def _ring(r, w):
    inner = (r - w + 0.5) ** 2
    return _grid(lambda dx, dy: inner < dx * dx + dy * dy <= (r + 0.5) ** 2)


def _stamp(mask, rows, x0, y0, value=True):
    """Set (or clear) the '#' pixels of `rows` with the top-left at (x0, y0)."""
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch == "#":
                mask[y0 + dy, x0 + dx] = value
    return mask


_EXCLAIM = ["###"] * 8 + ["..."] + ["###"] * 2
# 11 x 7, so its bounding box centres on the ring's centre pixel (9, 9).
_CHECK = [
    ".........##",
    "........##.",
    ".......##..",
    "##....##...",
    ".##..##....",
    "..####.....",
    "...##......",
]
_QUESTION = [
    ".####.",
    "##..##",
    "....##",
    "...##.",
    "..##..",
    "..##..",
    "......",
    "..##..",
]
# Points right. 6 rows, so it is symmetric about the half-pixel line between the
# two rows of the ring's 2 px band at its top end (rows 2 and 3).
_ARROW_HEAD = [
    "#..",
    "##.",
    "###",
    "###",
    "##.",
    "#..",
]


def waiting():
    """A filled disk with '!' cut out."""
    return _stamp(_disk(9), _EXCLAIM, _C - 1, 4, value=False)


def done():
    """A ring with a check mark."""
    return _stamp(_ring(9, 2), _CHECK, _C - 5, _C - 3)


def stale():
    """A ring with '?'."""
    return _stamp(_ring(9, 2), _QUESTION, _C - 3, 5)


def idle():
    """A crescent moon: a disk minus a disk moved up and right."""
    import numpy as np
    big = _disk(8)
    cut = np.zeros_like(big)
    shift_x, shift_y = 4, -3
    small = _disk(7)
    for y in range(SIZE):
        for x in range(SIZE):
            sy, sx = y - shift_y, x - shift_x
            if 0 <= sy < SIZE and 0 <= sx < SIZE and small[sy, sx]:
                cut[y, x] = True
    return big & ~cut


def working():
    """A circular arrow (refresh): a ring open at the top right, its top end
    carrying a head that points right, i.e. clockwise.

    The ring is r=7 so its top band (rows 2..3 at the centre column) leaves room
    above it for the head, and the gap ends exactly at 90 degrees, so the band
    stops at column 8 and the head starts at column 9, centred on the band."""
    ring = _ring(7, 2)

    def keep(dx, dy):
        # Angle 0 = right, counter-clockwise, in screen coordinates (y down).
        angle = math.degrees(math.atan2(-dy, dx)) % 360
        return not (20 <= angle <= 90)
    mask = ring & _grid(keep)
    return _stamp(mask, _ARROW_HEAD, _C, 0)


def microphone(scale: float = 1.0):
    """A microphone: capsule, U-shaped holder, stand and foot, about 22 x 19 px
    times `scale`, from distance tests at pixel centres."""
    import numpy as np
    h, w = int(22 * scale), int(19 * scale)
    mask = np.zeros((h, w), dtype=bool)
    cx = (w - 1) / 2
    r = 3.5 * scale                     # capsule half width
    top, bottom = r, 11.5 * scale - r   # centres of its round ends
    ring_y = 7 * scale
    for y in range(h):
        yy = y + 0.5
        for x in range(w):
            dx = x - cx
            if abs(dx) <= r and (top <= yy <= bottom
                                 or dx * dx + (yy - top) ** 2 <= r * r
                                 or dx * dx + (yy - bottom) ** 2 <= r * r):
                mask[y, x] = True       # capsule
            d = (dx * dx + (yy - ring_y) ** 2) ** 0.5
            if yy >= ring_y and 5.5 * scale < d <= 7.5 * scale:
                mask[y, x] = True       # holder: the lower half of a ring
    stand = max(2, round(2 * scale))
    sx = int(round(cx - stand / 2 + 0.5))
    mask[int(15 * scale):int(19 * scale), sx:sx + stand] = True
    foot = int(9 * scale)
    fx = int(round(cx - foot / 2 + 0.5))
    mask[int(19 * scale):int(21 * scale) + 1, fx:fx + foot] = True
    return mask


def waiting_disk(r: int):
    """The waiting icon at radius `r`: a filled disk with '!' cut out."""
    import numpy as np
    n = 2 * r + 1
    yy, xx = np.mgrid[0:n, 0:n]
    mask = (xx - r) ** 2 + (yy - r) ** 2 <= (r + 0.5) ** 2
    bar = max(3, r // 3) | 1
    x0 = r - bar // 2
    mask[int(r * 0.45):int(r * 1.25), x0:x0 + bar] = False
    dot = int(r * 1.45)
    mask[dot:dot + bar, x0:x0 + bar] = False
    return mask


def scaled(mask, px: int):
    """`mask` resampled to px x px (Lanczos, then a threshold), for the 16 px
    state icons on the agent cards."""
    import numpy as np
    from PIL import Image
    img = Image.fromarray(np.asarray(mask, dtype=np.uint8) * 255).resize((px, px), Image.LANCZOS)
    return np.array(img) >= 110


def right_arrow(width=13):
    """A 2 px shaft with a solid head, pointing right, 9 px tall."""
    import numpy as np
    mask = np.zeros((9, width), dtype=bool)
    mask[3:6, : width - 4] = True
    for i in range(5):
        mask[4 - i: 5 + i, width - 1 - i] = True
    return mask
