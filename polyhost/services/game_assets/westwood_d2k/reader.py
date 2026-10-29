"""Game-asset reader for Dune 2000 (1998).

Reads the user's own DATA.R16 (DATA.R8 in older copies) and PALETTE.BIN.
OpenRA's content installer writes them to ``Content/d2k/v3/`` (see
``openra.py``). Nothing read here leaves the machine.

Recipes give frame numbers in DATA.R16, as OpenRA's mods/d2k/sequences/*.yaml
do (a unit's facings start at its ``Start``):

- ``{frame: 1755, turret: 1883}``: a frame, with an optional second frame (a
  turret) drawn over it, the two centred on each other, drawn like the C&C
  units (``westwood_td.reader._keycap``);
- ``{crowd: 206}``: twelve of one infantry frame in three rows.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from polyhost.services.game_assets import openra
from polyhost.services.game_assets.westwood_d2k.r16 import R16
from polyhost.services.game_assets.westwood_td import reader as td

SPRITES = ("data.r16", "data.r8")
PALETTE = "palette.bin"


def data_files(d: Path) -> dict | None:
    names = td._listing(d)
    sprites = next((s for s in SPRITES if s in names), None)
    if sprites is None or PALETTE not in names:
        return None
    return {"sprites": d / names[sprites], PALETTE: d / names[PALETTE]}


def find(folder: str = "", hint=None) -> dict | None:
    """From `folder` when set; else from OpenRA's Dune 2000 content folder."""
    if folder:
        return data_files(Path(folder).expanduser())
    for d in openra.content_dirs("d2k/v3", hint) + openra.content_dirs("d2k", hint):
        files = data_files(d)
        if files:
            return files
    return None


def fingerprint(files: dict) -> list:
    return sorted(files.values())


def open_source(files: dict) -> R16:
    return R16(Path(files["sprites"]).read_bytes(), Path(files[PALETTE]).read_bytes())


def _grey(rgb):
    return rgb.astype(float) @ [0.299, 0.587, 0.114] / 255


def _overlay(base, top):
    """`top` (rgb, cover) drawn centred over `base`."""
    (a, ca), (b, cb) = base, top
    h, w = max(a.shape[0], b.shape[0]), max(a.shape[1], b.shape[1])
    rgb, cover = np.zeros((h, w, 3), np.uint8), np.zeros((h, w), bool)
    for img, c in ((a, ca), (b, cb)):
        y0, x0 = (h - img.shape[0]) // 2, (w - img.shape[1]) // 2
        rgb[y0:y0 + img.shape[0], x0:x0 + img.shape[1]][c] = img[c]
        cover[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] |= c
    return rgb, cover


def _crowd(frame):
    rgb, c = frame
    ys, xs = np.nonzero(c)
    rgb, c = rgb[ys.min():ys.max() + 1, xs.min():xs.max() + 1], c[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    dy, dx = max(1, c.shape[0] * 2 // 5), max(1, c.shape[1] * 3 // 4)
    H, W = c.shape[0] + 2 * dy, c.shape[1] + 3 * dx + dx // 2
    out, cover = np.zeros((H, W, 3), np.uint8), np.zeros((H, W), bool)
    for r in range(3):
        for k in range(4):
            y, x = r * dy, k * dx + (dx // 2 if r % 2 else 0)
            out[y:y + c.shape[0], x:x + c.shape[1]][c] = rgb[c]
            cover[y:y + c.shape[0], x:x + c.shape[1]] |= c
    return out, cover


def draw(src: R16, recipe: dict, size):
    if "frame" in recipe:
        img = src.frame(recipe["frame"])
        if "turret" in recipe:
            img = _overlay(img, src.frame(recipe["turret"]))
    elif "crowd" in recipe:
        img = _crowd(src.frame(recipe["crowd"]))
    else:
        raise ValueError(f"unknown recipe {recipe!r}")
    rgb, cover = img
    if not cover.any():
        raise ValueError("an empty frame")
    return td._keycap(_grey(rgb) * cover, cover, size)
