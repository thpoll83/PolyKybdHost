#!/usr/bin/env python3
"""Render the control-group units from Warzone 2100's 3D models.

Warzone 2100's models and textures are GPL-2.0-or-later (its COPYING.README;
the texture repository's README says the same), so they may be used in this
GPL-3.0-or-later host. Command & Conquer's own art is EA's and is not used.

A unit is assembled the way the game does it: a body, a propulsion, and a
weapon (turret mount + gun) placed at the body's first connector. It is drawn
with its texture and a top-front light from an orthographic camera
(`yaw`, `pitch`), fitted into 48x40, Floyd-Steinberg dithered, and given a lit
1 px outline so the shape stays closed on the black OLED.

The model files are fetched from pinned commits, so a re-run gives the same
icons:

    python polyhost/res/overlay_sources/cnc_remastered/wz_units.py
"""
from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.icon_fetch import _get  # noqa: E402

WZ_SHA = "e115b6379c1b831d12980f00f877c1e72e599c68"       # Warzone2100/warzone2100
TEX_SHA = "009ec2f652a6230d8315cc3db4eadb5690f18fbd"      # Warzone2100/data-texpages
WZ_URL = f"https://raw.githubusercontent.com/Warzone2100/warzone2100/{WZ_SHA}/data/{{}}"
TEX_URL = f"https://raw.githubusercontent.com/Warzone2100/data-texpages/{TEX_SHA}/{{}}"

W, H = aoe2.GROUP_W, aoe2.GROUP_H          # 48 x 40, the group binding's region
CACHE = Path(tempfile.gettempdir()) / f"polykybd-wz-{WZ_SHA[:8]}"

B, M = "base/components", "mp/components"


# Key 1: three loose rows of four scavenger soldiers, Warzone's one human model.
# (x, z) in model units; a single figure is drawn too thin to read on a keycap.
CROWD = [(-22.9, -2.1), (-8.4, -1.6), (7.4, -2.4), (26.8, -1.7),
         (-15.0, 20.8), (2.2, 23.0), (13.8, 24.1), (34.7, 24.4),
         (-23.6, 41.9), (-9.8, 46.6), (8.3, 42.1), (26.3, 44.8)]

# digit: (label, [(model path under data/, offset or "body-connector")], camera)
UNITS = {
    "1": ("Infantry crowd (12 scavenger soldiers)",
          [(f"{B}/bodies/exbloke.pie", (x, 0, z)) for x, z in CROWD], dict(yaw=60, pitch=20)),
    "2": ("Scavenger trike", [(f"{B}/bodies/extrike.pie", (0, 0, 0))], dict(yaw=120, pitch=25)),
    "3": ("Pulse laser tank",
          [(f"{B}/bodies/drmbod06.pie", (0, 0, 0)), (f"{B}/prop/prmtrk2.pie", (0, 0, 0)),
           (f"{B}/weapons/trmlas.pie", "body-connector"),
           (f"{B}/weapons/gnmrlas.pie", "body-connector")], dict(yaw=60, pitch=10)),
    "4": ("Half-track, machine gun",
          [(f"{B}/bodies/drmbod06.pie", (0, 0, 0)), (f"{B}/prop/prmhtr2.pie", (0, 0, 0)),
           (f"{B}/weapons/trmmg.pie", "body-connector"),
           (f"{B}/weapons/gnmmg1.pie", "body-connector")], dict(yaw=60, pitch=25)),
    "5": ("Heavy tank, cannon",
          [(f"{B}/bodies/drhbod09.pie", (0, 0, 0)), (f"{B}/prop/prhtrk3.pie", (0, 0, 0)),
           (f"{B}/weapons/trhcan.pie", "body-connector"),
           (f"{B}/weapons/gnhcan.pie", "body-connector")], dict(yaw=60, pitch=25)),
    "6": ("Sensor", [(f"{B}/bodies/drmbod05.pie", (0, 0, 0)), (f"{B}/prop/prmwhl1.pie", (0, 0, 0)),
                     (f"{B}/weapons/trmsnsr2.pie", "body-connector"),
                     (f"{B}/weapons/gnmsnsr2.pie", "body-connector")], dict(yaw=120, pitch=25)),
    "7": ("Rail gun tank",
          [(f"{B}/bodies/drhbod11.pie", (0, 0, 0)), (f"{B}/prop/prhtrk3.pie", (0, 0, 0)),
           (f"{B}/weapons/trhgss.pie", "body-connector"),
           (f"{B}/weapons/gnhgss.pie", "body-connector")], dict(yaw=60, pitch=25)),
    "8": ("Howitzer",
          [(f"{B}/bodies/drhbod09.pie", (0, 0, 0)), (f"{B}/prop/prhtrk3.pie", (0, 0, 0)),
           (f"{B}/weapons/trhhowt.pie", "body-connector"),
           (f"{B}/weapons/gnhhowt.pie", "body-connector")], dict(yaw=60, pitch=25)),
    "9": ("Rocket array",
          [(f"{B}/bodies/drmbod07.pie", (0, 0, 0)), (f"{B}/prop/prmtrk2.pie", (0, 0, 0)),
           (f"{B}/weapons/trmrckt.pie", "body-connector"),
           (f"{B}/weapons/gnmrckt.pie", "body-connector")], dict(yaw=120, pitch=25)),
    "0": ("Scavenger helicopter",
          [(f"{M}/bodies/scavchop.pie", (0, 0, 0)),
           ("base/effects/mediumheli_rotor_stationary.pie", (0, 17, 2))], dict(yaw=70, pitch=65)),
}



def _fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_get(url))
    return dest


def load(path: str):
    """Level 1 of a .pie: points, [(indices, uvs)], connectors, texture file."""
    lines = _fetch(WZ_URL.format(path), CACHE / path).read_text(errors="replace").splitlines()
    ver, tex, scale = 2, None, (256.0, 256.0)
    pts, polys, conns, lvl, i = [], [], [], 0, 0
    while i < len(lines):
        t = lines[i].split()
        if t and t[0] == "PIE":
            ver = int(t[1])
        elif t and t[0] == "TEXTURE":
            tex = t[2]
            scale = (float(t[3]) or 1.0, float(t[4]) or 1.0) if ver == 2 else (1.0, 1.0)
        elif t and t[0] == "LEVEL":
            lvl = int(t[1])
        elif t and t[0] in ("POINTS", "POLYGONS", "CONNECTORS") and lvl == 1:
            n = int(t[1])
            rows = [lines[i + 1 + k].split() for k in range(n)]
            if t[0] == "POINTS":
                pts = [list(map(float, r[:3])) for r in rows]
            elif t[0] == "CONNECTORS":
                conns = [list(map(float, r[:3])) for r in rows]
            else:
                for r in rows:
                    cnt = int(r[1])
                    idx = [int(x) for x in r[2:2 + cnt]]
                    rest = r[2 + cnt:]
                    if int(r[0], 16) & 0x4000:          # animated texture: skip frame data
                        rest = rest[4:]
                    uv = [(float(rest[2 * j]) / scale[0], float(rest[2 * j + 1]) / scale[1])
                          for j in range(cnt)] if len(rest) >= 2 * cnt else [(0.0, 0.0)] * cnt
                    polys.append((idx, uv))
            i += n
        i += 1
    return np.array(pts), polys, np.array(conns) if conns else np.zeros((0, 3)), tex


_textures = {}


def texture(name: str):
    if name not in _textures:
        p = _fetch(TEX_URL.format(name), CACHE / "texpages" / name)
        _textures[name] = np.asarray(Image.open(p).convert("RGB"), float).mean(-1) / 255
    return _textures[name]


def render(parts, yaw, pitch, px=320, light=(-0.4, 0.8, 0.45), ambient=0.35):
    """Grey image (0..1) and coverage of the textured, lit model."""
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    R = (np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
         @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]))
    L = np.array(light, float) / np.linalg.norm(light)
    body_conn = load(parts[0][0])[2]
    bx, bz, by = body_conn[0] if len(body_conn) else (0, 0, 0)
    tris = []
    for path, off in parts:
        p, polys, _, texname = load(path)
        off = (bx, by, bz) if off == "body-connector" else off
        T = texture(texname) if texname else None
        q = (p + np.array(off)) @ R.T
        for idx, uv in polys:
            for k in range(1, len(idx) - 1):
                tri = [0, k, k + 1]
                tris.append((q[[idx[j] for j in tri]], np.array([uv[j] for j in tri]), T))
    allp = np.concatenate([t[0] for t in tris])
    x0, x1 = allp[:, 0].min(), allp[:, 0].max()
    y0, y1 = allp[:, 1].min(), allp[:, 1].max()
    s = (px - 4) / max(x1 - x0, y1 - y0)
    w, h = int((x1 - x0) * s) + 4, int((y1 - y0) * s) + 4
    img, cover, zbuf = np.zeros((h, w)), np.zeros((h, w), bool), np.full((h, w), -1e9)
    for P, UV, T in tris:
        sx, sy_ = (P[:, 0] - x0) * s + 2, (y1 - P[:, 1]) * s + 2
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if not np.linalg.norm(n):
            continue
        n = n / np.linalg.norm(n)
        if n[2] < 0:                    # two-sided: turn every face to the camera
            n = -n
        shade = ambient + (1 - ambient) * max(0.0, float(n @ L))
        xa, xb = max(0, math.floor(sx.min())), min(w - 1, math.ceil(sx.max()))
        ya, yb = max(0, math.floor(sy_.min())), min(h - 1, math.ceil(sy_.max()))
        d = (sy_[1] - sy_[2]) * (sx[0] - sx[2]) + (sx[2] - sx[1]) * (sy_[0] - sy_[2])
        if xb < xa or yb < ya or abs(d) < 1e-9:
            continue
        X, Y = np.meshgrid(np.arange(xa, xb + 1) + 0.5, np.arange(ya, yb + 1) + 0.5)
        w0 = ((sy_[1] - sy_[2]) * (X - sx[2]) + (sx[2] - sx[1]) * (Y - sy_[2])) / d
        w1 = ((sy_[2] - sy_[0]) * (X - sx[2]) + (sx[0] - sx[2]) * (Y - sy_[2])) / d
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        z = w0 * P[0, 2] + w1 * P[1, 2] + w2 * P[2, 2]
        win = inside & (z > zbuf[ya:yb + 1, xa:xb + 1])
        if not win.any():
            continue
        if T is not None:
            u = (w0 * UV[0, 0] + w1 * UV[1, 0] + w2 * UV[2, 0]) % 1.0
            v = (w0 * UV[0, 1] + w1 * UV[1, 1] + w2 * UV[2, 1]) % 1.0
            col = T[(v * (T.shape[0] - 1)).astype(int), (u * (T.shape[1] - 1)).astype(int)]
        else:
            col = np.full(X.shape, 0.6)
        zbuf[ya:yb + 1, xa:xb + 1][win] = z[win]
        img[ya:yb + 1, xa:xb + 1][win] = (col * shade)[win]
        cover[ya:yb + 1, xa:xb + 1][win] = True
    return img, cover


def _edge(a):
    p = np.pad(a, 1)
    return a & ~(p[2:, 1:-1] & p[:-2, 1:-1] & p[1:-1, 2:] & p[1:-1, :-2])


def keycap(img, cover, blur=0.4, floor=0.15, size=(W, H), mirror=True):
    """Fit into `size`, dither the inside, light the outline. The renders face
    left, so `mirror` turns them to face right."""
    ys, xs = np.nonzero(cover)
    img = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    cover = cover[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if mirror:
        img, cover = img[:, ::-1], cover[:, ::-1]
    s = min(size[0] / img.shape[1], size[1] / img.shape[0])
    size = (max(1, round(img.shape[1] * s)), max(1, round(img.shape[0] * s)))
    gi = Image.fromarray((img * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur / s))
    g = np.asarray(gi.resize(size, Image.LANCZOS), float) / 255
    a = np.asarray(Image.fromarray((cover * 255).astype(np.uint8)).resize(size, Image.LANCZOS)) > 127
    lo, hi = np.percentile(g[a], 3), np.percentile(g[a], 97)
    g = np.clip((g - lo) / max(hi - lo, 1e-6), 0, 1)
    out = _edge(a)
    inside = a & ~out
    v = np.where(inside, floor + (1 - floor) * g, 0)
    fill = np.asarray(Image.fromarray((v * 255).astype(np.uint8)).convert("1")) > 0
    return out | (fill & inside)


def _with_plus(mask, size=13, bar=3):
    """The plus for Ctrl (create group) in the top-right corner, with the AoE2
    groups' GROUP_SEAM px of clear space around it."""
    h, w = mask.shape
    p = np.zeros((h, w), bool)
    cy, cx = size // 2, w - size // 2 - 1
    p[cy - bar // 2:cy + bar // 2 + 1, cx - size // 2:cx + size // 2 + 1] = True
    p[cy - size // 2:cy + size // 2 + 1, cx - bar // 2:cx + bar // 2 + 1] = True
    return (mask & ~program_mark.dilate(p, aoe2.GROUP_SEAM)) | p


def _save(mask, path: Path) -> None:
    """White on transparent, right-aligned and bottom-aligned in W x H."""
    canvas = np.zeros((H, W, 4), np.uint8)
    h, w = mask.shape
    canvas[H - h:, W - w:, :3] = 255
    canvas[H - h:, W - w:, 3] = np.where(mask, 255, 0)
    Image.fromarray(canvas, "RGBA").save(path)


def main(out: Path | None = None) -> int:
    out = out or Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for digit, (label, parts, cam) in UNITS.items():
        m = keycap(*render(parts, **cam))
        _save(m, out / f"group{digit}.png")
        full = np.zeros((H, W), bool)
        full[H - m.shape[0]:, W - m.shape[1]:] = m
        _save(_with_plus(full), out / f"groupnew{digit}.png")
        print(f"  group{digit}.png, groupnew{digit}.png  <- Warzone 2100: {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
