"""Shared parts of the key-binding sources for games installed through Steam
or the game's own launcher: where a Windows user folder can be on this
machine, and the bind format of the Source engine games.

Used by ``tf2_keys``, ``apex_keys``, ``poe_keys`` and ``poe2_keys``. Each of
them has ``find()``, ``bindings(path, data)`` and ``BINDINGS_COMPLETE``, as
``build.bindings_source`` expects.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# The overlay generator's spelling of the keys that have a keycap cell, for a
# Source engine key name (Team Fortress 2 tf/cfg/config.cfg; Apex Legends
# settings.cfg uses the same names). Letters and digits are written in lower
# case by the game; the lookup ignores case.
SOURCE_KEYS = {
    "SPACE": "SPACE", "TAB": "TAB", "ENTER": "ENTER", "ESCAPE": "ESCAPE", "BACKSPACE": "BSPC",
    "CAPSLOCK": "CAPS", "SCROLLLOCK": "SCROLLLOCK", "PAUSE": "PAUSE", "INS": "INSERT",
    "DEL": "DELETE", "HOME": "HOME", "END": "END", "PGUP": "PGUP", "PGDN": "PGDN",
    "UPARROW": "UP", "DOWNARROW": "DOWN", "LEFTARROW": "LEFT", "RIGHTARROW": "RIGHT",
    "UP": "UP", "DOWN": "DOWN", "LEFT": "LEFT", "RIGHT": "RIGHT",
    "SEMICOLON": "SEMICOLON", "'": "QUOTE", "`": "GRAVE", ",": "COMMA", ".": "DOT",
    "/": "SLASH", "\\": "BACKSLASH", "-": "MINUS", "=": "EQUAL", "[": "LBRACKET", "]": "RBRACKET",
}
SOURCE_KEYS.update({c: c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"})
SOURCE_KEYS.update({f"F{n}": f"F{n}" for n in range(1, 13)})

# `bind "key" "command"` (TF2) and `bind_US_standard "key" "command" 0` (Apex).
# The key may be written without quotes; a backslash may be escaped as "\\"
# (`source_token` unescapes it). Each quoted part is one `[^"]*` run, with no
# alternation that could match the same characters two ways: a line of many
# backslashes and no closing quote then costs linear time, not exponential
# (CodeQL py/redos on PolyKybdHost#916).
_BIND = re.compile(r'^\s*(bind\w*)\s+(?:"([^"]*)"|([^\s"]+))\s+"([^"]*)"')


def source_token(name: str) -> str | None:
    """The generator's key name for a Source key name, or None for a key with
    no keycap cell (mouse, keypad, the modifier keys)."""
    name = name.replace("\\\\", "\\")
    return SOURCE_KEYS.get(name.upper())


def parse_source_binds(text: str, directive) -> dict:
    """{command: [token, ...]} from Source engine bind lines. `directive(name)`
    says whether a line's first word is a bind to read (``bind`` for TF2,
    ``bind_US_standard`` but not ``bind_held_US_standard`` for Apex). A key
    bound to several commands with ``;`` counts for each of them, so a
    player's ``+jump; exec x.cfg`` still names ``+jump``. Keys with no keycap
    cell are left out, but their command is kept: a command bound only to the
    mouse, the keypad or a gamepad gives [], so its default key is cleared
    even where the file is not a complete list (Apex)."""
    out: dict = {}
    for line in text.lstrip("﻿").splitlines():
        m = _BIND.match(line)
        if not m or not directive(m.group(1)):
            continue
        token = source_token(m.group(2) if m.group(2) is not None else m.group(3))
        for part in m.group(4).split(";"):
            command = " ".join(part.split())
            if not command:
                continue
            keys = out.setdefault(command, [])
            if token is not None and token not in keys:
                keys.append(token)
    return out


def read_text(path, data: bytes | None, limit: int) -> str:
    """The file's text (UTF-8, damaged bytes replaced), refused above `limit`
    bytes. `data` is the content when the caller has read it already."""
    path = Path(path)
    size = path.stat().st_size if data is None else len(data)
    if size > limit:
        raise ValueError(f"{path.name} is larger than this reader opens")
    if data is None:
        data = path.read_bytes()
    return data.decode("utf-8", errors="replace")


def steam_libraries() -> list[Path]:
    """Every Steam library folder on this machine."""
    from polyhost.services.game_assets.westwood_td.reader import _steam_libraries
    return _steam_libraries()


def windows_homes(app_id: int | None = None) -> list[Path]:
    """Folders that can hold a Windows user's Documents and Saved Games: the
    user's home on Windows, the Wine prefix ($WINEPREFIX or ~/.wine), and the
    Proton prefix of Steam app `app_id` in each Steam library."""
    home = Path.home()
    homes = []
    if os.environ.get("USERPROFILE"):
        homes.append(Path(os.environ["USERPROFILE"]))
    homes.append(home)
    prefixes = [Path(os.environ["WINEPREFIX"])] if os.environ.get("WINEPREFIX") else []
    prefixes.append(home / ".wine")
    if app_id is not None:
        prefixes += [lib / "steamapps" / "compatdata" / str(app_id) / "pfx" for lib in steam_libraries()]
    for prefix in prefixes:
        users = prefix / "drive_c" / "users"
        homes += sorted(p for p in users.glob("*") if p.name.lower() != "public") if users.is_dir() else []
    seen, out = set(), []
    for h in homes:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def documents_dirs(app_id: int | None = None) -> list[Path]:
    """Documents and OneDrive/Documents under every folder of
    `windows_homes`."""
    return [h / d for h in windows_homes(app_id) for d in ("Documents", Path("OneDrive") / "Documents")]


def newest(paths) -> Path | None:
    """The most recently changed file of `paths` that exists, or None. The
    game was last played with that one."""
    found = [p for p in paths if p.is_file()]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None
