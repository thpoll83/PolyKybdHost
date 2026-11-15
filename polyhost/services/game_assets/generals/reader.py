"""Game-asset reader for Command & Conquer Generals and Zero Hour.

Reads no pictures: it reads the key assignments of the installed game, so the
overlay's icons sit on the keys the installed language and the player's own
files use (``build.remap``). Each binding in ``generals.yaml`` names its
command as the game does:

- ``SELECT_TEAM1``, ``STOP`` and the other ``CommandMap`` blocks: the game
  reads ``Data\\<Language>\\CommandMap.ini`` and then
  ``Data\\INI\\CommandMap.ini``; a field the second file sets replaces the
  first one's (``SubsystemInterface.cpp``, ``MetaEvent.cpp``);
- ``CONTROLBAR:AttackMove`` and the other command-card buttons: the letter
  after the ``&`` in the button's text, from ``Data\\<Language>\\Generals.csf``,
  or from ``Data\\Generals.str`` when that file exists (``GameText.cpp``,
  ``HotKey.cpp``).

A loose file in the install folder replaces the copy in the BIG archives
(``FileSystem.cpp`` opens local files first), which is how players change
their hotkeys. The language is the one whose archive is in the folder
(``EnglishZH.big``, ``GermanZH.big``; ``English.big`` for Generals), or the
``Language`` value in the game's registry key on Windows when there are
several. Behaviour from EA's source release of Generals and Zero Hour (2025);
checked on the English files of the Steam release of Zero Hour. Nothing read
here leaves the machine.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

from polyhost.services.game_assets.generals import big, strings

log = logging.getLogger("PolyHost")

LANGUAGES = ("english", "german", "french", "spanish", "italian", "korean", "chinese",
             "brazilian", "polish")
MAX_TEXT = 4 * 1024 * 1024       # the largest text file read; Generals.csf is about 1 MB

# The game's key names (KEY_* in MetaEvent.h) for the keys that have a keycap
# cell, in the overlay generator's spelling. Letters, digits and F1..F12 are
# the same in both; the keypad and KEY_NONE give no key.
KEYS = {
    "ESC": "ESCAPE", "BACKSPACE": "BSPC", "ENTER": "ENTER", "SPACE": "SPACE", "TAB": "TAB",
    "MINUS": "MINUS", "EQUAL": "EQUAL", "LBRACKET": "LBRACKET", "RBRACKET": "RBRACKET",
    "SEMICOLON": "SEMICOLON", "APOSTROPHE": "QUOTE", "TICK": "GRAVE", "BACKSLASH": "BACKSLASH",
    "COMMA": "COMMA", "PERIOD": "DOT", "SLASH": "SLASH", "UP": "UP", "DOWN": "DOWN",
    "LEFT": "LEFT", "RIGHT": "RIGHT", "HOME": "HOME", "END": "END", "PGUP": "PGUP",
    "PGDN": "PGDN", "INS": "INSERT", "DEL": "DELETE",
}
KEYS.update({c: c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"})
KEYS.update({f"F{n}": f"F{n}" for n in range(1, 13)})

MODIFIERS = {"NONE": (), "CTRL": ("CTRL",), "ALT": ("ALT",), "SHIFT": ("SHIFT",),
             "CTRL_ALT": ("ALT", "CTRL"), "SHIFT_CTRL": ("CTRL", "SHIFT"),
             "SHIFT_ALT": ("ALT", "SHIFT"), "SHIFT_ALT_CTRL": ("ALT", "CTRL", "SHIFT")}

INSTALL_HINTS = ("generals", "zero hour")      # words in an install folder's name

# The game files list the keys of their own commands only, so a command the
# reader did not find is unknown, not unbound (build.remap).
BINDINGS_COMPLETE = False


# --------------------------------------------------------------------------- #
# finding the files
# --------------------------------------------------------------------------- #

def _listing(d: Path) -> dict:
    """{lower-case name: real name} of the entries in `d`; empty when unreadable."""
    try:
        return {n.lower(): n for n in os.listdir(d)}
    except OSError:
        return {}


def _registry_language() -> str | None:
    """The ``Language`` value of the game's registry key (Zero Hour, then
    Generals), on Windows only."""
    if sys.platform != "win32":
        return None
    import winreg
    for sub in ("Command and Conquer Generals Zero Hour", "Generals"):
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for base in ("SOFTWARE\\Electronic Arts\\EA Games\\",
                         "SOFTWARE\\WOW6432Node\\Electronic Arts\\EA Games\\"):
                try:
                    with winreg.OpenKey(root, base + sub) as key:
                        value, _ = winreg.QueryValueEx(key, "Language")
                    return str(value).strip().lower() or None
                except OSError:
                    continue
    return None


def language_archives(names: dict) -> dict:
    """{language: lower-case archive name} of the language archives in a
    listing; a Zero Hour archive (``EnglishZH.big``) takes priority over a
    Generals one (``English.big``)."""
    out = {}
    for lang in LANGUAGES:
        for name in (f"{lang}zh.big", f"{lang}.big"):
            if name in names:
                out[lang] = name
                break
    return out


def _loose(d: Path, *parts: str) -> Path | None:
    """The file at `d`/`parts`, each part matched without regard to case."""
    for part in parts:
        real = _listing(d).get(part.lower())
        if real is None:
            return None
        d = d / real
    return d if d.is_file() else None


def data_files(d: Path, language: str | None = None) -> dict | None:
    """The files to read in install folder `d`, or None when it holds no
    language archive: ``lang.big`` and, when present, ``ini.big``
    (INIZH.big or INI.big) and the loose files that replace their copies."""
    names = _listing(d)
    archives = language_archives(names)
    if not archives:
        return None
    language = language if language in archives else (
        "english" if "english" in archives and len(archives) > 1 else next(iter(archives)))
    files = {"lang.big": d / names[archives[language]]}
    for ini in ("inizh.big", "ini.big"):
        if ini in names:
            files["ini.big"] = d / names[ini]
            break
    for key, parts in (("lang/commandmap.ini", ("Data", language, "CommandMap.ini")),
                       ("ini/commandmap.ini", ("Data", "INI", "CommandMap.ini")),
                       ("lang/generals.csf", ("Data", language, "Generals.csf")),
                       ("generals.str", ("Data", "Generals.str"))):
        if (p := _loose(d, *parts)) is not None:
            files[key] = p
    return files


def _steam_libraries() -> list[Path]:
    from polyhost.services.game_assets.westwood_td.reader import (
        _steam_libraries as libs,
    )
    return libs()


def install_candidates() -> list[Path]:
    """Folders a Generals or Zero Hour install may be in: the folders whose
    name has "generals" or "zero hour" in Program Files (and its EA Games
    folder), the Steam libraries and the default Wine prefix (or
    $WINEPREFIX), and one level below them. Not checked on an install."""
    home = Path.home()
    parents = [lib / "steamapps" / "common" for lib in _steam_libraries()]
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        if os.environ.get(env):
            parents += [Path(os.environ[env]), Path(os.environ[env]) / "EA Games"]
    prefixes = [Path(os.environ["WINEPREFIX"])] if os.environ.get("WINEPREFIX") else []
    prefixes.append(home / ".wine")
    for prefix in prefixes:
        for pf in ("Program Files (x86)", "Program Files"):
            parents += [prefix / "drive_c" / pf, prefix / "drive_c" / pf / "EA Games"]
    out = []
    for parent in parents:
        for low, real in _listing(parent).items():
            if any(w in low for w in INSTALL_HINTS):
                d = parent / real
                out.append(d)
                out += [d / r for lo, r in _listing(d).items() if any(w in lo for w in INSTALL_HINTS)]
    return out


def searched(hint=None) -> list[Path]:
    """Game.dat runs from the install folder."""
    return ([Path(hint)] if hint else []) + install_candidates()


def find(folder: str = "", hint=None) -> dict | None:
    """The game files to read: from `folder` when set; else beside the running
    game (`hint`); else from the usual install folders. A Zero Hour install is
    preferred to a Generals one."""
    language = _registry_language()
    if folder:
        return data_files(Path(folder).expanduser(), language)
    found = [f for d in searched(hint) if (f := data_files(d, language))]
    zh = [f for f in found if f["lang.big"].name.lower().endswith("zh.big")]
    if hint and found and found[0]["lang.big"].parent == Path(hint):
        return found[0]
    return (zh or found or [None])[0]


def fingerprint(files: dict) -> list:
    """The files whose size and time key the cached copy."""
    return sorted(files.values())


def open_source(files: dict):
    return None


def draw(src, recipe: dict, size):
    raise ValueError("the Generals reader draws no pictures")


# --------------------------------------------------------------------------- #
# the key assignments
# --------------------------------------------------------------------------- #

def _text(data: bytes) -> str:
    return data.decode("latin-1").lstrip("﻿ï»¿")


def command_map(text: str) -> dict:
    """{command: {field: value}} of the ``CommandMap <NAME> ... End`` blocks."""
    out, current = {}, None
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].split("//", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"CommandMap\s+(\S+)", line, re.IGNORECASE)
        if m:
            current = out.setdefault(m.group(1).upper(), {})
            continue
        if line.lower() == "end":
            current = None
            continue
        if current is not None and "=" in line:
            name, _, value = line.partition("=")
            current[name.strip().lower()] = value.strip()
    return out


def token(fields: dict) -> str | None:
    """``{key: KEY_1, modifiers: SHIFT_CTRL}`` -> ``"CTRL+SHIFT+1"``; None for
    KEY_NONE, a keypad key or an unknown name."""
    key = fields.get("key", "").upper()
    name = KEYS.get(key[4:]) if key.startswith("KEY_") else None
    mods = MODIFIERS.get((fields.get("modifiers") or "NONE").upper())
    if name is None or mods is None:
        return None
    return "+".join(list(mods) + [name])


def bindings(files: dict) -> dict | None:
    """{command: [key token]} of the installed game (see the module
    docstring), or None when no file could be read."""
    archives = {k: big.Archive.open(files[k]) for k in ("lang.big", "ini.big") if k in files}
    lang_dir = next((m.group(1) for n in archives["lang.big"].names()
                     if (m := re.fullmatch(r"data\\([^\\]+)\\commandmap\.ini", n))), None)

    def read(loose_key, archive_key, name):
        if loose_key in files:
            path = files[loose_key]
            if os.path.getsize(path) > MAX_TEXT:
                raise ValueError(f"{Path(path).name} is larger than this reader opens")
            return Path(path).read_bytes()
        archive = archives.get(archive_key)
        return archive.get(name, MAX_TEXT) if archive and name else None

    lang = f"Data\\{lang_dir}\\" if lang_dir else None
    merged: dict = {}
    for data in (read("lang/commandmap.ini", "lang.big", lang and lang + "CommandMap.ini"),
                 read("ini/commandmap.ini", "ini.big", "Data\\INI\\CommandMap.ini")):
        for command, fields in command_map(_text(data or b"")).items():
            merged.setdefault(command, {}).update(fields)
    out = {command: [t] if (t := token(fields)) else [] for command, fields in merged.items()}
    # Generals.str takes priority over the csf, loose or in an archive.
    data = read("generals.str", "lang.big", "Data\\Generals.str")
    if data is None:
        data = read("generals.str", "ini.big", "Data\\Generals.str")
    if data is not None:
        text = strings.str_file(data.decode("utf-8", errors="replace"))
    else:
        data = read("lang/generals.csf", "lang.big", lang and lang + "Generals.csf")
        text = strings.csf(data) if data else {}
    for label, value in text.items():
        if label.upper().startswith("CONTROLBAR:"):
            key = strings.hotkey(value)
            out[label] = [key] if key else []       # no & : the button has no hotkey
    return out or None
