"""Game-asset reader for Factorio (2.0 and later).

Reads PNG icons from the user's own Factorio install: the ``data`` folder,
which holds the ``base`` and ``core`` mods. Nothing read here leaves the
machine, and no Factorio image is in this repository.

The reader knows nothing about keys: an overlay spec's ``game_assets:`` block
says what to draw on each key, as a recipe (``draw()``), and the shared build
in ``build.py`` places the result. A recipe::

    {file: base/graphics/icons/pistol.png, mode: dither}
    {file: core/graphics/side-menu-buttons.png, size: 64, row: 7, mode: silhouette}

- ``file``: the PNG, relative to the data folder (the path after
  ``__base__/`` or ``__core__/`` in the game's prototype definitions), or a
  list of them: the first one present is read.
- ``size``: the side of one square picture in the file, in px. Default: the
  height of the file. Factorio 2.0 stores an icon at 64x64 with its smaller
  copies (mipmaps) to the right of it (64 + 32 + 16 + 8 = 120 px wide); only
  the first square is read.
- ``row``: the picture ``row`` squares down in a sheet of pictures (default 0).
- ``mode``: ``dither`` (the picture's light and dark parts, dithered, with its
  outline lit: for coloured item art), ``threshold`` (the same, with the parts
  lighter than mid-grey lit and no dither) or ``silhouette`` (the shape alone:
  for the one-colour GUI symbols). A ``silhouette`` picture that turns out to
  have parts of different brightness, or no transparent background, is drawn
  as ``threshold`` instead, so that its inner lines are not lost.
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image

from polyhost.services.game_assets import dither
from polyhost.services.game_assets.steam import libraries as _steam_libraries

# Present in every Factorio data folder: the mods' manifests and the icon folders.
REQUIRED = ("base/info.json", "core/info.json", "base/graphics/icons")

# Item art is 64 px drawn at about 40 px: a little sharpening keeps thin parts.
ITEM = {"lo_p": 3, "hi_p": 97, "sharpen": 0.6}
# A one-colour picture: brightness spread (standard deviation, 0..1) below this.
FLAT = 0.12
# A picture whose shape fills more than this of its bounding box has no
# transparent background to draw the shape from.
SOLID = 0.9
# The macOS system applications folder (a module name, so tests can move it).
SYSTEM_APPS = Path("/Applications")
# Larger files are not Factorio icons; refused before decoding.
MAX_PIXELS = 4096 * 4096


# --------------------------------------------------------------------------- #
# finding the files
# --------------------------------------------------------------------------- #

def is_data_dir(d: Path) -> bool:
    return all((Path(d) / r).exists() for r in REQUIRED)


def _data_dirs(d: Path) -> list[Path]:
    """`d` itself, and the data folder of an install folder or a macOS app."""
    d = Path(d)
    return [d, d / "data", d / "Contents" / "data", d / "factorio.app" / "Contents" / "data"]


def _hint_dirs(hint) -> list[Path]:
    """The data folder of the install the running game's executable is in.
    The executable is ``bin/x64/factorio(.exe)``, so the data folder is two
    levels up; under Proton the hint is the working folder, which may be the
    install folder itself."""
    if not hint:
        return []
    h = Path(hint)
    out = []
    for up in (h, *list(h.parents)[:3]):
        out.extend(_data_dirs(up))
    return out


def install_candidates() -> list[Path]:
    """The data folders of the installs this host knows how to find: Steam
    (every library, Windows, Linux and macOS), the standalone Windows installer,
    the Linux archive unpacked in the home folder, and the macOS app."""
    home = Path.home()
    out = []
    for lib in _steam_libraries():
        inst = lib / "steamapps" / "common" / "Factorio"
        out += [inst / "data", inst / "factorio.app" / "Contents" / "data"]
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        if os.environ.get(env):
            out.append(Path(os.environ[env]) / "Factorio" / "data")
    out.append(home / "factorio" / "data")
    for apps in (SYSTEM_APPS, home / "Applications"):
        out.append(apps / "factorio.app" / "Contents" / "data")
    return out


def find(folder: str = "", hint=None) -> dict | None:
    """{"data": the data folder}: from `folder` when set (the data folder, the
    install folder or factorio.app); else from the install that `hint` (the
    folder of the running game's executable) belongs to; else from the first
    known install folder that has one."""
    if folder:
        candidates = _data_dirs(Path(folder).expanduser())
    else:
        candidates = _hint_dirs(hint) + install_candidates()
    for d in candidates:
        if is_data_dir(d):
            return {"data": d}
    return None


def fingerprint(files: dict) -> list:
    """The files whose size and time key the cached copy: each mod's info.json,
    which a game update rewrites with the new version."""
    return [files["data"] / "base" / "info.json", files["data"] / "core" / "info.json"]


def inputs(files: dict, recipes: dict) -> list:
    """Every PNG the recipes name, present or not. Repairing the game files
    rewrites a damaged or missing PNG and leaves info.json as it was, so these
    are part of the cache key too (build.build)."""
    out = []
    for recipe in recipes.values():
        names = recipe.get("file") or []
        for name in names if isinstance(names, list) else [names]:
            rel = PurePosixPath(str(name))
            if not rel.is_absolute() and ".." not in rel.parts:
                out.append(files["data"].joinpath(*rel.parts))
    return out


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

class Icons:
    """The data folder, and each PNG read so far."""

    def __init__(self, data: Path):
        self.data = Path(data)
        self._png = {}

    def rgba(self, name: str) -> np.ndarray:
        """The file `name` (relative to the data folder) as RGBA, 0..1."""
        rel = PurePosixPath(name)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"{name} is not inside the data folder")
        if name not in self._png:
            path = self.data.joinpath(*rel.parts)
            if not path.is_file():
                raise KeyError(f"{name} is not in the Factorio data folder")
            try:
                with Image.open(path) as im:
                    if im.width * im.height > MAX_PIXELS:
                        raise ValueError(f"{name} is {im.width}x{im.height}, larger than an icon")
                    self._png[name] = np.asarray(im.convert("RGBA"), float) / 255
            except OSError as e:
                # Unreadable or not a PNG: costs this key only (build.render).
                raise ValueError(f"{name}: {e}") from e
        return self._png[name]


def picture(icons: Icons, recipe: dict):
    """(grey 0..1, alpha 0..1) of the one square picture a recipe names. A
    list of files is tried in order (a file renamed between game versions)."""
    names = recipe["file"] if isinstance(recipe["file"], list) else [recipe["file"]]
    if not names:
        raise ValueError("a recipe without a file")
    for name in names:
        try:
            rgba = icons.rgba(name)
            break
        except KeyError:
            if name == names[-1]:
                raise
    side = int(recipe.get("size") or rgba.shape[0])
    row = int(recipe.get("row", 0))
    if side <= 0 or rgba.shape[1] < side or rgba.shape[0] < (row + 1) * side:
        raise ValueError(f"{name} has no {side} px picture in row {row}")
    cell = rgba[row * side:(row + 1) * side, :side]
    return cell[..., :3] @ [0.299, 0.587, 0.114], cell[..., 3]


def mode_for(grey, cover, mode: str) -> str:
    """The mode a picture is drawn in: `silhouette` only for a one-colour
    picture on a transparent background."""
    if mode != "silhouette":
        return mode
    ys, xs = np.nonzero(cover)
    box = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
    if grey[cover].std() >= FLAT or cover.sum() > SOLID * box:
        return "threshold"
    return "silhouette"


def draw(icons: Icons, recipe: dict, size):
    """A boolean mask fitted inside `size` (w, h) for one recipe (see the
    module docstring)."""
    grey, alpha = picture(icons, recipe)
    cover = alpha >= 0.5
    if not cover.any():
        raise ValueError(f"{recipe['file']} has an empty picture")
    mode = mode_for(grey, cover, recipe.get("mode", "dither"))
    if mode == "dither":
        return dither.keycap(grey * cover, cover, size, **ITEM)
    if mode == "threshold":
        return dither.keycap(grey * cover, cover, size, threshold=0.5, **ITEM)
    if mode == "silhouette":
        return dither.keycap(grey * cover, cover, size, threshold=-1.0)
    raise ValueError(f"unknown mode {mode!r}")


def open_source(files: dict) -> Icons:
    return Icons(files["data"])
