"""The player's key bindings, from UT2004's System/User.ini.

The ``[Engine.Input]`` section holds one ``Key=Command`` line per key, as
DefUser.ini writes it for a new player (``Space=Jump``,
``4=SwitchWeapon 4``). The game rewrites User.ini when the player changes a
binding and the settings are saved.
"""
from __future__ import annotations

# UT2004 key names (EInputKey, as User.ini writes them) for the keys that have
# a keycap cell, in the overlay generator's spelling. Letters, digits and
# F1..F12 are the same in both. Mouse, joystick and numeric keypad keys have
# no cell; Ctrl, Shift and Alt are left out because the overlay draws them as
# modifiers.
KEY_NAMES = {
    "tilde": "GRAVE", "minus": "MINUS", "equals": "EQUAL",
    "leftbracket": "LBRACKET", "rightbracket": "RBRACKET", "backslash": "BACKSLASH",
    "semicolon": "SEMICOLON", "singlequote": "QUOTE", "comma": "COMMA",
    "period": "PERIOD", "slash": "SLASH",
    "backspace": "BSPC", "enter": "ENTER", "tab": "TAB", "space": "SPACE",
    "escape": "ESCAPE", "capslock": "CAPS",
    "insert": "INSERT", "delete": "DELETE", "home": "HOME", "end": "END",
    "pageup": "PGUP", "pagedown": "PGDN",
    "up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT",
    "printscrn": "PRTSC", "scrolllock": "SCROLLLOCK", "pause": "PAUSE", "numlock": "NUMLOCK",
}
KEY_NAMES.update({c.lower(): c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"})
KEY_NAMES.update({f"f{n}": f"F{n}" for n in range(1, 13)})

# The largest User.ini read; a stock one is about 12 KB.
MAX_INI = 1024 * 1024


def parse(text: str) -> dict:
    """{command: [key name in the generator's spelling, ...]} from the
    ``[Engine.Input]`` section of `text`. Keys bound to nothing, and keys with
    no keycap cell, are left out. Lines outside the section are ignored."""
    out: dict = {}
    section = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("["):
            section = line.strip("[]").strip().lower()
            continue
        if section != "engine.input" or "=" not in line:
            continue
        key, _, command = line.partition("=")
        name = KEY_NAMES.get(key.strip().lower())
        if name is None or not command.strip():
            continue
        out.setdefault(command.strip(), []).append(name)
    return out
