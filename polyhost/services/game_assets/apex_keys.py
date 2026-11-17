"""The player's Apex Legends key binds, from local/settings.cfg.

The game keeps its binds in ``Saved Games/Respawn/Apex/local/settings.cfg``
in the Windows user folder, one line per bind:
``bind_US_standard "<key>" "<command>" <slot>``, where the slot is 0 for the
primary and 1 for the alternate key. ``bind_held_US_standard`` lines are the
hold actions, which the overlay does not draw. Key names are the Source
engine's, with ``LSHIFT``, ``LCTRL`` and ``LALT`` for the modifiers.

Respawn documents neither the file nor its defaults. The format is from
settings.cfg files players published on GitHub (240hz/ApexConfigs,
Zazzop/Apex-Legends, salvatorepolverino/ApexLegends-AutoExec-Videoconfig).
Those files list every bound key, but it is not known that a removed bind
is always written, so a command with no line keeps its default key
(``BINDINGS_COMPLETE``). Not checked on an install.

The overlay spec names this source with ``bindings: apex`` in its
``game_assets:`` block.
"""
from __future__ import annotations

import re
from pathlib import Path

from polyhost.services.game_assets import key_files

BINDINGS_COMPLETE = False
MAX_FILE = 1024 * 1024        # the largest file read; a full settings.cfg is about 20 KB

STEAM_APP = 1172470
_DIRECTIVE = re.compile(r"bind_(?!held_)\w*standard", re.IGNORECASE)


def candidates() -> list[Path]:
    """local/settings.cfg under Saved Games in each Windows user folder,
    including Steam's Proton prefix of the game."""
    return [h / "Saved Games" / "Respawn" / "Apex" / "local" / "settings.cfg"
            for h in key_files.windows_homes(STEAM_APP)]


def find() -> Path | None:
    """The settings.cfg changed last, or None."""
    return key_files.newest(candidates())


def parse(text: str) -> dict:
    """{command: [token, ...]} from the ``bind_<layout>_standard`` lines."""
    return key_files.parse_source_binds(text, lambda d: bool(_DIRECTIVE.fullmatch(d)))


def bindings(path, data: bytes | None = None) -> dict | None:
    """The player's binds from `path`, or None without one."""
    if path is None:
        return None
    return parse(key_files.read_text(path, data, MAX_FILE))
