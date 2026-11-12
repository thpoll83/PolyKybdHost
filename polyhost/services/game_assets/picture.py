"""The icon picker's renderer (tools/icon_picker_template.html), in Python.

The page and the readers must draw the same pixels, so this is a line-by-line
port of the page's JavaScript, including where the page stores values as
32-bit floats (its Float32Array buffers): every such store is rounded with
`_f32` here. A recipe chosen in the page then looks the same on the keyboard.
tests/services/game_assets_picture_test.py pins known answers.

Three kinds of drawing, each fitted into a region (w, h) and placed in it as
the page places it (right-aligned, top / centre / bottom):

- ``picture(idx, palette, p, region)``: a palette-index image, by the
  ``dither`` engine (cut the background, fit, sharpen, stretch, gamma, S-curve,
  floor, then levels / error diffusion / Bayer / threshold inside a lit
  outline) or the ``pixel`` engine (chosen pixels at a whole-number scale);
- ``vector(alpha, p, region)``: an icon's silhouette shaded as a raised plate
  (or one flat grey) and dithered like a picture;
- ``word(font, p, region)``: text in a game font.
"""
from __future__ import annotations

import math
import struct

import numpy as np

W, H = 72, 40
BAYER = (0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5)


def _f32(x: float) -> float:
    return struct.unpack("f", struct.pack("f", x))[0]


def _round(x: float) -> int:          # JavaScript's Math.round
    return math.floor(x + 0.5)


class _A:
    """A w x h buffer of 32-bit floats, the page's arr()."""

    def __init__(self, w, h, fill=0.0):
        self.w, self.h, self.a = w, h, [_f32(fill)] * (w * h)


def _crop(m, x0, y0, x1, y1):
    o = _A(x1 - x0, y1 - y0)
    for y in range(y0, y1):
        o.a[(y - y0) * o.w:(y - y0 + 1) * o.w] = m.a[y * m.w + x0:y * m.w + x1]
    return o


def _bbox(m):
    x0, y0, x1, y1 = m.w, m.h, -1, -1
    for y in range(m.h):
        for x in range(m.w):
            if m.a[y * m.w + x] > 0.5:
                x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
    return None if x1 < 0 else (x0, y0, x1 + 1, y1 + 1)


def _mirror(m):
    o = _A(m.w, m.h)
    for y in range(m.h):
        o.a[y * m.w:(y + 1) * m.w] = m.a[y * m.w:(y + 1) * m.w][::-1]
    return o


def _resample(m, tw, th):
    """Area average, as the page's resample()."""
    o = _A(tw, th)
    sx, sy = m.w / tw, m.h / th
    for ty in range(th):
        for tx in range(tw):
            x0 = tx * sx
            x1 = x0 + sx
            y0 = ty * sy
            y1 = y0 + sy
            s = n = 0.0
            for y in range(math.floor(y0), math.ceil(y1)):
                wy = min(y + 1, y1) - max(y, y0)
                if wy <= 0:
                    continue
                for x in range(math.floor(x0), math.ceil(x1)):
                    wx = min(x + 1, x1) - max(x, x0)
                    if wx <= 0:
                        continue
                    s += m.a[min(y, m.h - 1) * m.w + min(x, m.w - 1)] * wx * wy
                    n += wx * wy
            o.a[ty * tw + tx] = _f32(s / n if n else 0.0)
    return o


def _gauss(m, sigma):
    r = math.ceil(sigma * 3)
    k = [math.exp(-i * i / (2 * sigma * sigma)) for i in range(-r, r + 1)]
    ks = 0.0
    for v in k:
        ks += v
    t, o = _A(m.w, m.h), _A(m.w, m.h)
    for y in range(m.h):
        for x in range(m.w):
            s = 0.0
            for i in range(-r, r + 1):
                s += k[i + r] * m.a[y * m.w + min(m.w - 1, max(0, x + i))]
            t.a[y * m.w + x] = _f32(s / ks)
    for y in range(m.h):
        for x in range(m.w):
            s = 0.0
            for i in range(-r, r + 1):
                s += k[i + r] * t.a[min(m.h - 1, max(0, y + i)) * m.w + x]
            o.a[y * m.w + x] = _f32(s / ks)
    return o


def _pct(vals, p):
    if not vals:
        return 0.0
    s = sorted(_f32(v) for v in vals)
    i = (len(s) - 1) * p / 100
    lo, hi = math.floor(i), math.ceil(i)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def _edge(a):
    o = _A(a.w, a.h)

    def out(x, y):
        return x < 0 or y < 0 or x >= a.w or y >= a.h or a.a[y * a.w + x] < 0.5
    for y in range(a.h):
        for x in range(a.w):
            if a.a[y * a.w + x] >= 0.5 and (out(x - 1, y) or out(x + 1, y) or out(x, y - 1) or out(x, y + 1)):
                o.a[y * a.w + x] = 1.0
    return o


def _kron(m, k):
    o = _A(m.w * k, m.h * k)
    for y in range(o.h):
        for x in range(o.w):
            o.a[y * o.w + x] = m.a[(y // k) * m.w + x // k]
    return o


def _grey(palette, i):
    return (0.299 * int(palette[i][0]) + 0.587 * int(palette[i][1]) + 0.114 * int(palette[i][2])) / 255


def _src_maps(idx, palette, p):
    h, w = idx.shape
    y0 = x0 = 0
    y1, x1 = h, w
    if p.get("crop"):
        y0, x0 = p["crop"]
        y1, x1 = h - y0, w - x0
    elif p.get("frame"):
        y0 = x0 = p["frame"]
        y1, x1 = h - y0, w - x0
    sub = idx[y0:y1, x0:x1]
    cw, ch = x1 - x0, y1 - y0
    flat = [int(v) for v in sub.reshape(-1)]
    g = _A(cw, ch)
    lut = [_f32(_grey(palette, i)) for i in range(256)]
    g.a = [lut[v] for v in flat]
    return flat, g, cw, ch


def _cut_cover(flat, w, h, cut):
    c = _A(w, h, 1.0)
    if not cut:
        return c
    cnt: dict = {}
    for x in range(w):
        for v in (flat[x], flat[(h - 1) * w + x]):
            cnt[v] = cnt.get(v, 0) + 1
    for y in range(h):
        for v in (flat[y * w], flat[y * w + w - 1]):
            cnt[v] = cnt.get(v, 0) + 1
    bg, best = 0, -1
    for v, n in cnt.items():            # first seen wins a tie, as the page's Map
        if n > best:
            best, bg = n, v
    c.a = [1.0 if v != bg else 0.0 for v in flat]
    o = _A(w, h)

    def nb(x, y):
        return 0 <= x < w and 0 <= y < h and c.a[y * w + x]
    for y in range(h):
        for x in range(w):
            if c.a[y * w + x] and (nb(x - 1, y) or nb(x + 1, y) or nb(x, y - 1) or nb(x, y + 1)):
                o.a[y * w + x] = 1.0
    return o if any(o.a) else _A(w, h, 1.0)


def dither_core(g, cov, p, region):
    """Fit, sharpen, stretch, dither inside a lit outline. `g` and `cov` are _A."""
    bb = _bbox(cov)
    if not bb:
        return _A(1, 1)
    g, cov = _crop(g, *bb), _crop(cov, *bb)
    if p.get("mirror"):
        g, cov = _mirror(g), _mirror(cov)
    s = min(region[0] / g.w, region[1] / g.h)
    tw, th = max(1, _round(g.w * s)), max(1, _round(g.h * s))
    gr = _resample(g, tw, th)
    a = _resample(cov, tw, th)
    a.a = [1.0 if v > 0.5 else 0.0 for v in a.a]
    if p.get("sharpen", 0) > 0:
        b = _gauss(gr, 1.5)
        gr.a = [_f32(min(1, max(0, v + p["sharpen"] * (v - bv)))) for v, bv in zip(gr.a, b.a)]
    inside = [gr.a[i] for i in range(len(a.a)) if a.a[i]]
    lo, hi = _pct(inside, p["lo"]), _pct(inside, p["hi"])
    k = 1 + 4 * p["curve"]
    nk = 2 * math.tanh(0.5 * k)
    out = _edge(a) if p.get("outline") else _A(tw, th)
    v = [0.0] * (tw * th)
    for i in range(tw * th):
        if not a.a[i] or out.a[i]:
            continue
        x = min(1, max(0, (gr.a[i] - lo) / max(hi - lo, 1e-6))) ** p["gamma"]
        if p["curve"]:
            x = 0.5 + math.tanh((x - 0.5) * k) / nk
        v[i] = _f32(p["floor"] + (1 - p["floor"]) * x)
    res = _A(tw, th)
    mode = p.get("mode", "levels")
    if mode == "fs":
        e = list(v)
        for y in range(th):
            for x in range(tw):
                i = y * tw + x
                on = 1 if e[i] >= 0.5 else 0
                err = e[i] - on
                res.a[i] = float(on)
                if x + 1 < tw:
                    e[i + 1] = _f32(e[i + 1] + err * 7 / 16)
                if y + 1 < th:
                    if x > 0:
                        e[i + tw - 1] = _f32(e[i + tw - 1] + err * 3 / 16)
                    e[i + tw] = _f32(e[i + tw] + err * 5 / 16)
                    if x + 1 < tw:
                        e[i + tw + 1] = _f32(e[i + tw + 1] + err / 16)
    else:
        thr = p.get("thr", 0.5)
        for y in range(th):
            for x in range(tw):
                i = y * tw + x
                q = v[i]
                if mode == "levels":
                    on = q > 2 / 3 or (q > 1 / 3 and (x + y) % 2 == 0)
                elif mode == "bayer":
                    on = q > BAYER[(y % 4) * 4 + x % 4] / 16 + 1 / 32
                elif mode == "threshold":
                    on = q > thr
                else:
                    raise ValueError(f"unknown dither mode {mode!r}")
                res.a[i] = 1.0 if on else 0.0
    for i in range(tw * th):
        if out.a[i]:
            res.a[i] = 1.0
        if not a.a[i]:
            res.a[i] = 0.0
    return res


def _render_pixel(flat, g, w, h, p, region):
    m = _A(w, h)
    nz = [g.a[i] for i in range(w * h) if flat[i]]
    lit = p.get("lit", "edge+bright")
    if lit == "nonzero":
        m.a = [1.0 if v else 0.0 for v in flat]
    elif lit == "centre":
        c = flat[(h // 2) * w + w // 2]
        m.a = [1.0 if v == c else 0.0 for v in flat]
    elif lit in ("darker", "brighter"):
        t = _pct(nz, p.get("pct", 50))
        m.a = [1.0 if flat[i] and (g.a[i] < t if lit == "darker" else g.a[i] > t) else 0.0 for i in range(w * h)]
    elif lit == "edge+bright":
        cov = _A(w, h)
        cov.a = [1.0 if v else 0.0 for v in flat]
        e, t = _edge(cov), _pct(nz, p.get("pct", 50))
        m.a = [1.0 if e.a[i] or (cov.a[i] and g.a[i] > t) else 0.0 for i in range(w * h)]
    else:
        raise ValueError(f"unknown lit rule {lit!r}")
    bb = _bbox(m)
    if not bb:
        return _A(1, 1)
    m = _crop(m, *bb)
    if p.get("mirror"):
        m = _mirror(m)
    if p.get("smooth_w"):
        tw = min(p["smooth_w"], region[0])
        th = max(1, _round(m.h * tw / m.w))
        r = _resample(m, tw, th)
        r.a = [1.0 if v > 0.43 else 0.0 for v in r.a]
        return r
    k = p["scale"] if p.get("scale", 0) > 0 else max(1, min(region[0] // m.w, region[1] // m.h))
    return _kron(m, k)


def _place(m, region, valign, word=False) -> np.ndarray:
    """`m` in a region-sized mask, right-aligned, as the page's place()."""
    bw, bh = min(region[0], W), min(region[1], H)
    out = np.zeros((bh, bw), bool)
    w, h = min(m.w, bw), min(m.h, bh)
    oy = bh - h - (1 if word else 0) if valign == "bottom" else (bh - h) // 2 if valign == "centre" else 0
    ox = bw - w
    for y in range(h):
        for x in range(w):
            if m.a[y * m.w + (m.w - w) + x] > 0.5:
                out[oy + y, ox + x] = True
    return out


def picture(idx: np.ndarray, palette, p: dict, region) -> np.ndarray:
    """A palette-index image drawn by p["engine"] and placed in `region`."""
    flat, g, w, h = _src_maps(idx, palette, p)
    if p.get("engine", "dither") == "pixel":
        m = _render_pixel(flat, g, w, h, p, region)
    else:
        m = dither_core(g, _cut_cover(flat, w, h, p.get("cut", True)), p, region)
    return _place(m, region, p.get("valign", "top"))


def _mulberry(seed: int):
    """The page's seeded(): mulberry32 and a Box-Muller normal."""
    t = seed & 0xFFFFFFFF

    def imul(a, b):
        r = (a * b) & 0xFFFFFFFF
        return r - 0x100000000 if r & 0x80000000 else r

    def u():
        nonlocal t
        t = (t + 0x6D2B79F5) & 0xFFFFFFFF
        r = imul((t ^ (t >> 15)) & 0xFFFFFFFF, (1 | t) & 0xFFFFFFFF) & 0xFFFFFFFF
        r = (r ^ ((r + (imul((r ^ (r >> 7)) & 0xFFFFFFFF, (61 | r) & 0xFFFFFFFF) & 0xFFFFFFFF)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((r ^ (r >> 14)) & 0xFFFFFFFF) / 4294967296

    def normal():
        a = u()
        b = u()
        return math.sqrt(-2 * math.log(a + 1e-12)) * math.cos(2 * math.pi * b)
    return normal


def relief(cov, p):
    """A port of cnc_remastered/fetch_icons.py relief(), as the page draws it."""
    w, h = cov.w, cov.h
    r = max(2, _round(p["depth"] * min(w, h)))
    dist = [0.0] * (w * h)
    m = [1 if v > 0.5 else 0 for v in cov.a]
    for _ in range(r):
        nm = [0] * (w * h)
        for y in range(h):
            for x in range(w):
                i = y * w + x
                dist[i] += m[i]
                nm[i] = 1 if (m[i] and 0 < x < w - 1 and 0 < y < h - 1 and m[i - 1] and m[i + 1]
                              and m[i - w] and m[i + w]) else 0
        m = nm
    az, el = p["azimuth"] * math.pi / 180, p["elevation"] * math.pi / 180
    L = (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))
    rnd = _mulberry(p["seed"])
    row = [_f32(rnd() * 0.08) for _ in range(h)]
    g = _A(w, h)

    def hh(i):
        return _f32(dist[i]) / r
    for y in range(h):
        for x in range(w):
            i = y * w + x
            grain = (row[y] + rnd() * 0.05) * p["grain"]
            if cov.a[i] < 0.5:
                continue
            gx = hh(i + 1) - hh(i) if x == 0 else hh(i) - hh(i - 1) if x == w - 1 else (hh(i + 1) - hh(i - 1)) / 2
            gy = hh(i + w) - hh(i) if y == 0 else hh(i) - hh(i - w) if y == h - 1 else (hh(i + w) - hh(i - w)) / 2
            nx, ny, nz = -gx * r, -gy * r, 1.0
            nl = math.hypot(nx, ny, nz)
            nx, ny, nz = nx / nl, ny / nl, nz / nl
            shade = p["ambient"] + (1 - p["ambient"]) * min(1, max(0, nx * L[0] + ny * L[1] + nz * L[2]))
            fall = p["falloff"] * (x / w + y / h) / 2
            g.a[i] = _f32(min(1, max(0, shade - fall + grain)))
    return g


def vector(alpha: np.ndarray, p: dict, region) -> np.ndarray:
    """An icon silhouette (alpha 0..255), shaded and dithered, placed in `region`."""
    h, w = alpha.shape
    cov = _A(w, h)
    cov.a = [1.0 if v > 127 else 0.0 for v in alpha.reshape(-1)]
    if p.get("relief", True):
        g = relief(cov, p)
    else:
        g = _A(w, h)
        g.a = [_f32(p["flat"]) if c else 0.0 for c in cov.a]
    return _place(dither_core(g, cov, p, region), region, p.get("valign", "top"))


def word(font, p: dict, region) -> np.ndarray:
    """`p["text"]` in `font` (height, {code: glyph of 0..3}), placed in `region`
    with 1 px under it, as the page places a word."""
    fh, chars = font
    parts = [chars[ord(c)] for c in str(p["text"]) if ord(c) in chars and chars[ord(c)].shape[1]]
    gap = p.get("gap", 1)
    if not parts:
        return np.zeros((min(region[1], H), min(region[0], W)), bool)
    m = _A(max(1, sum(g.shape[1] + gap for g in parts) - gap), fh)
    x0 = 0
    lit = {1: p.get("body", True), 2: p.get("shade", False), 3: p.get("outline", False)}
    for g in parts:
        for y in range(fh):
            for x in range(g.shape[1]):
                if lit.get(int(g[y, x])):
                    m.a[y * m.w + x0 + x] = 1.0
        x0 += g.shape[1] + gap
    bb = _bbox(m)
    if bb:
        m = _crop(m, *bb)
    if p.get("scale", 1) > 1:
        m = _kron(m, p["scale"])
    return _place(m, region, p.get("valign", "bottom"), word=True)
