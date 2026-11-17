"""The player's Team Fortress 2 key binds, from tf/cfg/config.cfg.

The game writes config.cfg in its install folder when it exits
(``host_writeconfig``): ``unbindall``, then one ``bind "<key>" "<command>"``
line for every bound key. So the file lists every bind, and a command with
no line is unbound (``BINDINGS_COMPLETE``). Letters are lower case; the key
names are the Source engine's (``SEMICOLON``, ``PGUP``, ``KP_END``). Before
the first exit there is no config.cfg, and the game runs Valve's
config_default.cfg instead, whose keys the overlay ships.

Format from the engine's own strings (``unbindall\\n``, ``bind "%s" "%s"\\n``)
and tf/cfg/config_default.cfg in SteamDatabase/GameTracking-TF2 (commit
910657b). Not checked on an install.

The overlay spec names this source with ``bindings: tf2`` in its
``game_assets:`` block; ``build.remap`` then moves each icon whose binding
names a ``command:`` (the console command) to the player's key.
"""
from __future__ import annotations

from pathlib import Path

from polyhost.services.game_assets import key_files

BINDINGS_COMPLETE = True
MAX_FILE = 1024 * 1024        # the largest file read; a full config.cfg is about 20 KB

APP_DIR = "Team Fortress 2"


def candidates() -> list[Path]:
    """tf/cfg/config.cfg in every Steam library."""
    return [lib / "steamapps" / "common" / APP_DIR / "tf" / "cfg" / "config.cfg"
            for lib in key_files.steam_libraries()]


def find() -> Path | None:
    """The config.cfg changed last, or None before the game's first exit."""
    return key_files.newest(candidates())


def parse(text: str) -> dict:
    """{command: [token, ...]} from the ``bind`` lines."""
    return key_files.parse_source_binds(text, lambda d: d.lower() == "bind")


def bindings(path, data: bytes | None = None) -> dict | None:
    """The player's binds from `path`, or None without one. `data` is the
    file's content when the caller has read it already."""
    if path is None:
        return None
    return parse(key_files.read_text(path, data, MAX_FILE))
