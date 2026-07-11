"""Faithful Python/NumPy port of fontconvert's dither.c — the pixel pipeline.

This is the host-side reimplementation of the colour/gray → 1-bit conversion the C
`fontconvert` tool performs, so the inspector can *build* trial glyphs (font-pack
extend path) without the compiled binary.  It mirrors dither.c function-for-function
so output matches the C tool bit-for-bit on the deterministic paths (given the same
FreeType bitmap input):

  bgra_to_gray (composite over BLACK, gray = a·lum) · gray8_to_float ·
  bilinear scale_gray · fit_dimensions · normalize(-N, 99th pct) · unsharp(-U) ·
  gamma(-G) · contrast(-c) · exposure(-e) · {floyd_steinberg, stucki, bayer,
  threshold, random}(-D) · invert(-I) · interior edges(-E) · outline(-O,
  alpha-inner for colour / morphological dilation for mono).

Bits are MSB-first, row-major continuous (i = y·w + x), byte-padded per glyph —
the GFXfont packing.  Computation is float32 to track the C `float` arithmetic
(Floyd–Steinberg error diffusion is order-sensitive); `-D random` is the only
mode that can't be bit-exact (C uses srand(0)+rand()).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Dither modes (match types.h DitherMode enum order/names).
DITHER_FLOYD_STEINBERG = 0
DITHER_STUCKI = 1
DITHER_BAYER = 2
DITHER_THRESHOLD = 3
DITHER_RANDOM = 4

_DITHER_NAMES = {"fs": DITHER_FLOYD_STEINBERG, "floyd": DITHER_FLOYD_STEINBERG,
                 "stucki": DITHER_STUCKI, "bayer": DITHER_BAYER,
                 "threshold": DITHER_THRESHOLD, "random": DITHER_RANDOM}

EDGE_THRESH = np.float32(0.28)   # -E gradient magnitude that counts as a feature edge
EDGE_BAND = 2                    # -E keep edges this many px clear of the alpha boundary
NORM_PCT = 99.0                  # -N white point = 99th percentile


def dither_mode_from_name(name: str) -> int:
    if name not in _DITHER_NAMES:
        raise ValueError(f"unknown dither mode {name!r}; valid: {sorted(_DITHER_NAMES)}")
    return _DITHER_NAMES[name]


@dataclass
class DitherOpts:
    """Mirror of the dither-relevant FontSettings fields."""
    render_mode: int = 0          # -g (1 = grayscale/colour quantise)
    dither_mode: int = DITHER_FLOYD_STEINBERG
    normalize: bool = False       # -N
    sharpness: float = 0.0        # -U
    gamma_val: float = 1.0        # -G
    contrast: float = 1.0         # -c
    exposure: float = 0.0         # -e
    saturation_boost: float = 0.0 # -B
    outline: int = 0              # -O
    invert: bool = False          # -I
    edge_preserve: bool = False   # -E
    max_width: int = 0            # -W
    height: int = 0               # -r (render-size limit used by fit_dimensions)


# ───────────────────────────── bit buffer (enbit) ───────────────────────────

class _Bits:
    """MSB-first packed-bit buffer, row-major continuous — fontconvert's enbit()."""
    __slots__ = ("buf",)

    def __init__(self, n_bits: int):
        self.buf = bytearray((n_bits + 7) // 8)

    def set(self, i: int):
        self.buf[i >> 3] |= 0x80 >> (i & 7)

    def get(self, i: int) -> int:
        return (self.buf[i >> 3] >> (7 - (i & 7))) & 1

    def flip(self, i: int):
        self.buf[i >> 3] ^= 0x80 >> (i & 7)


# ───────────────────────────── colour/gray buffers ──────────────────────────

def bgra_to_gray(buf: bytes, pitch: int, width: int, rows: int,
                 saturation_boost: float = 0.0) -> np.ndarray:
    """BGRA (straight alpha) → float32 gray over BLACK: gray = a·lum (dither.c)."""
    arr = np.frombuffer(buf, dtype=np.uint8)[:rows * pitch].reshape(rows, pitch)
    arr = arr[:, :width * 4].reshape(rows, width, 4).astype(np.float32) / np.float32(255.0)
    b, g, r, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    lum = np.float32(0.2126) * r + np.float32(0.7152) * g + np.float32(0.0722) * b
    if saturation_boost > 0.0:
        cmax = np.maximum(np.maximum(r, g), b)
        cmin = np.minimum(np.minimum(r, g), b)
        sat = np.where(cmax > 0.0, (cmax - cmin) / np.maximum(cmax, np.float32(1e-20)), np.float32(0.0))
        lum = np.minimum(lum + np.float32(saturation_boost) * sat, np.float32(1.0))
    return (a * lum).astype(np.float32)


def gray8_to_float(buf: bytes, pitch: int, width: int, rows: int) -> np.ndarray:
    arr = np.frombuffer(buf, dtype=np.uint8)[:rows * pitch].reshape(rows, pitch)
    return (arr[:, :width].astype(np.float32) / np.float32(255.0))


def fit_dimensions(src_w: int, src_h: int, max_w: int, max_h: int):
    out_w, out_h = src_w, src_h
    if max_h > 0 and src_h > max_h:
        out_w = src_w * max_h // src_h
        out_h = max_h
    if max_w > 0 and out_w > max_w:
        out_h = out_h * max_w // out_w
        out_w = max_w
    return max(out_w, 1), max(out_h, 1)


def scale_gray(src: np.ndarray, dst_w: int, dst_h: int) -> np.ndarray:
    """Bilinear downscale matching dither.c scale_gray_buf (float32, src-1 span)."""
    src_h, src_w = src.shape
    if (src_w, src_h) == (dst_w, dst_h):
        return src
    xs = np.arange(dst_w, dtype=np.float32) * np.float32(src_w - 1) / np.float32(max(dst_w - 1, 1))
    ys = np.arange(dst_h, dtype=np.float32) * np.float32(src_h - 1) / np.float32(max(dst_h - 1, 1))
    x0 = xs.astype(np.int32); x1 = np.minimum(x0 + 1, src_w - 1); fx = xs - x0
    y0 = ys.astype(np.int32); y1 = np.minimum(y0 + 1, src_h - 1); fy = ys - y0
    fx = fx[None, :]; fy = fy[:, None]
    s00 = src[np.ix_(y0, x0)]; s01 = src[np.ix_(y0, x1)]
    s10 = src[np.ix_(y1, x0)]; s11 = src[np.ix_(y1, x1)]
    out = (s00 * (1 - fx) * (1 - fy) + s01 * fx * (1 - fy)
           + s10 * (1 - fx) * fy + s11 * fx * fy)
    return out.astype(np.float32)


# ───────────────────────────── adjustments (in place) ───────────────────────

def _normalize(gray: np.ndarray):
    total = gray.size
    b = np.clip((gray * 255.0 + 0.5).astype(np.int32), 0, 255)
    hist = np.bincount(b.ravel(), minlength=256)
    allow = int(total * (100.0 - NORM_PCT) / 100.0)
    acc, refb = 0, 0
    for bb in range(255, -1, -1):
        acc += int(hist[bb])
        if acc > allow:
            refb = bb
            break
    ref = refb / 255.0
    if 1e-4 < ref < 1.0:
        gray *= np.float32(1.0 / ref)
        np.minimum(gray, np.float32(1.0), out=gray)


def _unsharp(gray: np.ndarray, amount: float):
    pad = np.pad(gray, 1, mode="edge")
    k = np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=np.float32) / np.float32(16.0)
    blur = np.zeros_like(gray)
    for dy in range(3):
        for dx in range(3):
            blur += pad[dy:dy + gray.shape[0], dx:dx + gray.shape[1]] * k[dy, dx]
    out = gray + np.float32(amount) * (gray - blur)
    np.clip(out, 0.0, 1.0, out=gray)


def apply_adjustments(gray: np.ndarray, o: DitherOpts) -> np.ndarray | None:
    """Port of apply_dithering's pre-dither stage (normalize→unsharp→gamma→
    contrast→exposure) in place; returns the pre-dither snapshot for -E or None."""
    if o.normalize:
        _normalize(gray)
    if o.sharpness > 0.0:
        _unsharp(gray, o.sharpness)
    if o.gamma_val != 1.0:
        inv_g = np.float32(1.0 / o.gamma_val)
        pos = gray > 0.0
        gray[pos] = np.power(gray[pos], inv_g)
        gray[~pos] = 0.0
    if o.contrast != 1.0:
        np.clip((gray - np.float32(0.5)) * np.float32(o.contrast) + np.float32(0.5),
                0.0, 1.0, out=gray)
    if o.exposure != 0.0:
        np.clip(gray + np.float32(o.exposure), 0.0, 1.0, out=gray)
    return gray.copy() if o.edge_preserve else None


# ───────────────────────────── dithering → bits ─────────────────────────────

def _fs(gray: np.ndarray, bits: _Bits):
    g = gray.copy()
    h, w = g.shape
    f7 = np.float32(7.0 / 16.0); f3 = np.float32(3.0 / 16.0)
    f5 = np.float32(5.0 / 16.0); f1 = np.float32(1.0 / 16.0)
    for y in range(h):
        for x in range(w):
            old = g[y, x]
            if old < 0.0: old = np.float32(0.0)
            if old > 1.0: old = np.float32(1.0)
            new = np.float32(1.0) if old >= 0.5 else np.float32(0.0)
            if new >= 0.5:
                bits.set(y * w + x)
            err = old - new
            if x + 1 < w:
                g[y, x + 1] += err * f7
            if y + 1 < h:
                if x > 0:
                    g[y + 1, x - 1] += err * f3
                g[y + 1, x] += err * f5
                if x + 1 < w:
                    g[y + 1, x + 1] += err * f1


def _stucki(gray: np.ndarray, bits: _Bits):
    g = gray.copy()
    h, w = g.shape
    taps = [(0, 1, 8), (0, 2, 4),
            (1, -2, 2), (1, -1, 4), (1, 0, 8), (1, 1, 4), (1, 2, 2),
            (2, -2, 1), (2, -1, 2), (2, 0, 4), (2, 1, 2), (2, 2, 1)]
    d = np.float32(42.0)
    for y in range(h):
        for x in range(w):
            old = g[y, x]
            if old < 0.0: old = np.float32(0.0)
            if old > 1.0: old = np.float32(1.0)
            new = np.float32(1.0) if old >= 0.5 else np.float32(0.0)
            if new >= 0.5:
                bits.set(y * w + x)
            err = old - new
            for dy, dx, wt in taps:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and ny < h:
                    g[ny, nx] += err * np.float32(wt) / d


_BAYER = np.array([[0.5, 8.5, 2.5, 10.5],
                   [12.5, 4.5, 14.5, 6.5],
                   [3.5, 11.5, 1.5, 9.5],
                   [15.5, 7.5, 13.5, 5.5]], dtype=np.float32) / np.float32(16.0)


def _bayer(gray: np.ndarray, bits: _Bits):
    h, w = gray.shape
    thr = _BAYER[np.arange(h)[:, None] & 3, np.arange(w)[None, :] & 3]
    mask = gray >= thr
    for i in np.flatnonzero(mask.ravel()):
        bits.set(int(i))


def _threshold(gray: np.ndarray, bits: _Bits):
    for i in np.flatnonzero((gray >= np.float32(0.5)).ravel()):
        bits.set(int(i))


def _random(gray: np.ndarray, bits: _Bits, rng):
    h, w = gray.shape
    flat = gray.ravel()
    for i in range(flat.size):
        v = flat[i]
        if v <= 0.0:
            continue
        if v >= 1.0:
            bits.set(i)
        elif (rng.randrange(256)) < int(v * 256.0):
            bits.set(i)


def dither(gray: np.ndarray, mode: int, bits: _Bits, rng=None):
    if mode == DITHER_STUCKI:
        _stucki(gray, bits)
    elif mode == DITHER_BAYER:
        _bayer(gray, bits)
    elif mode == DITHER_THRESHOLD:
        _threshold(gray, bits)
    elif mode == DITHER_RANDOM:
        import random as _r
        _random(gray, bits, rng or _r.Random(0))
    else:
        _fs(gray, bits)


# ───────────────────────────── post-processes ───────────────────────────────

def _alpha_mask_scaled(bgra: bytes, pitch: int, sw: int, sh: int, out_w: int, out_h: int):
    arr = np.frombuffer(bgra, dtype=np.uint8)[:sh * pitch].reshape(sh, pitch)
    a = (arr[:, 3:sw * 4:4] > 0).astype(np.float32)
    if (sw, sh) != (out_w, out_h):
        a = scale_gray(a, out_w, out_h)
    return a >= np.float32(0.5)      # bool (out_h, out_w)


def _invert(bits: _Bits, mask: np.ndarray):
    for i in np.flatnonzero(mask.ravel()):
        bits.flip(int(i))


def _interior_edges(bits: _Bits, edge_gray: np.ndarray, mask: np.ndarray):
    h, w = edge_gray.shape
    b = EDGE_BAND
    thr2 = EDGE_THRESH * EDGE_THRESH
    for y in range(b, h - b):
        for x in range(b, w - b):
            if not mask[y, x]:
                continue
            near = False
            for dy in range(-b, b + 1):
                for dx in range(-b, b + 1):
                    if not mask[y + dy, x + dx]:
                        near = True
                        break
                if near:
                    break
            if near:
                continue
            gx = edge_gray[y, x + 1] - edge_gray[y, x - 1]
            gy = edge_gray[y + 1, x] - edge_gray[y - 1, x]
            if gx * gx + gy * gy > thr2:
                bits.set(y * w + x)


def _alpha_content_outline(bits: _Bits, mask: np.ndarray, t: int):
    h, w = mask.shape
    for y in range(h):
        for x in range(w):
            is_c = mask[y, x]
            near = False
            for dy in range(-t, t + 1):
                if near:
                    break
                for dx in range(-t, t + 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if nx < 0 or nx >= w or ny < 0 or ny >= h:
                        if is_c:
                            near = True
                            break
                        continue
                    if bool(mask[ny, nx]) != bool(is_c):
                        near = True
                        break
            if is_c and near:
                bits.set(y * w + x)


def _morphological_outline(bits: _Bits, w: int, h: int, t: int):
    src = bytes(bits.buf)

    def lit(i):
        return (src[i >> 3] >> (7 - (i & 7))) & 1
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if lit(idx):
                continue
            found = False
            for dy in range(-t, t + 1):
                if found:
                    break
                for dx in range(-t, t + 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and lit(ny * w + nx):
                        found = True
                        break
            if found:
                bits.set(idx)


# ───────────────────────────── top-level dispatch ───────────────────────────

def render_bitmap_to_bits(pixel_mode: int, width: int, rows: int, pitch: int,
                          buf: bytes, o: DitherOpts, rng=None):
    """Port of render_bitmap_to_bits + render_core: FreeType bitmap → (packed
    bytes, out_w, out_h).  `pixel_mode`: 1=MONO, 2=GRAY, 7=BGRA (FreeType values)."""
    FT_PIXEL_MODE_MONO, FT_PIXEL_MODE_GRAY, FT_PIXEL_MODE_BGRA = 1, 2, 7
    is_bgra = pixel_mode == FT_PIXEL_MODE_BGRA

    # render_core → packed bits + out dims + (optional) edge snapshot
    edge_gray = None
    if is_bgra:
        gray = bgra_to_gray(buf, pitch, width, rows, o.saturation_boost)
        out_w, out_h = fit_dimensions(width, rows, o.max_width, o.height)
        if (out_w, out_h) != (width, rows):
            gray = scale_gray(gray, out_w, out_h)
        edge_gray = apply_adjustments(gray, o)
        bits = _Bits(out_w * out_h)
        dither(gray, o.dither_mode, bits, rng)
    elif o.render_mode == 1 and pixel_mode == FT_PIXEL_MODE_GRAY:
        out_w, out_h = width, rows
        gray = gray8_to_float(buf, pitch, width, rows)
        edge_gray = apply_adjustments(gray, o)
        bits = _Bits(out_w * out_h)
        dither(gray, o.dither_mode, bits, rng)
    else:  # mono — direct bit extraction, no dither
        out_w, out_h = width, rows
        bits = _Bits(out_w * out_h)
        for y in range(rows):
            base = y * pitch
            for x in range(width):
                if buf[base + (x >> 3)] & (0x80 >> (x & 7)):
                    bits.set(y * width + x)

    # post-processes (order: invert → interior edges → outline)
    post = (o.outline > 0) or (is_bgra and (o.invert or o.edge_preserve))
    if post:
        if is_bgra:
            mask = _alpha_mask_scaled(buf, pitch, width, rows, out_w, out_h)
            if o.invert:
                _invert(bits, mask)
            if o.edge_preserve and edge_gray is not None \
                    and edge_gray.shape == (out_h, out_w):
                _interior_edges(bits, edge_gray, mask)
            if o.outline > 0:
                _alpha_content_outline(bits, mask, o.outline)
        elif o.outline > 0:
            _morphological_outline(bits, out_w, out_h, o.outline)

    return bytes(bits.buf), out_w, out_h
