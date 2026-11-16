"""The player's Path of Exile 2 key bindings, from poe2_production_Config.ini.

Same format as Path of Exile 1 (``poe_keys``), in ``Documents/My Games/Path
of Exile 2/poe2_production_Config.ini``. Path of Exile 2 has two sets of
bindings: ``[ACTION_KEYS]`` for mouse movement and ``[WASD_ACTION_KEYS]`` for
moving with W A S D. ``user_input_mode=wasd`` in ``[GENERAL]`` selects the
second set; the overlay ships the first.

The overlay spec names this source with ``bindings: poe2`` in its
``game_assets:`` block.
"""
from __future__ import annotations

from pathlib import Path

from polyhost.services.game_assets import key_files, poe_keys

BINDINGS_COMPLETE = False
MAX_FILE = poe_keys.MAX_FILE

STEAM_APP = 2694490
FOLDER = "Path of Exile 2"
NAMES = ("poe2_production_Config.ini",)


def find() -> Path | None:
    """The config file changed last, or None."""
    return key_files.newest(poe_keys.candidates(FOLDER, NAMES, STEAM_APP))


def input_mode(text: str) -> str:
    """The ``user_input_mode`` of the ``[GENERAL]`` section, lower case, or ""."""
    inside = False
    for raw in text.lstrip("﻿").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            inside = line[1:-1].strip().upper() == "GENERAL"
        elif inside and line.partition("=")[0].strip().lower() == "user_input_mode":
            return line.partition("=")[2].strip().lower()
    return ""


def parse(text: str) -> dict:
    """{action: [token]} from the section the input mode selects."""
    section = "WASD_ACTION_KEYS" if input_mode(text) == "wasd" else "ACTION_KEYS"
    return poe_keys.parse(text, section)


def bindings(path, data: bytes | None = None) -> dict | None:
    """The player's bindings from `path`, or None without one."""
    if path is None:
        return None
    return parse(key_files.read_text(path, data, MAX_FILE))
