"""The Steam library folders on this machine, for every reader that looks for a
Steam install (``westwood_td``, ``factorio``).

A Steam root lists its other library folders in
``steamapps/libraryfolders.vdf``; each library keeps its games in
``steamapps/common/<game>``.
"""
from __future__ import annotations

import os
from pathlib import Path


def roots() -> list[Path]:
    """The folders Steam itself may be installed in, on Linux (native and
    Flatpak), macOS and Windows."""
    home = Path.home()
    out = [home / ".steam" / "steam", home / ".local" / "share" / "Steam",
           home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
           home / "Library" / "Application Support" / "Steam"]
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        if os.environ.get(env):
            out.append(Path(os.environ[env]) / "Steam")
    return out


def libraries() -> list[Path]:
    """Every Steam root and every library folder named in its libraryfolders.vdf."""
    libs = []
    for root in roots():
        vdf = root / "steamapps" / "libraryfolders.vdf"
        libs.append(root)
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            parts = line.strip().split('"')
            if len(parts) >= 4 and parts[1] == "path":
                libs.append(Path(parts[3].replace("\\\\", "\\")))
    return libs
