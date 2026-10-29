"""Game-asset reader for Red Alert (1996).

Reads the user's own classic game files: CONQUER.MIX (unit and building
sprites), HIRES.MIX (infantry and the mouse cursors) and LOCAL.MIX (the
palette). OpenRA's content installer writes them to ``Content/ra/v2/`` (see
``openra.py``). HIRES.MIX and LOCAL.MIX are encrypted (``mix.py``). Nothing
read here leaves the machine.

The sprites use the Tiberian Dawn shape format, so the recipes and the drawing
are those of ``westwood_td/reader.py``: ``unit``, ``crowd``, ``helicopter`` and
``cursor``. The C&C Remastered copy of Red Alert keeps these files nested in
MAIN.MIX and REDALERT.MIX, which this reader does not open.
"""
from __future__ import annotations

from pathlib import Path

from polyhost.services.game_assets import openra
from polyhost.services.game_assets.westwood_ra import mix
from polyhost.services.game_assets.westwood_td import reader as td

REQUIRED = ("conquer.mix", "hires.mix", "local.mix")
PALETTE = "temperat.pal"


def data_files(d: Path) -> dict | None:
    """{"conquer.mix": path, ...} when `d` holds the required MIX files, else
    None. Names are matched without regard to case."""
    names = td._listing(d)
    if not all(r in names for r in REQUIRED):
        return None
    return {n: d / names[n] for n in REQUIRED}


# --------------------------------------------------------------------------- #
# the reader interface (build.py)
# --------------------------------------------------------------------------- #

def find(folder: str = "", hint=None) -> dict | None:
    """The game files to read: from `folder` when set; else from OpenRA's Red
    Alert content folder; else from any folder below OpenRA's content folders
    that has them (a third-party mod such as Combined Arms)."""
    if folder:
        return data_files(Path(folder).expanduser())
    for d in openra.content_dirs("ra/v2", hint) + openra.all_content_dirs(hint):
        files = data_files(d)
        if files:
            return files
    return None


def fingerprint(files: dict) -> list:
    """The files whose size and time key the cached copy."""
    return sorted(files.values())


def open_source(files: dict) -> td.Sprites:
    """The archives in REQUIRED order, each searched for every file."""
    mixes = [mix.read(Path(files[n]).read_bytes()) for n in REQUIRED]
    where = ", ".join(REQUIRED)

    def get(name):
        return next((d for m in mixes if (d := m.get(name)) is not None), None)

    pal = get(PALETTE)
    if pal is None:
        raise KeyError(f"{PALETTE} is not in {where}")
    return td.Sprites(mixes, pal, get("mouse.shp"), where)


draw = td.draw
