"""The folders where OpenRA keeps the original game files it installs.

OpenRA's content installer writes the classic MIX files to ``Content/<mod>/``
in its support folder: ``Content/cnc/`` for Tiberian Dawn, ``Content/ra/v2/``
for Red Alert. The support folder is ``%APPDATA%\\OpenRA`` on Windows,
``~/Library/Application Support/OpenRA`` on macOS and ``~/.config/openra`` on
Linux (``~/.openra`` before 2023). Flatpak and Snap packages keep their own
copy of the Linux folder, and a portable install a ``Support`` folder beside
the game.
"""
from __future__ import annotations

import os
from pathlib import Path


def support_dirs(hint=None) -> list[Path]:
    """Every OpenRA support folder that may exist here, the portable one of the
    install in `hint` (the game's folder) first."""
    home = Path.home()
    dirs = [Path(hint) / "Support"] if hint else []
    if os.environ.get("APPDATA"):
        dirs.append(Path(os.environ["APPDATA"]) / "OpenRA")
    dirs.append(home / "Library" / "Application Support" / "OpenRA")
    xdg = os.environ.get("XDG_CONFIG_HOME")
    dirs.append((Path(xdg) if xdg else home / ".config") / "openra")
    dirs.append(home / ".openra")
    dirs.extend(sorted((home / ".var" / "app").glob("*/config/openra")))
    dirs.extend(sorted((home / "snap").glob("*/current/.config/openra")))
    seen, out = set(), []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def content_dirs(mod_path: str, hint=None) -> list[Path]:
    """``Content/<mod_path>`` of each support folder, e.g. ``cnc`` or ``ra/v2``."""
    return [d / "Content" / mod_path for d in support_dirs(hint)]


def all_content_dirs(hint=None, depth: int = 3) -> list[Path]:
    """Every folder up to `depth` levels below each ``Content`` folder, for mods
    whose content folder is not known (third-party mods such as Combined Arms)."""
    out = []
    for root in (d / "Content" for d in support_dirs(hint)):
        level = [root]
        for _ in range(depth):
            nxt = []
            for d in level:
                try:
                    nxt.extend(sorted(p for p in d.iterdir() if p.is_dir()))
                except OSError:
                    continue
            out.extend(nxt)
            level = nxt
    return out
