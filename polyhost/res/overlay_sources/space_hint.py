"""The "hold Space" hint drawn on the Space key: a glyph with an arrow on each
side, at the right edge of the full 72x40 keycap.

Space is on the thumb row, where the firmware centres the legend horizontally
(`draw_legend_cx_cy` in qmk_firmware poly_keymap.c). The ␣ legend is drawn at
x 23..48, y 23..26, and the firmware clears the legend within 3 px of any
overlay ink. The cluster sits at the right edge, rows 0..34, and keeps clear of
that ␣ plus its 3 px margin.

A binding using it sets `region: [72, 40]` so the generator copies the PNG 1:1.

    from polyhost.res.overlay_sources import space_hint
    space_hint.draw(glyph_mask, out / "space_pan.png")
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

W, H = 72, 40
ARROW = 4                         # arrow half-width and depth, px
LEGEND_BOX = (23, 23, 48, 26)     # x0, y0, x1, y1 of the centred ␣ legend
COURTYARD = 3                     # firmware clears the legend this close to ink


def glyph_from_png(path: Path, size: int) -> np.ndarray:
    """`path` reduced to a bool mask that fits `size` x `size`, the same way
    the overlay generator converts an icon (scripts/generate_app_overlays.py)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    import generate_app_overlays as gen
    m = gen.render_icon(path, "contain", 150, None, (0, 0, size, size), "auto")
    return m[:size, :size].astype(bool)


def _tri(m: np.ndarray, pts) -> None:
    im = Image.fromarray((m * 255).astype("uint8"))
    ImageDraw.Draw(im).polygon(pts, fill=255)
    m[:] = np.array(im) > 0


def draw(glyph: np.ndarray, dest: Path, *, gap_v: int = 2, gap_h: int = 2) -> None:
    """Write `glyph` (bool mask, cropped to its ink here) with an arrow above,
    below, left and right of it, as a white-on-transparent 72x40 PNG.
    Raises if any ink comes within the courtyard of the ␣ legend."""
    rows, cols = np.where(glyph.any(1))[0], np.where(glyph.any(0))[0]
    g = glyph[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    gh, gw = g.shape
    a, right = ARROW, W - 1
    m = np.zeros((H, W), bool)
    gx, gy = right - a - gap_h - gw, a + gap_v + 1
    m[gy:gy + gh, gx:gx + gw] |= g
    cx, cy = gx + gw // 2, gy + gh // 2
    _tri(m, [(cx, 0), (cx - a, a), (cx + a, a)])
    yb = gy + gh + gap_v
    _tri(m, [(cx, yb + a), (cx - a, yb), (cx + a, yb)])
    xl = gx - gap_h - a - 1
    _tri(m, [(xl, cy), (xl + a, cy - a), (xl + a, cy + a)])
    _tri(m, [(right, cy), (right - a, cy - a), (right - a, cy + a)])

    x0, y0, x1, y1 = LEGEND_BOX
    c = COURTYARD
    if m[max(y0 - c, 0):y1 + c + 1, max(x0 - c, 0):x1 + c + 1].any():
        raise ValueError(f"{dest.name}: ink within {c} px of the Space legend")
    alpha = Image.fromarray((m * 255).astype("uint8"))
    img = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    img.putalpha(alpha)
    img.save(dest)
