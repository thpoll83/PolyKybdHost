"""Game-asset reader for StarCraft (1998) and Brood War, version 1.16.1.

Reads the user's own MPQ archives: StarDat.mpq, and BrooDat.mpq and
patch_rt.mpq when present (a file is taken from patch_rt.mpq first, then
BrooDat.mpq, then StarDat.mpq). Nothing read here leaves the machine.

StarCraft: Remastered, and as far as is known every release from 1.18 on,
keeps its data in CASC storage, which this reader does not open: it logs that
and the shipped overlay is used.

The reader knows nothing about keys: an overlay spec's ``game_assets:`` block
says what to draw on each key, as a recipe, and ``build.py`` places the
result. Recipes:

- ``{wireframe: 0}``: frame 0 of ``unit\\wirefram\\wirefram.grp``, the large
  wireframe the status panel shows for one selected unit. The frame number is
  the unit id (Marine 0, Zealot 65, Zergling 37: BWAPI's UnitType list);
- ``{cmdicon: 7}``: frame 7 of ``unit\\cmdbtns\\cmdicons.grp``, the command
  card icons, where a unit's train button uses its unit id too.

Both are drawn like the C&C sprites: the palette grey (``tileset\\badlands.wpe``)
dithered inside, the outline lit (``dither.keycap``). ``flat: true`` lights
every opaque pixel instead, and ``threshold`` (0..1) sets where a scaled pixel
counts as lit for it.

None of this was checked against real StarCraft files: the tests build small
archives and sprites of their own.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
from PIL import Image

from polyhost.services.game_assets import dither
from polyhost.services.game_assets.starcraft import grp, mpq

log = logging.getLogger("PolyHost")

REQUIRED = ("stardat.mpq",)
OPTIONAL = ("broodat.mpq", "patch_rt.mpq")
SEARCH = ("patch_rt.mpq", "broodat.mpq", "stardat.mpq")   # a file is taken from the first

WIREFRAMES = "unit\\wirefram\\wirefram.grp"
CMDICONS = "unit\\cmdbtns\\cmdicons.grp"
PALETTE = "tileset\\badlands.wpe"

SHARP = {"lo_p": 5, "hi_p": 95, "curve": 0.6, "sharpen": 1.5}
INSTALL_NAMES = ("starcraft",)              # the install folder, in any case

_casc_logged: set = set()


# --------------------------------------------------------------------------- #
# finding the files
# --------------------------------------------------------------------------- #

def _listing(d: Path) -> dict:
    """{lower-case name: real name} of the entries in `d`; empty when unreadable."""
    try:
        return {n.lower(): n for n in os.listdir(d)}
    except OSError:
        return {}


def is_casc(d: Path) -> bool:
    """Whether `d` looks like a CASC install (StarCraft: Remastered): a
    .build.info file, or a Data folder holding a data folder."""
    names = _listing(d)
    if ".build.info" in names:
        return True
    data = _listing(d / names["data"]) if "data" in names else {}
    return "data" in data


def data_files(d: Path) -> dict | None:
    """{"stardat.mpq": path, ...} when `d` holds StarDat.mpq, else None. Names
    are matched without regard to case. A CASC install is logged once."""
    names = _listing(d)
    if not all(r in names for r in REQUIRED):
        if names and is_casc(d) and str(d) not in _casc_logged:
            _casc_logged.add(str(d))
            log.info("Game art: the StarCraft install in %s keeps its files in CASC "
                     "(StarCraft: Remastered), which is not read; using the shipped overlay.",
                     _shown(d))
        return None
    return {n: d / names[n] for n in REQUIRED + OPTIONAL if n in names}


def _shown(d: Path) -> str:
    from polyhost.services.game_assets.build import shown_folder
    return shown_folder(d)


def _named(parent: Path) -> list[Path]:
    """The StarCraft folders directly in `parent`, in any case."""
    return [parent / real for low, real in _listing(parent).items() if low in INSTALL_NAMES]


def install_candidates() -> list[Path]:
    """Folders a StarCraft 1.16.1 install may be in: Program Files on Windows,
    Applications on macOS, and the same Program Files in the default Wine
    prefix (or $WINEPREFIX). Not checked on an install."""
    home = Path.home()
    parents = []
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        if os.environ.get(env):
            parents.append(Path(os.environ[env]))
    parents += [Path("/Applications"), home / "Applications"]
    prefixes = [Path(os.environ["WINEPREFIX"])] if os.environ.get("WINEPREFIX") else []
    prefixes.append(home / ".wine")
    for prefix in prefixes:
        parents += [prefix / "drive_c" / "Program Files (x86)", prefix / "drive_c" / "Program Files"]
    return [d for p in parents for d in _named(p)]


def _near(hint) -> list[Path]:
    """The folder of the running game and a StarCraft folder beside any of its
    four nearest parents: StarCraft II runs from
    ``<Program Files>/StarCraft II/Versions/Base<N>/``, and a StarCraft install
    is usually in the same Program Files."""
    if not hint:
        return []
    h = Path(hint)
    out = [h]
    for parent in list(h.parents)[:4]:
        out += _named(parent)
    return out


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

class Source:
    """The archives (searched in SEARCH order) and the palette. A GRP file is
    read from the archive once and cached; frames are decoded as asked for."""

    def __init__(self, archives: list, where: str):
        self.archives, self.where = archives, where
        self._files = {}
        pal = self.get(PALETTE)
        if pal is None:
            raise KeyError(f"{PALETTE} is not in {where}")
        self.pal = grp.wpe_palette(pal)

    def get(self, name: str) -> bytes | None:
        if name not in self._files:
            self._files[name] = next((d for a in self.archives if (d := a.get(name)) is not None), None)
        return self._files[name]

    def frame(self, name: str, i: int) -> np.ndarray:
        data = self.get(name)
        if data is None:
            raise KeyError(f"{name} is not in {self.where}")
        return grp.frame(data, i)

    def grey(self, idx: np.ndarray):
        """(grey 0..1, cover) of a palette-index image; index 0 is empty."""
        cover = idx != 0
        return self.pal[idx].astype(float) @ [0.299, 0.587, 0.114] / 255 * cover, cover


def _crop(*arrays):
    ys, xs = np.nonzero(arrays[-1])
    if not len(ys):
        raise ValueError("the frame is empty")
    sl = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    return [a[sl] for a in arrays]


def _keycap(g, c, size):
    """Upscale the pixel art so the blur and fit see a smooth image, then dither."""
    g, c = _crop(g, c)
    k = max(1, 320 // max(c.shape))
    return dither.keycap(np.kron(g, np.ones((k, k))), np.kron(c, np.ones((k, k), bool)), size, **SHARP)


def _flat(c, size, threshold):
    """Every opaque pixel lit, fitted inside `size`."""
    (c,) = _crop(c)
    s = min(size[0] / c.shape[1], size[1] / c.shape[0])
    w, h = max(1, round(c.shape[1] * s)), max(1, round(c.shape[0] * s))
    k = max(1, 320 // max(c.shape))
    big = Image.fromarray((np.kron(c, np.ones((k, k))) * 255).astype(np.uint8))
    return np.asarray(big.resize((w, h), Image.LANCZOS)) > threshold * 255


# --------------------------------------------------------------------------- #
# the reader interface (build.py)
# --------------------------------------------------------------------------- #

def find(folder: str = "", hint=None) -> dict | None:
    """The game files to read: from `folder` when set; else beside the running
    game (`hint`); else from the usual install folders."""
    if folder:
        return data_files(Path(folder).expanduser())
    for d in _near(hint) + install_candidates():
        files = data_files(d)
        if files:
            return files
    return None


def fingerprint(files: dict) -> list:
    """The files whose size and time key the cached copy."""
    return sorted(files.values())


def open_source(files: dict) -> Source:
    archives = [mpq.Archive.open(files[n]) for n in SEARCH if n in files]
    return Source(archives, ", ".join(Path(files[n]).name for n in SEARCH if n in files))


def draw(src: Source, recipe: dict, size):
    """A boolean mask fitted inside `size` (w, h) for one recipe (see the
    module docstring)."""
    if "wireframe" in recipe:
        idx = src.frame(WIREFRAMES, int(recipe["wireframe"]))
    elif "cmdicon" in recipe:
        idx = src.frame(CMDICONS, int(recipe["cmdicon"]))
    else:
        raise ValueError(f"unknown recipe {recipe!r}")
    if recipe.get("flat"):
        return _flat(idx != 0, size, float(recipe.get("threshold", 0.35)))
    return _keycap(*src.grey(idx), size)
