"""Game-asset reader for Unreal Tournament 2004.

Reads the user's own install: the HUD texture ``Generic.HUD`` in
``Textures/HudContent.utx``, and where each weapon's picture is on it, the
``IconCoords`` default of the weapon's class in ``System/XWeapons.u`` (and
``System/Onslaught.u`` for the Onslaught weapons). Nothing read here leaves
the machine.

The reader knows nothing about keys: the overlay spec's ``game_assets:``
block says what to draw on each key, as a recipe, and ``build.py`` places it:

- ``{weapon: ShockRifle}``: the weapon bar picture of that class, from
  XWeapons.u. ``package: Onslaught.u`` reads the class from that file.

``bindings()`` reads the player's key bindings from System/User.ini, so the
build moves each icon to the keys the player bound its command to
(``build.remap``).

The picture is drawn like the C&C sprites (``dither.keycap``): the grey
dithered inside, the outline lit. The game draws a dark glow round each
weapon, so the cover is eroded by ``erode`` px (default 1) first. The result
is right-aligned and centred in height in the key's area.

Checked on the UT2004 3369 files (HudContent.utx, XWeapons.u, Onslaught.u).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from polyhost.services.game_assets import dither
from polyhost.services.game_assets.unreal2 import dxt
from polyhost.services.game_assets.unreal2.bindings import MAX_INI, parse
from polyhost.services.game_assets.unreal2.package import Package

TEXTURES = ("textures", "hudcontent.utx")
WEAPONS = ("system", "xweapons.u")
OPTIONAL = {"onslaught.u": ("system", "onslaught.u"), "user.ini": ("system", "user.ini")}

SHARP = {"lo_p": 5, "hi_p": 95, "curve": 0.6, "sharpen": 1.5}
ALPHA = 0.5                      # a pixel belongs to the weapon from this alpha on
INSTALL_NAMES = ("ut2004", "unreal tournament 2004")


# --------------------------------------------------------------------------- #
# finding the files
# --------------------------------------------------------------------------- #

def _listing(d: Path) -> dict:
    """{lower-case name: real name} of the entries in `d`; empty when unreadable."""
    try:
        return {n.lower(): n for n in os.listdir(d)}
    except OSError:
        return {}


def _file(root: Path, sub: str, name: str) -> Path | None:
    """root/sub/name, matched without regard to case, or None."""
    top = _listing(root)
    if sub not in top:
        return None
    inner = _listing(root / top[sub])
    return root / top[sub] / inner[name] if name in inner else None


def data_files(root: Path) -> dict | None:
    """{"hudcontent.utx": path, "xweapons.u": path, ...} when `root` is a
    UT2004 install, else None."""
    tex, weap = _file(root, *TEXTURES), _file(root, *WEAPONS)
    if tex is None or weap is None:
        return None
    files = {"hudcontent.utx": tex, "xweapons.u": weap}
    for key, (sub, name) in OPTIONAL.items():
        p = _file(root, sub, name)
        if p is not None:
            files[key] = p
    return files


def _named(parent: Path) -> list[Path]:
    """The UT2004 folders directly in `parent`, in any case."""
    return [parent / real for low, real in _listing(parent).items() if low in INSTALL_NAMES]


def install_candidates() -> list[Path]:
    """Folders a UT2004 install may be in: the retail installer's C:\\UT2004,
    Program Files and Steam on Windows, the Linux installer's
    /usr/local/games, /Applications on macOS, and the same Windows folders in
    the default Wine prefix (or $WINEPREFIX). Not checked on an install."""
    home = Path.home()
    parents = []
    for env in ("SYSTEMDRIVE",):
        if os.environ.get(env):
            parents.append(Path(os.environ[env] + os.sep))
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        if os.environ.get(env):
            parents += [Path(os.environ[env]), Path(os.environ[env]) / "Steam" / "steamapps" / "common"]
    parents += [Path("/usr/local/games"), home, Path("/Applications"), home / "Applications",
                home / ".steam" / "steam" / "steamapps" / "common",
                home / ".local" / "share" / "Steam" / "steamapps" / "common"]
    prefixes = [Path(os.environ["WINEPREFIX"])] if os.environ.get("WINEPREFIX") else []
    prefixes.append(home / ".wine")
    for prefix in prefixes:
        parents += [prefix / "drive_c", prefix / "drive_c" / "Program Files (x86)",
                    prefix / "drive_c" / "Program Files"]
    return [d for p in parents for d in _named(p)]


def _near(hint) -> list[Path]:
    """The game's own folder: UT2004.exe runs from <install>/System."""
    if not hint:
        return []
    h = Path(hint)
    return [h.parent, h]


def searched(hint=None) -> list[Path]:
    return _near(hint) + install_candidates()


def find(folder: str = "", hint=None) -> dict | None:
    """The game files to read: from `folder` when set (the install folder or
    its System folder); else beside the running game (`hint`); else from the
    usual install folders."""
    if folder:
        d = Path(folder).expanduser()
        return data_files(d) or data_files(d.parent)
    for d in searched(hint):
        files = data_files(d)
        if files:
            return files
    return None


def bindings(files: dict) -> dict | None:
    """{command: [key, ...]} from the player's User.ini, or None without one
    (``bindings.parse``)."""
    path = files.get("user.ini")
    if path is None:
        return None
    if os.path.getsize(path) > MAX_INI:
        raise ValueError(f"{Path(path).name} is larger than a User.ini this reader opens")
    with open(path, "rb") as f:
        return parse(f.read().decode("latin-1"))


def fingerprint(files: dict) -> list:
    """The files whose size and time key the cached copy."""
    return sorted(files.values())


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

class Source:
    """The packages, opened on first use, and the decoded HUD textures."""

    def __init__(self, files: dict):
        self.files = files
        self._packages, self._textures = {}, {}

    def package(self, key: str) -> Package:
        key = key.lower()
        if key not in self._packages:
            if key not in self.files:
                raise KeyError(f"{key} is not in this install")
            self._packages[key] = Package.open(self.files[key])
        return self._packages[key]

    def texture(self, path: str) -> np.ndarray:
        """RGBA of a texture in HudContent.utx; `path` is the material's name as
        a weapon class names it (``HUDContent.Generic.HUD``)."""
        pkg, _, inner = path.partition(".")
        if pkg.lower() != "hudcontent":
            raise KeyError(f"{path} is not in HudContent.utx")
        if inner not in self._textures:
            self._textures[inner] = dxt.decode(*self.package("hudcontent.utx").texture(inner))
        return self._textures[inner]


def open_source(files: dict) -> Source:
    return Source(files)


def picture(src: Source, recipe: dict) -> np.ndarray:
    """The RGBA weapon bar picture of the recipe's weapon class."""
    pkg = src.package(str(recipe.get("package", "xweapons.u")))
    cls = str(recipe["weapon"])
    box = pkg.class_default(cls, "IconCoords")
    material = pkg.class_default(cls, "IconMaterial")
    if not isinstance(box, dict) or not material:
        raise KeyError(f"{cls} has no weapon bar picture in {pkg.where}")
    tex = src.texture(material)
    x1, y1, x2, y2 = (int(box.get(k, 0)) for k in ("X1", "Y1", "X2", "Y2"))
    x1, x2 = sorted((max(0, x1), min(tex.shape[1], x2)))
    y1, y2 = sorted((max(0, y1), min(tex.shape[0], y2)))
    if x2 - x1 < 4 or y2 - y1 < 4:
        raise ValueError(f"{cls}'s picture is {x2 - x1}x{y2 - y1} px")
    return tex[y1:y2, x1:x2]


def draw(src: Source, recipe: dict, size):
    """A boolean mask of `size` (w, h) for one recipe (see the module docstring)."""
    if "weapon" not in recipe:
        raise ValueError(f"unknown recipe {recipe!r}")
    rgba = picture(src, recipe).astype(float) / 255
    cover = rgba[:, :, 3] > ALPHA
    if not cover.any():
        raise ValueError(f"{recipe['weapon']}'s picture is empty")
    grey = rgba[:, :, :3] @ [0.299, 0.587, 0.114]
    # Upscale the small picture so the blur and fit see a smooth image.
    k = max(1, 320 // max(cover.shape))
    m = dither.keycap(np.kron(grey, np.ones((k, k))), np.kron(cover, np.ones((k, k), bool)),
                      size, erode=int(recipe.get("erode", 1)), **SHARP)
    ys, xs = np.nonzero(m)                  # the eroded rim leaves empty rows and columns
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    out = np.zeros((size[1], size[0]), bool)
    h, w = min(m.shape[0], size[1]), min(m.shape[1], size[0])
    top = (size[1] - h) // 2
    out[top:top + h, size[0] - w:] = m[:h, :w]
    return out
