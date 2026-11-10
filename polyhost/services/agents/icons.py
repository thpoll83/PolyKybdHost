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
_CHECK = [
    "..........##",
    ".........###",
    "........###.",
    "##.....###..",
    "###...###...",
    ".###.###....",
    "..#####.....",
    "...###......",
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
_ARROW_HEAD = [   # points right
    "#...",
    "##..",
    "###.",
    "####",
    "###.",
    "##..",
    "#...",
]


def waiting():
    """A filled disk with '!' cut out."""
    return _stamp(_disk(9), _EXCLAIM, _C - 1, 4, value=False)


def done():
    """A ring with a check mark."""
    return _stamp(_ring(9, 2), _CHECK, 3, 5)


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
    carrying a head that points right, i.e. clockwise."""
    ring = _ring(8, 2)

    def keep(dx, dy):
        # Angle 0 = right, counter-clockwise, in screen coordinates (y down).
        angle = math.degrees(math.atan2(-dy, dx)) % 360
        return not (15 <= angle <= 85)
    mask = ring & _grid(keep)
    # The top end of the ring is at x ~9, band rows 1..2; the head is centred there.
    return _stamp(mask, _ARROW_HEAD, _C, 0)


def microphone():
    """A microphone: capsule, U-shaped holder, stand and foot."""
    import numpy as np
    mask = np.zeros((SIZE + 3, SIZE), dtype=bool)
    # Capsule: 7 wide, rounded top and bottom, rows 0..11.
    for y in range(12):
        for x in range(SIZE):
            dx = x - _C
            if abs(dx) <= 3:
                if 3 <= y <= 8 or (y < 3 and dx * dx + (y - 3) ** 2 <= 12.25) \
                        or (y > 8 and dx * dx + (y - 8) ** 2 <= 12.25):
                    mask[y, x] = True
    # Holder: the lower half of a ring around the capsule.
    for y in range(6, 16):
        for x in range(SIZE):
            dx, dy = x - _C, y - 7
            d2 = dx * dx + dy * dy
            if dy >= 0 and 5.5 ** 2 < d2 <= 7.5 ** 2:
                mask[y, x] = True
    mask[15:19, _C - 1:_C + 1] = True     # stand
    mask[19:21, _C - 4:_C + 5] = True     # foot
    return mask


def right_arrow(width=13):
    """A 2 px shaft with a solid head, pointing right, 9 px tall."""
    import numpy as np
    mask = np.zeros((9, width), dtype=bool)
    mask[3:6, : width - 4] = True
    for i in range(5):
        mask[4 - i: 5 + i, width - 1 - i] = True
    return mask
