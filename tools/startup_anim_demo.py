#!/usr/bin/env python3
"""Preview the proposed split72 boot / idle demoscene animation as a GIF.

Unlike a hand-rolled layout, this drives the SAME ``kle_render.KleRenderer`` the
other demos use, so the key geometry (including the rotated thumb cluster and the
exact OLED rectangle inside each keycap) is the editor's real geometry — the
displays land where they actually are on the board.

The effect (sparkle dust -> converge -> splash letters dither-dissolve in over a
faint plasma; idle = the same minus letters, slower) is procedural and sampled in
the renderer's real board pixel space, so sparkles/plasma flow continuously across
keycaps and each key's panel is rotated/placed exactly as the renderer draws it.

Boot letters are placed on the logical display grid like show_splash_screen:
left POLY / KYBD, right SPLIT / 7 2.

Usage:
    python tools/startup_anim_demo.py --mode boot --out out/boot_anim.gif
    python tools/startup_anim_demo.py --mode idle --out out/idle_anim.gif

Design mock only (numpy/floats). The firmware port would be fixed-point
(sin8/cos8) + the same 4x4 Bayer dither.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from kle_render import KleRenderer, KeyContent, Theme, OLED_W, OLED_H

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
DEFAULT_KLE = os.path.join(HOST_REPO, "polyhost", "res", "polykybd-split72.json")
ENCODERS = {"3,7", "8,0"}          # left & right rotary encoders: no display
FONT = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"

# 4x4 ordered Bayer matrix, normalized to (0,1) -- the same one the firmware
# blitter (doom_blit.c) uses; ordered dither is stable frame-to-frame on mono.
TAU = 2.0 * np.pi     # exact, so integer-rate idle motions loop with no seam
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                   [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16.0
BAY = np.tile(BAYER4, (OLED_H // 4 + 1, OLED_W // 4 + 1))[:OLED_H, :OLED_W]

# ---- splash letters on the logical display grid (like show_splash_screen) ----
# disp(dr,dc) -> matrix(mr,mc): left = (dr,dc); right rows 5..8 add the c-- fold.
def _disp_mp(left, dr, dc):
    mr = dr if left else dr + 5
    mc = dc if left else (dc + 1 if dr < 4 else dc)
    return f"{mr},{mc}"


def splash_targets():
    tg = {}
    plan = [(True, 1, 1, "POLY"), (True, 2, 1, "KYBD"),
            (False, 1, 1, "SPLIT"), (False, 3, 1, " 7 2")]
    for left, dr, col, msg in plan:
        for k, ch in enumerate(msg):
            if ch != " ":
                tg[_disp_mp(left, dr, col + k)] = ch
    return tg


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def key_board_geom(r: KleRenderer):
    """For every real key return the board-space mapping of its native 72x40 OLED:
    center (cx,cy) and the per-native-pixel board vectors (ux,uy),(vx,vy) -- these
    already include the key's rotation, replicated from KleRenderer._key_tile."""
    U = r.unit
    pad = r.key_pad
    geom = {}
    for mp, p in r.km.items():
        if mp in r.exclude:
            continue
        c = r._corners_px(p)                      # rotated board corners (pre ox/oy)
        c0 = np.array(c[0], float)
        ex = (np.array(c[1], float) - c0) / (p['w'] * U)   # board vec / key-x px
        ey = (np.array(c[3], float) - c0) / (p['h'] * U)   # board vec / key-y px
        tw, th = p['w'] * U, p['h'] * U
        kw = tw - 2 * pad - 1
        kh = th - 2 * pad - 1
        m = max(3, U // 16)
        disp_w = max(2, kh - 2 * m)
        disp_h = int(disp_w * (OLED_H / OLED_W))
        dx = pad + m + (kw - kh) / 2
        dy = pad + m
        origin = c0 + ex * dx + ey * dy - np.array([r.ox, r.oy], float)
        ux = ex * (disp_w / OLED_W)
        uy = ey * (disp_h / OLED_H)
        cx, cy = origin + ux * (OLED_W / 2) + uy * (OLED_H / 2)
        geom[mp] = dict(cx=cx, cy=cy, ux=ux[0], uy=ux[1], vx=uy[0], vy=uy[1])
    return geom


class ImgRenderer(KleRenderer):
    """KleRenderer that lets a driver inject a binary 72x40 OLED image per key."""
    inject: dict

    def _oled_buffer(self, c):
        img = getattr(c, "oled", None)
        if img is None:
            return super()._oled_buffer(c)
        one = img.convert("1")
        rgb = Image.new("RGB", (OLED_W, OLED_H), self.theme.oled_bg)
        rgb.paste(Image.new("RGB", (OLED_W, OLED_H), self.theme.oled_on), (0, 0), one)
        return rgb


def hash2(x, y):
    """Static white-noise threshold in [0,1) from a per-pixel hash. Maximally
    *irregular* (no grid, no diagonal banding like Bayer/IGN) yet a pure function
    of board position, so it doesn't crawl between frames -- the plasma value
    animating across this fixed field is what makes the texture shimmer."""
    v = np.sin(x * 12.9898 + y * 78.233) * 43758.5453
    return v - np.floor(v)


class Effect:
    """Sparks stream left->right (each with a fading trail), then converge into
    the splash letters. State is procedural (a pure function of time)."""

    def __init__(self, geom, targets, board_wh, mode="boot", seed=1234):
        self.geom = geom
        self.mode = mode
        self.W, self.H = board_wh
        rng = np.random.default_rng(seed)
        n = 700 if mode == "boot" else 300
        self.n = n
        # Idle must be a SEAMLESS LOOP, so every motion has to be periodic over
        # tt in [0,1): integer flow/wander/twinkle rates and integer global speeds
        # mean state(tt=1) == state(tt=0). Boot plays once, so it stays continuous.
        self.loop = (mode != "boot")
        self.p0 = rng.uniform(0.0, 1.0, n).astype(np.float32)        # flow phase
        self.lane = (rng.uniform(-0.05, 1.05, n) * self.H).astype(np.float32)
        self.bob = rng.uniform(6, 30, n).astype(np.float32)          # vertical wander amp
        self.ph = rng.uniform(0, TAU, n).astype(np.float32)
        if self.loop:
            self.speed = rng.integers(1, 4, n).astype(np.float32)    # {1,2,3} cycles/loop
            self.bw = rng.integers(1, 4, n).astype(np.float32)
            self.tw = rng.integers(2, 6, n).astype(np.float32)
            self.bg_speed = 2.0
            self.ring_speed = 1.0        # integers so the ripple loops seamlessly
            self.ring_wob = 1.0          # angular wobble speed
            self.ring_drift = 1.0        # center drift speed
        else:
            self.speed = rng.uniform(0.9, 1.9, n).astype(np.float32)  # L->R flow rate
            self.bw = rng.uniform(1.2, 3.6, n).astype(np.float32)
            self.tw = rng.uniform(3.0, 6.5, n).astype(np.float32)     # twinkle rate
            self.bg_speed = 1.7          # background plasma flow rate (faster now)
            self.ring_speed = 0.55       # radial ripple expansion rate (3rd layer)
            self.ring_wob = 0.5
            self.ring_drift = 0.35
        self.margin = 0.12 * self.W
        if targets and mode == "boot":
            homes = [(geom[mp]["cx"], geom[mp]["cy"]) for mp in targets if mp in geom]
            self.target = np.array([homes[rng.integers(len(homes))] for _ in range(n)], np.float32)
        else:
            self.target = np.stack([np.zeros(n), self.lane], 1).astype(np.float32)

    def _converge(self, tt):
        return smooth(0.42, 0.72, tt) if self.mode == "boot" else 0.0

    def positions(self, tt):
        xnorm = np.mod(self.p0 + tt * self.speed, 1.0)              # left->right flow
        x = -self.margin + xnorm * (self.W + 2 * self.margin)
        y = self.lane + self.bob * np.sin(tt * TAU * self.bw + self.ph)
        stream = np.stack([x, y], 1)
        if self.mode == "boot":
            c = self._converge(tt)
            return stream * (1 - c) + self.target * c
        return stream

    def _env(self, tt):
        twk = 0.55 + 0.45 * np.sin(tt * TAU * self.tw + self.ph)
        if self.mode == "boot":
            e = (0.7 + 0.3 * twk) * (1 - smooth(0.70, 0.95, tt))          # fully fade before tutorial
            e += smooth(0.60, 0.70, tt) * (1 - smooth(0.70, 0.88, tt)) * 0.7 * twk  # arrival burst
        else:
            e = 0.5 + 0.4 * twk
        return np.clip(e, 0, 1.5).astype(np.float32)

    def trail_cloud(self, tt, T=26, dt=0.0006):
        """All spark points incl. trails. Sampling each spark's own path in many
        small sub-steps back in time makes a *continuous* comet streak (the
        sub-steps are <1 board pixel apart), fading with age so the head is bright
        and the tail dissolves. During converge the path curves toward the letter,
        so the streak curves too."""
        xs, ys, bs = [], [], []
        env = self._env(tt)
        for j in range(T):
            st = tt - j * dt
            if not self.loop:
                st = max(st, 0.0)      # boot: no history before the intro starts
            pos = self.positions(st)   # idle: periodic funcs handle st<0 (seamless)
            w = (1 - j / T) ** 1.3
            xs.append(pos[:, 0]); ys.append(pos[:, 1]); bs.append(env * w)
        return np.concatenate(xs), np.concatenate(ys), np.concatenate(bs)

    def plasma(self, gx, gy, tt):
        # NOTE: for a seamless idle loop bg_speed and the per-term time multipliers
        # must be integers, so the phase advances a whole number of turns per loop.
        t = tt * TAU * self.bg_speed
        cx, cy = self.W * 0.5, self.H * 0.5
        r = np.sqrt((gx - cx) ** 2 + (gy - cy) ** 2)
        v = (np.sin(gx * 0.010 + t) + np.sin(gy * 0.014 - t) +
             np.sin((gx + gy) * 0.008 + t) + np.sin(r * 0.012 - t))
        return 0.5 + 0.125 * v

    def rings(self, gx, gy, tt):
        """Third layer: expanding ripples -- a radial motion distinct from the
        flowing plasma and the horizontal sparks. Made OVAL (wider than tall),
        with an angular wobble and a slowly drifting center so the rings are not
        perfectly symmetric and vary over time. All time rates are integer in idle
        mode so the ripple loops seamlessly."""
        cx = self.W * (0.5 + 0.03 * np.sin(tt * TAU * self.ring_drift))
        cy = self.H * (0.42 + 0.025 * np.cos(tt * TAU * self.ring_drift))
        dx, dy = gx - cx, gy - cy
        r = np.sqrt((dx / 1.6) ** 2 + (dy * 1.1) ** 2)       # gentle horizontal oval
        th = np.arctan2(dy, dx)
        r = r * (1.0 + 0.06 * np.sin(2.0 * th + tt * TAU * self.ring_wob))  # subtle wobble
        return 0.5 + 0.5 * np.sin(r * 0.016 - tt * TAU * self.ring_speed)


_STAMP = np.array([[0.15, 0.55, 0.15], [0.55, 1.0, 0.55], [0.15, 0.55, 0.15]], np.float32)


def splat_sparks(W, H, xs, ys, bs):
    """Rasterize all spark/trail points into one board-sized intensity buffer, so
    per-key sampling is O(pixels) instead of O(pixels*particles)."""
    Z = np.zeros((H, W), np.float32)
    xi = np.round(xs).astype(int)
    yi = np.round(ys).astype(int)
    ok = (xi >= 1) & (xi < W - 1) & (yi >= 1) & (yi < H - 1) & (bs > 0.02)
    for x, y, b in zip(xi[ok], yi[ok], bs[ok]):
        Z[y - 1:y + 2, x - 1:x + 2] += b * _STAMP
    return Z


def glyph_masks(targets):
    font = ImageFont.truetype(FONT, 34)
    masks = {}
    for mp, ch in targets.items():
        img = Image.new("L", (OLED_W, OLED_H), 0)
        d = ImageDraw.Draw(img)
        bb = d.textbbox((0, 0), ch, font=font)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        d.text(((OLED_W - w) / 2 - bb[0], (OLED_H - h) / 2 - bb[1]), ch, fill=255, font=font)
        masks[mp] = np.asarray(img) > 127
    return masks


LX = np.arange(OLED_W)[None, :]
LY = np.arange(OLED_H)[:, None]


def panel_for(mp, g, eff, masks, Z, tt, pgain, letter_on, ring_gain, fade=0.0):
    # board coords of every native pixel of this key (rotation included)
    gx = g["cx"] + (LX - OLED_W / 2) * g["ux"] + (LY - OLED_H / 2) * g["vx"]
    gy = g["cy"] + (LX - OLED_W / 2) * g["uy"] + (LY - OLED_H / 2) * g["vy"]
    gxr = np.round(gx)
    gyr = np.round(gy)
    # layer 1: background plasma, sparse + irregular white-noise dither
    final = (eff.plasma(gx, gy, tt) * pgain) > hash2(gxr, gyr)
    # layer 3: expanding radial ripples (rv**6 -> thin, dim ring crests)
    rv = eff.rings(gx, gy, tt)
    final = final | ((rv ** 6) * ring_gain > hash2(gxr + 301, gyr + 211))
    # layer 2: sparks + trails -- sample the global spark buffer at this key
    xi = np.clip(gxr.astype(int), 0, Z.shape[1] - 1)
    yi = np.clip(gyr.astype(int), 0, Z.shape[0] - 1)
    final = final | (Z[yi, xi] > 0.24)
    # letters dissolve in, left->right, with an offset noise field
    if mp in masks and letter_on > 0:
        xn = np.clip(g["cx"] / eff.W, 0, 1)
        rf = np.clip(letter_on * 1.7 - xn * 0.45, 0, 1)
        final = final | (masks[mp] & (hash2(gxr + 101, gyr + 57) < rf))
    # dither-dissolve the whole panel to black (fade 0 -> nothing, 1 -> all black)
    if fade > 0.0:
        final = final & (hash2(gxr + 7, gyr + 3) >= fade)
    return Image.fromarray((final.astype(np.uint8) * 255), "L").convert("1")


def build_idle(r, geom, eff, n):
    """Seamless idle loop: sparks + faint plasma + dim ripples, no letters."""
    frames = []
    for f in range(n):
        tt = f / n
        xs, ys, bs = eff.trail_cloud(tt)
        Z = splat_sparks(r.cw, r.ch, xs, ys, bs)
        contents = {}
        for mp, g in geom.items():
            c = KeyContent()
            c.oled = panel_for(mp, g, eff, masks={}, Z=Z, tt=tt,
                               pgain=0.09, letter_on=0.0, ring_gain=0.18)
            contents[mp] = c
        frames.append(contents)
    return frames


def build_boot(r, geom, eff, masks):
    """Intro (sparks -> converge -> letters, ripples fading), a brief hold on the
    formed logo, then a dither-dissolve of EVERYTHING to black -- leaving an empty
    canvas for a (separate) tutorial to start from."""
    frames = []
    N_INTRO = 46
    for i in range(N_INTRO):
        tt = i / (N_INTRO - 1)                           # 0..1 inclusive: ends fully formed
        pgain = 0.03 + 0.02 * smooth(0.0, 0.5, tt)
        letter_on = smooth(0.50, 0.72, tt)
        ring_gain = 0.32 * (1 - smooth(0.45, 0.75, tt))  # dim + fully faded before the hold
        xs, ys, bs = eff.trail_cloud(tt)
        Z = splat_sparks(r.cw, r.ch, xs, ys, bs)
        contents = {}
        for mp, g in geom.items():
            c = KeyContent()
            c.oled = panel_for(mp, g, eff, masks, Z, tt, pgain, letter_on, ring_gain)
            contents[mp] = c
        frames.append(contents)

    # settled logo (no sparks / no ripples), hold, then dissolve to black
    Zzero = np.zeros((r.ch, r.cw), np.float32)
    HOLD, FADE, BLACK = 12, 16, 6

    def logo_frame(fade):
        contents = {}
        for mp, g in geom.items():
            c = KeyContent()
            c.oled = panel_for(mp, g, eff, masks, Zzero, 1.0, 0.05, 1.0, 0.0, fade)
            contents[mp] = c
        return contents

    for _ in range(HOLD):
        frames.append(logo_frame(0.0))
    for k in range(1, FADE + 1):
        frames.append(logo_frame(smooth(0.0, 1.0, k / FADE)))
    black = logo_frame(1.0)                              # fully dissolved -> empty canvas
    for _ in range(BLACK):
        frames.append(black)
    print(f"  boot: {len(frames)} frames ({N_INTRO} intro + hold + dissolve-to-black)")
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["boot", "idle"], default="boot")
    ap.add_argument("--kle", default=DEFAULT_KLE)
    ap.add_argument("--out", default=os.path.join(HERE, "out", "startup_anim.gif"))
    ap.add_argument("--unit", type=int, default=160,
                    help="px per key unit; larger => each OLED pixel is bigger/crisper")
    ap.add_argument("--gap", type=int, default=100)
    ap.add_argument("--frames", type=int, default=72)
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--scale", type=float, default=1.0,
                    help="post-render zoom; keep 1.0 so NEAREST OLED pixels stay crisp")
    ap.add_argument("--hold", type=int, default=12)
    args = ap.parse_args()

    # Pure-white lit pixel on a near-black OLED (was a cool white).
    theme = Theme(oled_on=(255, 255, 255), oled_bg=(6, 7, 10), oled_dim_bg=(10, 10, 12))
    r = ImgRenderer(json.load(open(args.kle, encoding="utf-8")),
                    unit=args.unit, exclude=ENCODERS, bezel=True, theme=theme)
    r.compact_halves(lambda mp: 'L' if int(mp.split(',')[0]) < 5 else 'R', gap_px=args.gap)
    geom = key_board_geom(r)
    targets = splash_targets() if args.mode == "boot" else {}
    targets = {mp: ch for mp, ch in targets.items() if mp in geom}
    masks = glyph_masks(targets)
    eff = Effect(geom, targets, (r.cw, r.ch), mode=args.mode)
    print(f"board {r.cw}x{r.ch}px  keys={len(geom)}  letters={len(targets)}  mode={args.mode}")

    if args.mode == "boot":
        frames = build_boot(r, geom, eff, masks)
    else:
        frames = build_idle(r, geom, eff, args.frames)
    dur = [int(1000 / args.fps)] * len(frames)
    if args.mode == "boot":
        dur[-1] = 1600           # linger on the final tutorial page before the loop
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    r.save_gif(frames, args.out, dur, loop=0, scale=args.scale)
    print("wrote", args.out, f"({len(frames)} frames)")


if __name__ == "__main__":
    main()
