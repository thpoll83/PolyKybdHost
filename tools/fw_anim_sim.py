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
    """All ``#define NAME <int>`` pairs in a C source string, plus simple alias
    defines (``#define NAME OTHER`` where OTHER is an already-defined int — e.g.
    ``#define SA_BG_FADE_START_MS SA_INTRO_MS``)."""
    out = {}
    for m in re.finditer(r"#define\s+(\w+)\s+(-?\d+)\b", text):
        out[m.group(1)] = int(m.group(2))
    for m in re.finditer(r"#define\s+(\w+)\s+(\w+)\s*(?://.*)?$", text, re.M):
        name, val = m.group(1), m.group(2)
        if name not in out and val in out:
            out[name] = out[val]
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
        self.BG_FADE = d["SA_BG_FADE_MS"]; self.BG_FADE_START = d["SA_BG_FADE_START_MS"]
        # scanline glitch fires 1 s after the background has fully faded (SA_LINE_CLEAR_AT_MS
        # is a macro expression, so compute it from its parts here)
        self.LINE_CLEAR_AT = self.BG_FADE_START + self.BG_FADE + d["SA_LINE_CLEAR_DELAY_MS"]
        self.BLACK = d["SA_BLACK_MS"]
        self.TOTAL = self.INTRO + self.HOLD + self.FADE + self.BLACK
        self.PGAIN = d["SA_PGAIN"]
        self.NSPARK = d["SA_NSPARK"]; self.TRAIL_MAX = d["SA_TRAIL_MAX"]
        self.RFREQ = d["SA_RING_FREQ"]; self.RASPECT = d["SA_RING_ASPECT"]
        self.NMASK = d["SA_NOISE_MASK"]                     # 63 → 64px tile
        self.NSHIFT = (self.NMASK + 1).bit_length() - 1    # 6 for a 64-wide row
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
        # When True, panel()/_timeline() render the IDLE screensaver look instead of
        # the boot sequence: the intro's opening comet field held open forever — cv
        # forced 0 (no converge), no letters, no bg/letter fade, no scanline, no black
        # tail. Mirrors sa_render_idle_frame() in startup_anim.c. `el` just advances.
        self.idle = False

    # ---- exact integer helpers -------------------------------------------
    def _sin(self, t):                       # sa_sin(uint8 t)
        return self.SIN[t & 0xFF]

    def _noise(self, x, y):                  # sa_noise: NOISE[((y&M)<<S)|(x&M)]
        return self.NOISE[((y & self.NMASK) << self.NSHIFT) | (x & self.NMASK)]

    @staticmethod
    def _dist(a, b):                          # sa_dist: octagonal (mx*123 + mn*51) >> 7
        a = np.abs(a); b = np.abs(b)
        mx = np.maximum(a, b); mn = np.minimum(a, b)
        return (mx * 123 + mn * 51) >> 7

    def _plasma(self, gx, gy, tp):           # sa_plasma
        a = self._sin(((gx * 3) >> 2) + tp)      # (uint8)((gx*3)>>2) + tp, then sa_sin
        b = self._sin((gy & 0xFF) - tp)
        c = self._sin(((gx + gy) >> 1) + tp)
        return ((a + b + c) * 85) >> 8           # /3 as *85>>8 (no divide)

    def _bg(self, gx, gy, T):                    # sa_bg: combined plasma+ring density (0..255)
        pv = self._plasma(gx, gy, T["tp"])
        dens = (pv * T["pgain"]) >> 8            # faint plasma haze
        if T["ring"]:
            ax = ((gx - self.cxr) * self.RASPECT) >> 8
            ay = gy - self.cyr
            rr = self._dist(ax, ay).astype(np.int64)
            rr = rr + ((self._sin((gx + 2 * gy) & 0xFF) - 128) >> 3)   # irregular radius wobble
            rv = self._sin((((rr * self.RFREQ) >> 8) - T["tprg"]) & 0xFF)
            thr = 200 if self.idle else 215   # idle: thicker/denser rings
            crest = np.where(rv > thr, rv - thr, 0)
            rdens = (crest * T["ring"]) >> 9
            dens = np.maximum(dens, rdens)
        return dens

    @staticmethod
    def _hash8(v):                           # sa_hash8(uint32) -> uint8 (scalar)
        v &= 0xFFFFFFFF
        v ^= v >> 15; v = (v * 0x2c1b3c6d) & 0xFFFFFFFF
        v ^= v >> 12; v = (v * 0x297a2d39) & 0xFFFFFFFF
        v ^= v >> 15
        return v & 0xFF

    # ---- timeline (mirrors sa_render_frame head) -------------------------
    def _timeline(self, el):
        tp = (el >> 4) & 0xFF
        tprg = (el >> 5) & 0xFF
        if self.idle:
            # Idle screensaver: perpetual comet field (sa_render_idle_frame).
            return dict(tt=0, tp=tp, tprg=tprg, cv=0, ring=255, letters=False,
                        sparks=True, spark_fade=0, letter_in=255,
                        bg_fade=0, letter_fade=0, pgain=self.PGAIN)
        tt = (el * 256) // self.INTRO if el < self.INTRO else 255
        cvi = (tt - 55) * 255 // 75           # converge earlier (tt 55..130): gather into letter zones before they appear
        cv = 0 if cvi < 0 else (255 if cvi > 255 else cvi)
        ring = 255 - cv
        letters = tt >= 130
        sparks = el < self.INTRO
        sfi = (tt - 130) * 255 // 125
        spark_fade = 0 if sfi < 0 else (255 if sfi > 255 else sfi)
        lii = (tt - 130) * 255 // 35          # letters dither IN over tt 130..165 (reverse dissolve)
        letter_in = 0 if lii < 0 else (255 if lii > 255 else lii)
        bg_fade = 0; letter_fade = 0
        if el >= self.BG_FADE_START:          # background dots dissolve early (top of hold) + slow
            b = ((el - self.BG_FADE_START) * 256) // self.BG_FADE
            bg_fade = 255 if b > 255 else b
        if el >= self.INTRO + self.HOLD:       # letters dissolve over the full (slow) fade phase
            lf = ((el - self.INTRO - self.HOLD) * 256) // self.FADE
            letter_fade = 255 if lf > 255 else lf
        pgain = (self.PGAIN * (255 - bg_fade)) // 255
        return dict(tt=tt, tp=tp, tprg=tprg, cv=cv, ring=ring, letters=letters,
                    sparks=sparks, spark_fade=spark_fade, letter_in=letter_in,
                    bg_fade=bg_fade, letter_fade=letter_fade, pgain=pgain)

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
        if not self.idle and el >= self.INTRO + self.HOLD + self.FADE:   # black tail — all keycaps black
            return np.zeros((SCREEN_H, SCREEN_W), bool)
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

        # Background density (plasma haze + dissolved ring), 2x2-coarsened for non-rotated
        # keys (matches the firmware sa_bg + s_brow reuse); per-pixel noise keeps the dither.
        if rot:
            bgv = self._bg(gx, gy, T)
        else:
            gxc = cx + ((self.lx & ~1) - 36)         # sample sa_bg at the 2x2 block top-left
            gyc = cy + ((self.ly & ~1) - 20)
            bgv = self._bg(gxc.astype(np.int64), gyc.astype(np.int64), T)
        bit = bgv > self._noise(gx, gy)

        if T["sparks"]:
            self._place_sparks(bit, cx, cy, rot, cosv, sinv, el)

        if T["letters"]:
            cp = self.LETTER[half][idx]
            if cp:
                bit = bit | self._letter_bmp(cp)
                if T["letter_in"] < 255:   # dither the letters IN (reverse of the end dissolve)
                    nx = self.lx + idx * 13
                    ny = self.ly + idx * 7
                    bit = bit & (self._noise(nx, ny) < T["letter_in"])

        # Scanline glitch: after the letters hold SA_LINE_CLEAR_MS, wipe every 2nd line
        # (instant, re-applied each frame so it persists). Mirrors the firmware.
        if not self.idle and el >= self.LINE_CLEAR_AT:
            bit = bit.copy()
            bit[1::2, :] = False

        if T["letter_fade"]:   # dissolve the letters (only lit pixels left by now)
            nx = self.lx + idx * 13
            ny = self.ly + idx * 7
            keep = self._noise(nx, ny) >= T["letter_fade"]
            bit = bit & keep
        return bit

    def _spark_points(self, el):
        """Comet HEAD board positions for this frame (one per live spark) — key
        independent, so compute once per el and cache. Mirrors sa_build_sparks."""
        if el in self._spark_cache:
            return self._spark_cache[el]
        T = self._timeline(el)
        cv = T["cv"]; spark_fade = T["spark_fade"]
        margin = self.BW // 8
        BW = self.BW
        sxs, sys, thicks, tlens = [], [], [], []
        for s in range(self.NSPARK):
            if self._hash8(s * 3 + 7) < spark_fade:   # staggered death: winks out one by one
                continue
            if self.idle and self._hash8(s * 19 + 11) < 160:   # idle thins the field (~37% kept)
                continue
            p0 = self._hash8(s * 2 + 1)
            spd = 1 + (self._hash8(s * 7 + 3) & (15 if self.idle else 7))   # idle: wider 1..16 spread
            lane = (self._hash8(s * 5 + 9) * self.BH) >> 8
            bw = 1 + (self._hash8(s * 11 + 2) & 3)
            ph = self._hash8(s * 13 + 5)
            bob = 6 + (self._hash8(s * 17) & 31)
            hv = self._hash8(s * 23 + 4)              # per-spark look variety
            tcx, tcy, _ = self.TARGETS[s % len(self.TARGETS)]
            tsh = 6 if self.idle else 4              # idle comets crawl (2 extra el-shift bits)
            xn = (p0 + ((el >> tsh) * spd & 0xFF)) & 0xFF
            sx = -margin + ((xn * (BW + 2 * margin)) >> 8)
            sy = lane + (((int(self._sin(((el >> (tsh + 1)) * bw + ph) & 0xFF)) - 128) * bob) >> 7)
            if cv:
                sx = sx + (((int(tcx) - sx) * cv) >> 8)
                sy = sy + (((int(tcy) - sy) * cv) >> 8)
            sxs.append(sx); sys.append(sy)
            thicks.append(2 if (hv & 1) else 1)
            base_tlen = 8 + (hv >> 4)
            tlens.append(base_tlen + 28 if self.idle else base_tlen)   # idle: long ghost trails
        pts = (np.array(sxs, np.int64), np.array(sys, np.int64),
               np.array(thicks, np.int64), np.array(tlens, np.int64))
        self._spark_cache[el] = pts
        return pts

    def _place_sparks(self, bit, cx, cy, rot, cosv, sinv, el):
        sx, sy, thick, tlen = self._spark_points(el)
        if sx.size == 0:
            return
        LM = 60 if self.idle else self.TRAIL_MAX   # idle: draw the long ghost trails (firmware caps at tlen)
        ddx = sx - cx
        ddy = sy - cy
        on = (ddx > -(40 + LM)) & (ddx < 40 + LM) & (ddy > -40) & (ddy < 40)
        if not on.any():
            return
        ddx, ddy, thick, tlen = ddx[on], ddy[on], thick[on], tlen[on]
        if rot:
            hx = 36 + ((ddx * cosv + ddy * sinv) >> 7)
            hy = 20 + ((-ddx * sinv + ddy * cosv) >> 7)
        else:
            hx = 36 + ddx
            hy = 20 + ddy
        th = thick == 2
        self._plot(bit, hx, hy)                        # bold 2×2 head
        self._plot(bit, hx + 1, hy)
        self._plot(bit, hx, hy + 1)
        self._plot(bit, hx + 1, hy + 1)
        self._plot(bit, hx[th], hy[th] - 1)            # taller/brighter head for thick comets
        self._plot(bit, hx[th] + 1, hy[th] - 1)
        for k in range(1, LM):                         # solid neck, then a fading tail
            live = tlen > k                            # only comets whose trail reaches k
            if not live.any():
                continue
            if k <= 5:
                draw = live
            else:
                draw = live & (self._noise(hx - k + 30, hy + 12) < ((255 - k * (230 // tlen)) & 0xFF))
            self._plot(bit, (hx - k)[draw], hy[draw])
            th2 = draw & th
            self._plot(bit, (hx - k)[th2], hy[th2] + 1)   # 2 px tall trail

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
