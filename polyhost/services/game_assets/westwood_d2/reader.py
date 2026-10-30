"""Game-asset reader for Dune II (1992).

Reads the user's own DUNE.PAK: the build portraits and buttons of SHAPES.SHP,
the unit sprites UNITS.SHP and UNITS2.SHP, the mouse cursors MOUSE.SHP, the
map tiles ICON.ICN / ICON.MAP, the fonts NEW8P.FNT and NEW6P.FNT and the
palette IBM.PAL. Dune Legacy and OpenDUNE both play from these files (see
``find``). Nothing read here leaves the machine.

A recipe is what the icon picker exports (tools/ICON_PICKER.md), drawn by
the picker's own renderer (``picture.py``), so the keyboard shows what the
page showed:

- ``{src: "shp:shapes.shp:81", engine: dither, ...}``: a picture (see
  ``source``) and the page's settings for it;
- ``{word: Attack, font: new8p.fnt, ...}``: a word in a game font.

``region`` and ``margin`` place it as the page did. Frame numbers are those
of Dune Legacy's GFXManager.cpp. The 1.0 demo's SHAPES.SHP, UNITS.SHP and
UNITS2.SHP have the same pictures at the same numbers, so 1.0 and 1.07 files
are both read.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from polyhost.services.game_assets import picture
from polyhost.services.game_assets.westwood_d2.formats import font_glyphs, icn_tiles
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


def open_source(files: dict) -> td.Sprites:
    pak = Pak.open(files["dune.pak"])
    pal = pak.get("ibm.pal")
    if pal is None:
        raise KeyError("IBM.PAL is not in DUNE.PAK")
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


def source(sp: td.Sprites, src: str) -> np.ndarray:
    """The palette-index image a recipe's `src` names:

    - ``shp:<file>.shp:<frame>``: a frame of a shape file;
    - ``sprite:<file>:<face>[+<turret>]``: a map sprite, a turret over its base;
    - ``icn:<group>:<start>:<w>x<h>``: a building as the map shows it, tiles
      start .. start + w*h - 1 of ICON.MAP group `group`, row by row;
    - ``icnset:<group>:<i>``: one tile of an ICON.MAP group;
    - ``icntile:<tile>:<n>``: ICON.ICN tile `tile`, repeated n x n."""
    kind, _, rest = src.partition(":")
    if kind == "shp":
        name, frame = rest.rsplit(":", 1)
        return sp.frame(name.lower().removesuffix(".shp"), int(frame))
    if kind == "sprite":
        name, faces = rest.split(":")
        face, _, turret = faces.partition("+")
        recipe = {"unit": name, "face": int(face)}
        if turret:
            recipe["turret"] = int(turret)
        return _pixels(sp, recipe)
    if kind in ("icn", "icnset", "icntile"):
        if getattr(sp, "_icn", None) is None:
            icn, mp = sp.get("icon.icn"), sp.get("icon.map")
            if icn is None or mp is None:
                raise KeyError("ICON.ICN or ICON.MAP is not in DUNE.PAK")
            sp._icn = icn_tiles(icn, mp)
        tiles, groups = sp._icn
        if kind == "icn":
            group, start, size = rest.split(":")
            tw, th = (int(v) for v in size.split("x"))
            t = groups[int(group)][int(start):int(start) + tw * th]
            return np.vstack([np.hstack([tiles[t[r * tw + c]] for c in range(tw)]) for r in range(th)])
        if kind == "icnset":
            group, i = rest.split(":")
            return tiles[groups[int(group)][int(i)]]
        tile, n = rest.split(":")
        return np.tile(tiles[int(tile)], (int(n), int(n)))
    raise ValueError(f"unknown source {src!r}")


def font(sp: td.Sprites, name: str) -> tuple[int, dict]:
    data = sp.get(name.lower())
    if data is None:
        raise KeyError(f"{name} is not in DUNE.PAK")
    return font_glyphs(data)


def palette(sp: td.Sprites) -> np.ndarray:
    """256 x RGB, as the icon picker page has it."""
    return np.asarray(sp.pal).astype(np.uint8)


def draw(sp: td.Sprites, recipe: dict, size):
    if "word" in recipe:
        return picture.word(font(sp, recipe.get("font", "new8p.fnt")), dict(recipe, text=recipe["word"]), size)
    if "src" in recipe:
        return picture.picture(source(sp, recipe["src"]), palette(sp), recipe, size)
    raise ValueError(f"unknown recipe {recipe!r}")
