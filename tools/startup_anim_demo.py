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

from kle_render import KleRenderer, KeyContent, OLED_W, OLED_H

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
DEFAULT_KLE = os.path.join(HOST_REPO, "polyhost", "res", "polykybd-split72.json")
ENCODERS = {"3,7", "8,0"}          # left & right rotary encoders: no display
FONT = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"

# 4x4 ordered Bayer matrix, normalized to (0,1) -- the same one the firmware
# blitter (doom_blit.c) uses; ordered dither is stable frame-to-frame on mono.
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


class Effect:
    def __init__(self, geom, targets, board_wh, mode="boot", seed=1234):
        self.geom = geom
        self.mode = mode
        self.W, self.H = board_wh
        rng = np.random.default_rng(seed)
        n = 240 if mode == "boot" else 90
        self.n = n
        if targets and mode == "boot":
            homes = [(geom[mp]["cx"], geom[mp]["cy"]) for mp in targets if mp in geom]
            self.home = np.array([homes[rng.integers(len(homes))] for _ in range(n)], np.float32)
        else:
            self.home = np.stack([rng.uniform(0, self.W, n), rng.uniform(0, self.H, n)], 1).astype(np.float32)
        self.phase = rng.uniform(0, 2 * np.pi, n).astype(np.float32)
        self.spin = (rng.uniform(0.6, 1.6, n) * rng.choice([-1, 1], n)).astype(np.float32)
        self.rad = rng.uniform(0.35, 1.0, n).astype(np.float32)
        self.tw = rng.uniform(2.0, 5.0, n).astype(np.float32)
        self.drx = (rng.uniform(0.3, 1.1, n) * rng.choice([-1, 1], n)).astype(np.float32)
        self.dry = (rng.uniform(0.3, 1.1, n) * rng.choice([-1, 1], n)).astype(np.float32)

    def converge(self, tt):
        return smooth(0.30, 0.62, tt) if self.mode == "boot" else 0.0

    def particles(self, tt):
        c = self.converge(tt)
        R0 = 0.16 * min(self.W, self.H)
        radius = self.rad * R0 * (1.0 - c)
        ang = self.phase + tt * 6.283 * self.spin
        drift = (1.0 - c) * 0.10 * min(self.W, self.H)
        dx = np.cos(ang) * radius + np.sin(tt * 6.283 * self.drx + self.phase) * drift
        dy = np.sin(ang) * radius + np.cos(tt * 6.283 * self.dry + self.phase) * drift
        pos = self.home + np.stack([dx, dy], 1)
        twk = 0.5 + 0.5 * np.sin(tt * 6.283 * self.tw + self.phase)
        if self.mode == "boot":
            env = (0.6 + 0.4 * twk) * (1.0 - smooth(0.72, 1.0, tt) * 0.8)
            env += smooth(0.55, 0.66, tt) * (1 - smooth(0.66, 0.8, tt)) * 0.8 * twk
        else:
            env = 0.35 + 0.35 * twk
        return pos, np.clip(env, 0, 1.4).astype(np.float32)

    def plasma(self, gx, gy, tt):
        t = tt * 6.283
        cx, cy = self.W * 0.5, self.H * 0.5
        r = np.sqrt((gx - cx) ** 2 + (gy - cy) ** 2)
        v = (np.sin(gx * 0.020 + t) + np.sin(gy * 0.028 - t * 0.8) +
             np.sin((gx + gy) * 0.017 + t * 0.6) + np.sin(r * 0.024 - t * 1.3))
        return 0.5 + 0.125 * v


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


def panel_for(mp, g, eff, masks, pos, pb, tt, pgain, letter_on):
    # board coords of every native pixel of this key (rotation included)
    gx = g["cx"] + (LX - OLED_W / 2) * g["ux"] + (LY - OLED_H / 2) * g["vx"]
    gy = g["cy"] + (LX - OLED_W / 2) * g["uy"] + (LY - OLED_H / 2) * g["vy"]
    lit = (eff.plasma(gx, gy, tt) * pgain > BAY).astype(np.float32) * 0.5
    # sparkles: nearby particles
    sel = ((pos[:, 0] > g["cx"] - 40) & (pos[:, 0] < g["cx"] + 40) &
           (pos[:, 1] > g["cy"] - 40) & (pos[:, 1] < g["cy"] + 40))
    if np.any(sel):
        d2 = ((gx[..., None] - pos[sel, 0]) ** 2 + (gy[..., None] - pos[sel, 1]) ** 2)
        spark = (np.exp(-d2 / (2 * 1.3 ** 2)) * pb[sel]).sum(-1)
        lit = np.maximum(lit, np.clip(spark, 0, 1))
    # letter dither-dissolve reveal, left->right by board x
    if mp in masks and letter_on > 0:
        xn = np.clip(g["cx"] / eff.W, 0, 1)
        rf = np.clip(letter_on * 1.6 - xn * 0.5, 0, 1)
        lit = np.maximum(lit, (masks[mp] & (BAY < rf)).astype(np.float32))
    return Image.fromarray((np.clip(lit, 0, 1) * 255).astype(np.uint8), "L").convert("1")


def build_frames(r, geom, eff, targets, masks, n):
    frames = []
    for f in range(n):
        tt = f / n
        pos, pb = eff.particles(tt)
        if eff.mode == "boot":
            pgain = 0.10 + 0.16 * smooth(0.0, 0.5, tt)
            letter_on = smooth(0.50, 0.62, tt)
        else:
            pgain, letter_on = 0.22, 0.0
        contents = {}
        for mp, g in geom.items():
            c = KeyContent()
            c.oled = panel_for(mp, g, eff, masks, pos, pb, tt, pgain, letter_on)
            contents[mp] = c
        frames.append(contents)
        if (f + 1) % 16 == 0:
            print(f"  frame {f+1}/{n}")
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["boot", "idle"], default="boot")
    ap.add_argument("--kle", default=DEFAULT_KLE)
    ap.add_argument("--out", default=os.path.join(HERE, "out", "startup_anim.gif"))
    ap.add_argument("--unit", type=int, default=72)
    ap.add_argument("--gap", type=int, default=48)
    ap.add_argument("--frames", type=int, default=84)
    ap.add_argument("--fps", type=int, default=22)
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--hold", type=int, default=14)
    args = ap.parse_args()

    r = ImgRenderer(json.load(open(args.kle, encoding="utf-8")),
                    unit=args.unit, exclude=ENCODERS, bezel=True)
    r.compact_halves(lambda mp: 'L' if int(mp.split(',')[0]) < 5 else 'R', gap_px=args.gap)
    geom = key_board_geom(r)
    targets = splash_targets() if args.mode == "boot" else {}
    targets = {mp: ch for mp, ch in targets.items() if mp in geom}
    masks = glyph_masks(targets)
    eff = Effect(geom, targets, (r.cw, r.ch), mode=args.mode)
    print(f"board {r.cw}x{r.ch}px  keys={len(geom)}  letters={len(targets)}  mode={args.mode}")

    n = args.frames
    frames = build_frames(r, geom, eff, targets, masks, n)
    if args.mode == "boot":
        frames += [frames[-1]] * args.hold
    dur = [int(1000 / args.fps)] * len(frames)
    if args.mode == "boot":
        dur[-1] = 900
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    r.save_gif(frames, args.out, dur, loop=0, scale=args.scale)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
