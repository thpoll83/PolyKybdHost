"""The player's Path of Exile key bindings, from production_Config.ini.

The game writes its options to ``Documents/My Games/Path of Exile/
production_Config.ini`` (``garena_tw_production_Config.ini`` for the Garena
client; on macOS under ``~/Library/Application Support/Path of Exile/
Preferences``). The ``[ACTION_KEYS]`` section has one line per action:
``action=<VK>`` or ``action=<VK> <modifier>``. The first number is a Windows
virtual-key code (0 or empty: unbound; 1, 2, 4 to 6: mouse buttons). The
modifier is 1 for Shift and 2 for Ctrl. Alt is not known for sure: tools that
read the file disagree whether it is 3 or 4, so a binding with any other
modifier value is left out.

The game writes every action it knows, but the set of actions changes with
the game version, so an action missing from the file keeps its default key
(``BINDINGS_COMPLETE``); an action written as 0 is unbound.

Path of Exile 2 uses the same format (``poe2_keys``). Format and folders
from SnosMe/awakened-poe-trade (GameConfig.ts), ParogDev/WhatsARoute
(GameKeys.cs) and 26 player files published on GitHub. Not checked on an
install.

The overlay spec names this source with ``bindings: poe`` in its
``game_assets:`` block.
"""
from __future__ import annotations

from pathlib import Path

from polyhost.services.game_assets import key_files

BINDINGS_COMPLETE = False
MAX_FILE = 1024 * 1024        # the largest file read; a full config is about 10 KB

STEAM_APP = 238960
FOLDER = "Path of Exile"
NAMES = ("production_Config.ini", "garena_tw_production_Config.ini")

# Windows virtual-key codes of the keys that have a keycap cell, in the
# overlay generator's spelling.
VK = {8: "BSPC", 9: "TAB", 13: "ENTER", 19: "PAUSE", 20: "CAPS", 27: "ESCAPE", 32: "SPACE",
      33: "PGUP", 34: "PGDN", 35: "END", 36: "HOME", 37: "LEFT", 38: "UP", 39: "RIGHT", 40: "DOWN",
      44: "PRTSC", 45: "INSERT", 46: "DELETE", 145: "SCROLLLOCK", 186: "SEMICOLON", 187: "EQUAL",
      188: "COMMA", 189: "MINUS", 190: "DOT", 191: "SLASH", 192: "GRAVE", 219: "LBRACKET",
      220: "BACKSLASH", 221: "RBRACKET", 222: "QUOTE"}
VK.update({0x30 + d: str(d) for d in range(10)})
VK.update({0x41 + i: chr(0x41 + i) for i in range(26)})
VK.update({0x70 + n: f"F{n + 1}" for n in range(12)})

MODIFIERS = {0: (), 1: ("SHIFT",), 2: ("CTRL",)}


def candidates(folder: str = FOLDER, names=NAMES, app_id: int = STEAM_APP) -> list[Path]:
    """The config file in My Games under every Documents folder (Windows,
    OneDrive, Wine and the game's Proton prefix), and the macOS one."""
    paths = [d / "My Games" / folder / n for d in key_files.documents_dirs(app_id) for n in names]
    paths += [Path.home() / "Library" / "Application Support" / folder / "Preferences" / n for n in names]
    return paths


def find() -> Path | None:
    """The config file changed last, or None."""
    return key_files.newest(candidates())


def token(value: str) -> str | None:
    """``"81 2"`` -> ``"CTRL+Q"``; None for an unbound action, a mouse button,
    a modifier key, or a modifier value not known."""
    parts = value.split()
    try:
        vk = int(parts[0]) if parts else 0
        mod = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return None
    key = VK.get(vk)
    if key is None or mod not in MODIFIERS:
        return None
    return "+".join(MODIFIERS[mod] + (key,))


def parse(text: str, section: str = "ACTION_KEYS") -> dict:
    """{action: [token]} from one section; an unbound action, or one bound to
    a key with no keycap cell, gives []."""
    out, inside = {}, False
    for raw in text.lstrip("﻿").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            inside = line[1:-1].strip().upper() == section
            continue
        if not inside or "=" not in line:
            continue
        name, _, value = line.partition("=")
        t = token(value)
        out[name.strip()] = [t] if t else []
    return out


def bindings(path, data: bytes | None = None) -> dict | None:
    """The player's bindings from `path`, or None without one."""
    if path is None:
        return None
    return parse(key_files.read_text(path, data, MAX_FILE))
