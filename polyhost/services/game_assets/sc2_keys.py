"""The player's StarCraft II hotkeys, from the active ``.SC2Hotkeys`` profile.

StarCraft II keeps a custom hotkey profile as
``Accounts/<account>/Hotkeys/<name>.SC2Hotkeys`` in its user folder, and the
name of the active one as ``hotkeyprofile=<name>`` in ``Variables.txt`` there.
A built-in profile has a name that starts with ``0_`` (``0_Default``) and no
file, so its keys are the defaults the overlay ships.

A profile file is INI text. The ``[Hotkeys]`` section holds the global
hotkeys (``ControlGroupRecall1=1``, ``CameraSave0=Control+F5``), the
``[Commands]`` section the unit abilities, which the overlay does not draw.
Modifiers are joined with ``+`` in any order, a command with more keys lists
them with commas, and an empty value is unbound. Only the hotkeys that differ
from the base profile are written (``BINDINGS_COMPLETE``).

Format from TheCoreLite's ``Defaults.ini`` and a user profile in it
(github.com/supercowz/TheCoreLite), and the parser of
github.com/jcfieldsdev/starcraft2-hotkey-editor. Not checked on an install.

An overlay spec names this source with ``bindings: sc2`` in its
``game_assets:`` block; ``build.remap`` then moves each icon whose binding
names a ``command:`` (the ``[Hotkeys]`` name) to the player's key.
"""
from __future__ import annotations

import os
from pathlib import Path

BINDINGS_COMPLETE = False
MAX_FILE = 1024 * 1024        # the largest file read; a full profile is about 60 KB

# StarCraft II key names for the keys that have a keycap cell, in the overlay
# generator's spelling. Letters, digits and F1..F12 are the same in both.
KEYS = {
    "BACKSPACE": "BSPC", "TAB": "TAB", "ENTER": "ENTER", "ESCAPE": "ESCAPE", "SPACE": "SPACE",
    "CAPSLOCK": "CAPS", "PAUSE": "PAUSE", "INSERT": "INSERT", "DELETE": "DELETE", "HOME": "HOME",
    "END": "END", "PAGEUP": "PGUP", "PAGEDOWN": "PGDN", "LEFT": "LEFT", "UP": "UP",
    "RIGHT": "RIGHT", "DOWN": "DOWN", "PRINTSCREEN": "PRTSC", "SCROLLLOCK": "SCROLLLOCK",
    "GRAVE": "GRAVE", "MINUS": "MINUS", "EQUALS": "EQUAL", "BRACKETOPEN": "LBRACKET",
    "BRACKETCLOSE": "RBRACKET", "BACKSLASH": "BACKSLASH", "SEMICOLON": "SEMICOLON",
    "APOSTROPHE": "QUOTE", "COMMA": "COMMA", "PERIOD": "DOT", "SLASH": "SLASH",
}
KEYS.update({c: c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"})
KEYS.update({f"F{n}": f"F{n}" for n in range(1, 13)})

MODIFIERS = {"CONTROL": "CTRL", "ALT": "ALT", "SHIFT": "SHIFT"}


def user_dirs() -> list[Path]:
    """StarCraft II user folders: Documents on Windows (also under OneDrive),
    Application Support on macOS, and Documents in the default Wine prefix
    (or $WINEPREFIX) and a Lutris prefix under ~/Games."""
    home = Path.home()
    docs = [home / "Documents", home / "OneDrive" / "Documents"]
    if os.environ.get("USERPROFILE"):
        docs.insert(0, Path(os.environ["USERPROFILE"]) / "Documents")
    dirs = [d / "StarCraft II" for d in docs]
    dirs.append(home / "Library" / "Application Support" / "Blizzard" / "StarCraft II")
    prefixes = [Path(os.environ["WINEPREFIX"])] if os.environ.get("WINEPREFIX") else []
    prefixes.append(home / ".wine")
    prefixes += sorted((home / "Games").glob("*starcraft*")) if (home / "Games").is_dir() else []
    for prefix in prefixes:
        dirs += sorted((prefix / "drive_c" / "users").glob("*/Documents/StarCraft II"))
    seen, out = set(), []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def active_profile(variables: Path) -> str | None:
    """The ``hotkeyprofile=`` value of a Variables.txt, or None."""
    if variables.stat().st_size > MAX_FILE:
        raise ValueError(f"{variables.name} is larger than this reader opens")
    for line in variables.read_bytes().decode("utf-8", errors="replace").splitlines():
        name, _, value = line.lstrip("﻿").partition("=")
        if name.strip().lower() == "hotkeyprofile":
            return value.strip() or None
    return None


def profile_file(user_dir: Path, profile: str) -> Path | None:
    """The newest ``<profile>.SC2Hotkeys`` under ``Accounts/*/Hotkeys`` (one
    per account; the game was last played with the newest), or None. A
    region folder between the account and Hotkeys is searched too."""
    want = f"{profile}.sc2hotkeys".lower()
    accounts = user_dir / "Accounts"
    found = [p for pattern in ("*/Hotkeys/*", "*/*/Hotkeys/*") for p in accounts.glob(pattern)
             if p.name.lower() == want and p.is_file()]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def find() -> Path | None:
    """The active custom hotkey profile, or None for a built-in one or no
    install. The first user folder with a Variables.txt is used."""
    for d in user_dirs():
        variables = d / "Variables.txt"
        if not variables.is_file():
            continue
        profile = active_profile(variables)
        if not profile or profile.startswith("0_"):
            return None
        return profile_file(d, profile)
    return None


def token(value: str) -> str | None:
    """``"Shift+Alt+5"`` -> ``"ALT+SHIFT+5"``; None for a key with no keycap
    cell (mouse, keypad, media) or a value that is only modifiers."""
    parts = [p.strip().upper() for p in value.split("+") if p.strip()]
    if not parts:
        return None
    *mods, key = parts
    name = KEYS.get(key)
    if name is None or any(m not in MODIFIERS for m in mods):
        return None
    return "+".join(sorted({MODIFIERS[m] for m in mods}) + [name])


def parse(text: str) -> dict:
    """{hotkey name: [token, ...]} from the ``[Hotkeys]`` section; an empty
    value, or one with only keys that have no keycap cell, gives []."""
    out, inside = {}, False
    for raw in text.lstrip("﻿").splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "//")):
            continue
        if line.startswith("[") and line.endswith("]"):
            inside = line[1:-1].strip().lower() == "hotkeys"
            continue
        if not inside or "=" not in line:
            continue
        name, _, value = line.partition("=")
        tokens = [t for t in (token(v) for v in value.split(",")) if t]
        out[name.strip()] = list(dict.fromkeys(tokens))
    return out


def bindings(path) -> dict | None:
    """The player's hotkeys from `path` (an .SC2Hotkeys file), or None without one."""
    if path is None:
        return None
    path = Path(path)
    if path.stat().st_size > MAX_FILE:
        raise ValueError(f"{path.name} is larger than this reader opens")
    return parse(path.read_bytes().decode("utf-8", errors="replace"))
