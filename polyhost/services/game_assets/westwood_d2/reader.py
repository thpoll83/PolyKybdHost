"""Game-asset reader for Dune II (1992).

Reads the user's own DUNE.PAK: the unit sprites UNITS.SHP, UNITS1.SHP and
UNITS2.SHP, the mouse cursors MOUSE.SHP and the palette IBM.PAL. Dune Legacy
and OpenDUNE both play from these files (see ``find``). Nothing read here
leaves the machine.

The sprites are 16 to 24 px, too small to dither like the C&C ones. A unit is
drawn pixel for pixel at a whole-number scale: its outline lit and the inside
lit where it is brighter than the sprite's median. Recipes:

- ``{unit: units2, face: 3, turret: 8}``: a frame of a shape file, with an
  optional second frame (a turret) drawn over it, the two centred on each
  other;
- ``{cursor: 5}``: a mouse cursor, as in the C&C reader.

Frame numbers are those of the 1.07 files (Dune Legacy's GFXManager.cpp):
each ground unit has five facings from north to south, so base + 3 faces
south-east.
"""
from __future__ import annotations

import os
import struct
from pathlib import Path

import numpy as np

from polyhost.services.game_assets import dither
from polyhost.services.game_assets.westwood_d2.pak import Pak
from polyhost.services.game_assets.westwood_td import reader as td
from polyhost.services.game_assets.westwood_td import westwood

REQUIRED = ("dune.pak",)


def data_files(d: Path) -> dict | None:
    names = td._listing(d)
    if not all(r in names for r in REQUIRED):
        return None
    return {n: d / names[n] for n in REQUIRED}


def data_dirs(hint=None) -> list[Path]:
    """Where Dune Legacy and OpenDUNE keep the original files: beside the game
    (`hint`) and in its data subfolder, then the users' data folders."""
    home = Path.home()
    dirs = [Path(hint), Path(hint) / "data"] if hint else []
    if os.environ.get("APPDATA"):
        dirs.append(Path(os.environ["APPDATA"]) / "DuneLegacy" / "data")
    xdg = os.environ.get("XDG_CONFIG_HOME")
    dirs.append((Path(xdg) if xdg else home / ".config") / "DuneLegacy" / "data")
    dirs += [home / "Library" / "Application Support" / "Dune Legacy" / "data",
             home / "Library" / "Application Support" / "OpenDUNE" / "data",
             Path("/usr/share/dunelegacy"), Path("/usr/local/share/dunelegacy"),
             Path("/usr/share/DuneLegacy"), Path("/usr/local/share/DuneLegacy")]
    return dirs


def find(folder: str = "", hint=None) -> dict | None:
    """The game files to read: from `folder` when set; else from the folder of
    the running game's executable or its data subfolder; else from Dune
    Legacy's and OpenDUNE's data folders. DOSBox users set the folder: the
    executable is DOSBox's."""
    if folder:
        return data_files(Path(folder).expanduser())
    for d in data_dirs(hint):
        files = data_files(d)
        if files:
            return files
    return None


def fingerprint(files: dict) -> list:
    return sorted(files.values())


def is_v1_0(shp: bytes) -> bool:
    """Whether a shape file is from Dune II 1.0 (the 1992 demo and first
    release): its frame offsets are 2 bytes, those of 1.07 are 4."""
    return len(shp) >= 6 and (struct.unpack_from("<I", shp, 2)[0] & 0xFF0000) > 0


def open_source(files: dict) -> td.Sprites:
    pak = Pak.open(files["dune.pak"])
    pal = pak.get("ibm.pal")
    if pal is None:
        raise KeyError("IBM.PAL is not in DUNE.PAK")
    units = pak.get("units.shp")
    if units is not None and is_v1_0(units):
        # 1.0 numbers its frames differently: the recipes would draw the wrong units.
        raise ValueError("DUNE.PAK is from Dune II 1.0; the recipes number the frames of 1.07")
    return td.Sprites([pak], pal, pak.get("mouse.shp"), "DUNE.PAK", decode=westwood.shp_d2_frames)


def _pixels(sp: td.Sprites, recipe: dict) -> np.ndarray:
    """The palette-index image of a unit recipe, a turret centred on its base."""
    idx = sp.frame(recipe["unit"], recipe.get("face", 0)).copy()
    if "turret" in recipe:
        t = sp.frame(recipe["unit"], recipe["turret"])
        h, w = max(idx.shape[0], t.shape[0]), max(idx.shape[1], t.shape[1])
        out = np.zeros((h, w), np.uint8)
        for img in (idx, t):
            y0, x0 = (h - img.shape[0]) // 2, (w - img.shape[1]) // 2
            sub = out[y0:y0 + img.shape[0], x0:x0 + img.shape[1]]
            sub[img != 0] = img[img != 0]
        idx = out
    return idx


def pixel_icon(sp: td.Sprites, idx: np.ndarray, size) -> np.ndarray:
    """`idx` cropped to its pixels, lit as described above, at the largest
    whole-number scale that fits `size` (w, h)."""
    cover = idx != 0
    ys, xs = np.nonzero(cover)
    sl = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    idx, cover = idx[sl], cover[sl]
    g = sp.pal[idx].astype(float) @ [0.299, 0.587, 0.114]
    edge = dither.edge(cover)
    m = edge | (cover & ~edge & (g > np.median(g[cover])))
    k = max(1, min(size[0] // m.shape[1], size[1] // m.shape[0]))
    return np.kron(m, np.ones((k, k), bool))


def draw(sp: td.Sprites, recipe: dict, size):
    if "unit" in recipe:
        return pixel_icon(sp, _pixels(sp, recipe), size)
    if "cursor" in recipe:
        if sp.mouse is None:
            return None
        return td._cursor(sp, recipe["cursor"], size, recipe.get("threshold", -1.0))
    raise ValueError(f"unknown recipe {recipe!r}")
