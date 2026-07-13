#!/usr/bin/env python3
"""Faithful Python port of the firmware Eden boot animation.

This is NOT a design mock — it re-implements ``sa_render_frame`` from
``qmk_firmware/keyboards/polykybd/anim/startup_anim.c`` with the SAME fixed-point
integer semantics, reading the SAME generated tables
(``startup_anim_geom.h``: SA_SIN, SA_NOISE, SA_GEOM_*, SA_TARGETS, SA_LETTER_*)
and the SAME tuning ``#define``s (SA_INTRO_MS, SA_RING_FREQ, …). So a frame it
produces is what the hardware actually draws, and the GIF is a real cross-check
of the firmware rather than a separate effect.

Each ``panel(half, disp_idx, elapsed_ms)`` returns the 72x40 boolean the firmware
writes into its per-keycap scratch buffer (the key's LOCAL pixel frame, BEFORE the
physical panel rotation). The demo blits that through the KLE renderer, which
applies the physical key rotation for placement — matching hardware, where the
firmware pre-rotates the content and the panel is physically rotated.
"""
from __future__ import annotations

import os
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
WORKSPACE = os.path.dirname(HOST_REPO)
QMK_ANIM = os.path.join(WORKSPACE, "qmk_firmware", "keyboards", "polykybd", "anim")
SPLASH_FONT = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"

SCREEN_W, SCREEN_H = 72, 40


def _defines(text):
    """All ``#define NAME <int>`` pairs in a C source string."""
    out = {}
    for m in re.finditer(r"#define\s+(\w+)\s+(-?\d+)\b", text):
        out[m.group(1)] = int(m.group(2))
    return out


def _int_list(text, name):
    """Flatten the ``{...}`` initializer of ``name`` into a list of ints (accepts
    nested braces and 0x.. hex, e.g. the geom struct rows or SA_SIN)."""
    m = re.search(re.escape(name) + r"\s*\[[^\]]*\]\s*=\s*\{(.*?)\n\};", text, re.S)
    if not m:
        raise ValueError(f"array {name} not found")
    body = m.group(1)
    return [int(tok, 0) for tok in re.findall(r"-?0x[0-9a-fA-F]+|-?\d+", body)]


class FwSim:
    def __init__(self, anim_c=None, geom_h=None):
        anim_c = anim_c or os.path.join(QMK_ANIM, "startup_anim.c")
        geom_h = geom_h or os.path.join(QMK_ANIM, "startup_anim_geom.h")
        c = open(anim_c, encoding="utf-8").read()
        h = open(geom_h, encoding="utf-8").read()
        d = _defines(c)
        d.update(_defines(h))          # geom header defines (BOARD_W/H, NOISE_MASK, …)
        self.d = d
        self.INTRO = d["SA_INTRO_MS"]; self.HOLD = d["SA_HOLD_MS"]; self.FADE = d["SA_FADE_MS"]
        self.TOTAL = self.INTRO + self.HOLD + self.FADE
        self.PGAIN = d["SA_PGAIN"]
        self.NSPARK = d["SA_NSPARK"]; self.TRAIL = d["SA_TRAIL"]; self.TRAILSTEP = d["SA_TRAILSTEP"]
        self.RFREQ = d["SA_RING_FREQ"]
        self.RANUM = d["SA_RING_ANUM"]; self.RADEN = d["SA_RING_ADEN"]
        self.BW = d["SA_BOARD_W"]; self.BH = d["SA_BOARD_H"]
        self.SIN = np.array(_int_list(h, "SA_SIN"), np.int64)
        self.NOISE = np.array(_int_list(h, "SA_NOISE"), np.int64)
        geomL = _int_list(h, "SA_GEOM_LEFT"); geomR = _int_list(h, "SA_GEOM_RIGHT")
        self.GEOM = {"L": np.array(geomL, np.int64).reshape(-1, 4),
                     "R": np.array(geomR, np.int64).reshape(-1, 4)}   # rows: cx,cy,ang,valid
        self.LETTER = {"L": _int_list(h, "SA_LETTER_LEFT"), "R": _int_list(h, "SA_LETTER_RIGHT")}
        tgt = _int_list(h, "SA_TARGETS")
        self.TARGETS = np.array(tgt, np.int64).reshape(-1, 3)        # rows: cx,cy,cp
        self.cxr = self.BW // 2
        self.cyr = self.BH * 42 // 100
        # local pixel grids (ly rows, lx cols)
        self.ly = np.arange(SCREEN_H, dtype=np.int64)[:, None]
        self.lx = np.arange(SCREEN_W, dtype=np.int64)[None, :]
        self._letter_cache = {}
        self._spark_cache = {}

    # ---- exact integer helpers -------------------------------------------
    def _sin(self, t):                       # sa_sin(uint8 t)
        return self.SIN[t & 0xFF]

    def _noise(self, x, y):                  # sa_noise: NOISE[((y&31)<<5)|(x&31)]
        return self.NOISE[((y & 31) << 5) | (x & 31)]

    @staticmethod
    def _isqrt(v):
        """Vectorized bit-exact port of the C sa_isqrt (b seeded at 1<<20). Starting
        every element at 4^10 and running 11 fixed iterations gives the same floor(sqrt)
        as the C reduce-first loop — the leading b>v iterations are no-ops."""
        v = v.astype(np.int64).copy()
        r = np.zeros_like(v)
        b = np.full_like(v, 1 << 20)
        for _ in range(11):                  # 4^10 .. 4^0
            t = r + b
            r = r >> 1
            ge = v >= t
            v = np.where(ge, v - t, v)
            r = np.where(ge, r + b, r)
            b = b >> 2
        return r

    def _dist(self, a, b):                    # sa_dist = isqrt(a*a + b*b)
        return self._isqrt(a * a + b * b)

    def _plasma(self, gx, gy, tp):           # sa_plasma
        a = self._sin(((gx * 3) >> 2) + tp)      # (uint8)((gx*3)>>2) + tp, then sa_sin
        b = self._sin((gy & 0xFF) - tp)
        c = self._sin(((gx + gy) >> 1) + tp)
        return (a + b + c) // 3                  # uint8

    @staticmethod
    def _hash8(v):                           # sa_hash8(uint32) -> uint8 (scalar)
        v &= 0xFFFFFFFF
        v ^= v >> 15; v = (v * 0x2c1b3c6d) & 0xFFFFFFFF
        v ^= v >> 12; v = (v * 0x297a2d39) & 0xFFFFFFFF
        v ^= v >> 15
        return v & 0xFF

    # ---- timeline (mirrors sa_render_frame head) -------------------------
    def _timeline(self, el):
        tt = (el * 256) // self.INTRO if el < self.INTRO else 255
        tp = (el >> 4) & 0xFF
        tprg = (el >> 5) & 0xFF
        cvi = (tt - 110) * 255 // 75
        cv = 0 if cvi < 0 else (255 if cvi > 255 else cvi)
        ring = 255 - cv
        letters = tt >= 150
        sparks = (el < self.INTRO) and (tt < 220)
        fade = 0
        if el >= self.INTRO + self.HOLD:
            f = ((el - self.INTRO - self.HOLD) * 256) // self.FADE
            fade = 255 if f > 255 else f
        return dict(tt=tt, tp=tp, tprg=tprg, cv=cv, ring=ring,
                    letters=letters, sparks=sparks, fade=fade)

    def _letter_bmp(self, cp):
        """Rasterize a splash codepoint the way FreeSansBold24pt7b does on the
        keycap (centred, ~34 px cap height). Approximate but visually faithful."""
        if cp in self._letter_cache:
            return self._letter_cache[cp]
        img = Image.new("L", (SCREEN_W, SCREEN_H), 0)
        d = ImageDraw.Draw(img)
        f = ImageFont.truetype(SPLASH_FONT, 40)
        ch = chr(cp)
        bb = d.textbbox((0, 0), ch, font=f)
        w, hh = bb[2] - bb[0], bb[3] - bb[1]
        d.text(((SCREEN_W - w) / 2 - bb[0], (SCREEN_H - hh) / 2 - bb[1]), ch, fill=255, font=f)
        m = (np.asarray(img) > 127)
        self._letter_cache[cp] = m
        return m

    # ---- one keycap's 72x40 local buffer ---------------------------------
    def panel(self, half, idx, el):
        g = self.GEOM[half][idx]
        cx, cy, ang, valid = int(g[0]), int(g[1]), int(g[2]), int(g[3])
        if not valid:
            return None
        T = self._timeline(el)
        rot = ang != 0
        cosv = int(self._sin((ang + 64) & 0xFF)) - 128
        sinv = int(self._sin(ang)) - 128

        dx = self.lx - 36
        dy = self.ly - 20
        if rot:
            gx = cx + ((dx * cosv - dy * sinv) >> 7)
            gy = cy + ((dx * sinv + dy * cosv) >> 7)
        else:
            gx = cx + dx * np.ones_like(dy)
            gy = cy + dy * np.ones_like(dx)
        gx = gx.astype(np.int64); gy = gy.astype(np.int64)

        pv = self._plasma(gx, gy, T["tp"])
        bit = ((pv >> 4) > self._noise(gx, gy))
        if T["ring"]:
            ax = np.trunc((gx - self.cxr) * self.RANUM / self.RADEN).astype(np.int64)
            ay = gy - self.cyr
            rr = self._dist(ax, ay)          # true isqrt (round rings near centre)
            rv = self._sin((((rr * self.RFREQ) >> 8) - T["tprg"]) & 0xFF)
            crest = np.where(rv > 128, rv - 128, 0)                # upper half → rings (≤~50%)
            dens = (crest * T["ring"]) >> 8                        # fade with envelope
            ring_hit = self._noise(gx + 50, gy + 30) < dens
            bit = bit | ring_hit

        if T["sparks"]:
            self._place_sparks(bit, cx, cy, rot, cosv, sinv, el)

        if T["letters"]:
            cp = self.LETTER[half][idx]
            if cp:
                bit = bit | self._letter_bmp(cp)

        if T["fade"]:
            # sa_noise(lx+idx*13, ly+idx*7) < fade  -> clear
            nx = self.lx + idx * 13
            ny = self.ly + idx * 7
            keep = self._noise(nx, ny) >= T["fade"]
            bit = bit & keep
        return bit

    def _spark_points(self, el):
        """All (sx, sy, is_head) spark/trail board positions for this frame — key
        independent, so compute once per el and cache. Exact port of sa_sparks minus
        the per-key placement."""
        if el in self._spark_cache:
            return self._spark_cache[el]
        cv = self._timeline(el)["cv"]
        margin = self.BW // 8
        BW = self.BW
        sxs, sys, heads = [], [], []
        for s in range(self.NSPARK):
            p0 = self._hash8(s * 2 + 1)
            spd = 1 + (self._hash8(s * 7 + 3) & 3)
            lane = (self._hash8(s * 5 + 9) * self.BH) >> 8
            bw = 1 + (self._hash8(s * 11 + 2) & 3)
            ph = self._hash8(s * 13 + 5)
            bob = 6 + (self._hash8(s * 17) & 31)
            tcx, tcy, _ = self.TARGETS[s % len(self.TARGETS)]
            for j in range(self.TRAIL):
                if self._hash8(s * 31 + j) > ((255 - j * (200 // self.TRAIL)) & 0xFF):
                    continue
                xn = (p0 + ((el >> 4) * spd & 0xFF) - j * self.TRAILSTEP) & 0xFF
                sx = -margin + ((xn * (BW + 2 * margin)) >> 8)
                sy = lane + (((int(self._sin(((el >> 5) * bw + ph) & 0xFF)) - 128) * bob) >> 7)
                if cv:
                    sx = sx + (((int(tcx) - sx) * cv) >> 8)
                    sy = sy + (((int(tcy) - sy) * cv) >> 8)
                sxs.append(sx); sys.append(sy); heads.append(j == 0)
        pts = (np.array(sxs, np.int64), np.array(sys, np.int64), np.array(heads, bool))
        self._spark_cache[el] = pts
        return pts

    def _place_sparks(self, bit, cx, cy, rot, cosv, sinv, el):
        sx, sy, head = self._spark_points(el)
        if sx.size == 0:
            return
        ddx = sx - cx
        ddy = sy - cy
        on = (ddx > -40) & (ddx < 40) & (ddy > -40) & (ddy < 40)
        if not on.any():
            return
        ddx, ddy, head = ddx[on], ddy[on], head[on]
        if rot:
            px = 36 + ((ddx * cosv + ddy * sinv) >> 7)
            py = 20 + ((-ddx * sinv + ddy * cosv) >> 7)
        else:
            px = 36 + ddx
            py = 20 + ddy
        self._plot(bit, px, py)
        self._plot(bit, px[head] + 1, py[head])   # brighter head

    @staticmethod
    def _plot(bit, px, py):
        ok = (px >= 0) & (px < SCREEN_W) & (py >= 0) & (py < SCREEN_H)
        bit[py[ok], px[ok]] = True


# disp_idx (0..39) = disp_row*8 + disp_col; mp mapping mirrors _disp_mp in the demo.
def disp_mp(left, dr, dc):
    mr = dr if left else dr + 5
    mc = dc if left else (dc + 1 if dr < 4 else dc)
    return f"{mr},{mc}"


def mp_to_half_idx():
    """{matrix 'r,c' -> ('L'|'R', disp_idx)} for every displayed key."""
    out = {}
    for left in (True, False):
        for dr in range(5):
            for dc in range(8):
                out[disp_mp(left, dr, dc)] = ("L" if left else "R", dr * 8 + dc)
    return out


if __name__ == "__main__":       # quick self-test: print a mid-intro panel's lit-count
    sim = FwSim()
    p = sim.panel("L", 9, sim.INTRO // 3)
    print("panel L#9 @intro/3:", None if p is None else int(p.sum()), "lit px",
          "| total ms", sim.TOTAL)
