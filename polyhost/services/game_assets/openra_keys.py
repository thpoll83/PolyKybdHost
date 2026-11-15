"""The player's OpenRA hotkeys, from OpenRA's settings.yaml.

OpenRA keeps a changed hotkey in the ``Keys:`` section of settings.yaml in
its support folder, one line per hotkey, as ``<Name>: <KEY> <Modifiers>``
(``AttackMove: B``, ``ControlGroupCreate01: NUMBER_1 Ctrl, Shift``). A hotkey
at its default is not written, so the file is not a full list
(``BINDINGS_COMPLETE``); a hotkey set to nothing is written with no value.
The section is shared by every mod. Format and folders from OpenRA's
HotkeyManager.cs, Settings.cs and Platform.cs (commit cd20761).

An overlay spec names this source with ``bindings: openra`` in its
``game_assets:`` block; ``build.remap`` then moves each icon whose binding
names a ``command:`` (the OpenRA hotkey name) to the player's key.
"""
from __future__ import annotations

import os
from pathlib import Path

BINDINGS_COMPLETE = False
MAX_SETTINGS = 4 * 1024 * 1024          # the largest settings.yaml read; a stock one is a few KB

# OpenRA's Keycode names (OpenRA.Game/Input/Keycode.cs) for the keys that have
# a keycap cell, in the overlay generator's spelling. Letters and F1..F12 are
# the same in both.
KEYCODES = {
    "RETURN": "ENTER", "ESCAPE": "ESCAPE", "BACKSPACE": "BSPC", "TAB": "TAB", "SPACE": "SPACE",
    "QUOTE": "QUOTE", "COMMA": "COMMA", "MINUS": "MINUS", "PERIOD": "DOT", "SLASH": "SLASH",
    "SEMICOLON": "SEMICOLON", "EQUALS": "EQUAL", "LEFTBRACKET": "LBRACKET",
    "BACKSLASH": "BACKSLASH", "RIGHTBRACKET": "RBRACKET", "BACKQUOTE": "GRAVE",
    "CAPSLOCK": "CAPS", "PRINTSCREEN": "PRTSC", "SCROLLLOCK": "SCROLLLOCK", "PAUSE": "PAUSE",
    "INSERT": "INSERT", "HOME": "HOME", "PAGEUP": "PGUP", "DELETE": "DELETE", "END": "END",
    "PAGEDOWN": "PGDN", "RIGHT": "RIGHT", "LEFT": "LEFT", "DOWN": "DOWN", "UP": "UP",
}
KEYCODES.update({f"NUMBER_{d}": str(d) for d in range(10)})
KEYCODES.update({c: c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"})
KEYCODES.update({f"F{n}": f"F{n}" for n in range(1, 13)})

MODIFIERS = {"CTRL": "CTRL", "ALT": "ALT", "SHIFT": "SHIFT"}   # Meta has no overlay tier


def support_dirs() -> list[Path]:
    """OpenRA's user support folders, newest convention first: %APPDATA% and
    Documents on Windows, Application Support on macOS, $XDG_CONFIG_HOME/openra
    and ~/.openra on Linux, and the Flatpak's config folder."""
    home = Path.home()
    dirs = []
    if os.environ.get("APPDATA"):
        dirs.append(Path(os.environ["APPDATA"]) / "OpenRA")
    dirs.append(home / "Documents" / "OpenRA")
    dirs.append(home / "Library" / "Application Support" / "OpenRA")
    xdg = os.environ.get("XDG_CONFIG_HOME")
    dirs.append((Path(xdg) if xdg else home / ".config") / "openra")
    dirs.append(home / ".openra")
    dirs.append(home / ".var" / "app" / "net.openra.OpenRA" / "config" / "openra")
    return dirs


def find() -> Path | None:
    """The settings.yaml OpenRA uses, or None. The first folder that has one
    wins, as OpenRA takes the first support folder that exists."""
    for d in support_dirs():
        p = d / "settings.yaml"
        if p.is_file():
            return p
    return None


def token(value: str) -> str | None:
    """``"NUMBER_1 Ctrl, Shift"`` -> ``"CTRL+SHIFT+1"``; None for a key with no
    keycap cell or a modifier the overlay does not draw."""
    key, _, mods = value.strip().partition(" ")
    name = KEYCODES.get(key.upper())
    if name is None:
        return None
    parts = []
    for m in (m.strip().upper() for m in mods.split(",") if m.strip()):
        if m not in MODIFIERS:
            return None
        parts.append(MODIFIERS[m])
    return "+".join(sorted(set(parts)) + [name])


def parse(text: str) -> dict:
    """{hotkey name: [token]} from the top-level ``Keys:`` section; a hotkey
    set to nothing, or to a key with no keycap cell, gives []."""
    out, inside, level = {}, False, None
    for raw in text.lstrip("﻿").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = raw[:len(raw) - len(raw.lstrip())]
        if not indent:
            inside, level = raw.split(":", 1)[0].strip() == "Keys", None
            continue
        if not inside:
            continue
        level = level or indent              # the first line under Keys: sets the level
        if indent != level:
            continue                         # a deeper line belongs to a hotkey above
        name, _, value = raw.strip().partition(":")
        if not name:
            continue
        t = token(value) if value.strip() else None
        out[name.strip()] = [t] if t else []
    return out


def bindings(path) -> dict | None:
    """The player's hotkeys from `path` (a settings.yaml), or None without one."""
    if path is None:
        return None
    path = Path(path)
    if path.stat().st_size > MAX_SETTINGS:
        raise ValueError(f"{path.name} is larger than this reader opens")
    return parse(path.read_bytes().decode("utf-8", errors="replace"))
