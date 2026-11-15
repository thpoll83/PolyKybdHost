"""Game-asset reader for Warcraft III (classic, the MPQ releases up to 1.31).

Reads no pictures: it reads the key assignments of the installed game, so
the overlay's icons sit on the keys the installed language and the player's
own CustomKeys.txt use (``build.remap``). A German install, for example,
moves the unit to B (Bewegen) and ends the game with Alt+B, where the
English one uses M and Alt+Q.

Each binding in ``warcraft3.yaml`` names its command as the game's files do:

- ``SaveGameButton``, ``LoadGameButton``, ``OptionsButton``, ``HelpButton``,
  ``QuitButton``: Alt + the button's ``ControlShortcutKey`` in
  ``UI\\FrameDef\\UI\\EscMenuMainPanel.fdf``;
- ``MINIMAPSIGNALTOOLTIP`` and the other tooltips in ``TOOLTIPS``: the
  ``ALT-<key>`` the tooltip text in ``UI\\FrameDef\\GlobalStrings.fdf`` names;
- ``CmdMove``, ``CmdAttack`` and the other sections of
  ``Units\\CommandStrings.txt``: their ``Hotkey=``, replaced by the same
  section in the player's ``CustomKeys.txt`` (in the install folder) when it
  has one.

A file is taken from War3Patch.mpq first, then War3xlocal.mpq, War3x.mpq and
war3.mpq. Nothing read here leaves the machine. Checked on the German 1.22
files.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from polyhost.services.game_assets.starcraft import mpq

log = logging.getLogger("PolyHost")

REQUIRED = ("war3.mpq",)
OPTIONAL = ("war3x.mpq", "war3xlocal.mpq", "war3patch.mpq", "customkeys.txt")
SEARCH = ("war3patch.mpq", "war3xlocal.mpq", "war3x.mpq", "war3.mpq")   # a file is taken from the first

MENU_FILE = "UI\\FrameDef\\UI\\EscMenuMainPanel.fdf"
STRINGS_FILE = "UI\\FrameDef\\GlobalStrings.fdf"
COMMANDS_FILE = "Units\\CommandStrings.txt"

MENU_BUTTONS = ("SaveGameButton", "LoadGameButton", "OptionsButton", "HelpButton", "QuitButton")
TOOLTIPS = ("MINIMAPSIGNALTOOLTIP", "MINIMAPTERRAINTOOLTIP", "MINIMAPALLYCOLORTOOLTIP",
            "MINIMAPCREEPCOLORTOOLTIP", "FORMATION_TOOLTIP")

# Hotkey= numbers that are not letters (Windows key codes); 512 is Escape.
HOTKEY_CODES = {"512": "ESCAPE"}

INSTALL_NAMES = ("warcraft iii", "warcraft 3", "warcraft3")
MAX_TEXT = 4 * 1024 * 1024            # the largest text file read; CommandStrings.txt is 18 KB

# The game's files list only some keys, so a command the reader did not find
# is unknown, not unbound (build.remap).
BINDINGS_COMPLETE = False

_casc_logged: set = set()


# --------------------------------------------------------------------------- #
# finding the files
# --------------------------------------------------------------------------- #

def _listing(d: Path) -> dict:
    """{lower-case name: real name} of the entries in `d`; empty when unreadable."""
    try:
        return {n.lower(): n for n in os.listdir(d)}
    except OSError:
        return {}


def is_casc(d: Path) -> bool:
    """Whether `d` looks like a CASC install (Reforged, 1.32 and later)."""
    names = _listing(d)
    return ".build.info" in names or "_retail_" in names


def data_files(d: Path) -> dict | None:
    """{"war3.mpq": path, ...} when `d` holds war3.mpq, else None. Names are
    matched without regard to case. A CASC install is logged once."""
    names = _listing(d)
    if not all(r in names for r in REQUIRED):
        if names and is_casc(d) and str(d) not in _casc_logged:
            _casc_logged.add(str(d))
            log.info("Game art: the Warcraft III install in %s keeps its files in CASC "
                     "(Reforged), which is not read; the default keys are shown.", _shown(d))
        return None
    return {n: d / names[n] for n in REQUIRED + OPTIONAL if n in names}


def _shown(d: Path) -> str:
    from polyhost.services.game_assets.build import shown_folder
    return shown_folder(d)


def _named(parent: Path) -> list[Path]:
    """The Warcraft III folders directly in `parent`, in any case."""
    return [parent / real for low, real in _listing(parent).items() if low in INSTALL_NAMES]


def install_candidates() -> list[Path]:
    """Folders a Warcraft III install may be in: Program Files on Windows,
    Applications on macOS, and the same Program Files in the default Wine
    prefix (or $WINEPREFIX). Not checked on an install."""
    home = Path.home()
    parents = []
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        if os.environ.get(env):
            parents.append(Path(os.environ[env]))
    parents += [Path("/Applications"), home / "Applications"]
    prefixes = [Path(os.environ["WINEPREFIX"])] if os.environ.get("WINEPREFIX") else []
    prefixes.append(home / ".wine")
    for prefix in prefixes:
        parents += [prefix / "drive_c" / "Program Files (x86)", prefix / "drive_c" / "Program Files"]
    return [d for p in parents for d in _named(p)]


def searched(hint=None) -> list[Path]:
    """war3.exe, Warcraft III.exe and Frozen Throne.exe run from the install folder."""
    return ([Path(hint)] if hint else []) + install_candidates()


def find(folder: str = "", hint=None) -> dict | None:
    """The game files to read: from `folder` when set; else beside the running
    game (`hint`); else from the usual install folders."""
    if folder:
        return data_files(Path(folder).expanduser())
    for d in searched(hint):
        files = data_files(d)
        if files:
            return files
    return None


def fingerprint(files: dict) -> list:
    """The files whose size and time key the cached copy."""
    return sorted(files.values())


def open_source(files: dict):
    return None


def draw(src, recipe: dict, size):
    raise ValueError("the Warcraft III reader draws no pictures")


# --------------------------------------------------------------------------- #
# the key assignments
# --------------------------------------------------------------------------- #

def _text(data: bytes) -> str:
    """The game's text files are UTF-8, some with a byte order mark."""
    return data.decode("utf-8", errors="replace").lstrip("﻿")


def menu_keys(fdf: str) -> dict:
    """{button: "ALT+<key>"} of MENU_BUTTONS, from the frame that names the
    button and the first ControlShortcutKey inside it."""
    out = {}
    for name in MENU_BUTTONS:
        m = re.search(r'Frame\s+"GLUETEXTBUTTON"\s+"%s"[^{]*\{(.*?)\n\s*\}' % name, fdf, re.S)
        key = m and re.search(r'ControlShortcutKey\s+"([^"]+)"', m.group(1))
        if key and len(key.group(1).strip()) == 1:
            out[name] = f"ALT+{key.group(1).strip().upper()}"
    return out


def tooltip_keys(fdf: str) -> dict:
    """{tooltip: "ALT+<key>"} of TOOLTIPS, from the ``ALT-<key>`` in their text."""
    out = {}
    for name in TOOLTIPS:
        m = re.search(r'^\s*%s\s+"([^"\n]*)"' % name, fdf, re.M)
        key = m and re.search(r"ALT-([A-Za-z0-9])\b", m.group(1))
        if key:
            out[name] = f"ALT+{key.group(1).upper()}"
    return out


def command_keys(text: str) -> dict:
    """{section: key} from a CommandStrings.txt or CustomKeys.txt: the first
    ``Hotkey=`` of each ``[Cmd...]`` section, a letter or digit, or Escape."""
    out, section = {}, None
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.strip()
        if line.startswith("["):
            section = line.strip("[]").strip()
            continue
        if not section or not section.lower().startswith("cmd") or section in out:
            continue
        name, _, value = line.partition("=")
        if name.strip().lower() != "hotkey":
            continue
        value = value.split(",")[0].strip()
        if value in HOTKEY_CODES:
            out[section] = HOTKEY_CODES[value]
        elif len(value) == 1 and value.isalnum():
            out[section] = value.upper()
    return out


def bindings(files: dict) -> dict | None:
    """{command: [key token]} of the installed game (see the module
    docstring), or None when no file could be read."""
    archives = [mpq.Archive.open(files[n]) for n in SEARCH if n in files]

    def get(name):
        data = next((d for a in archives if (d := a.get(name)) is not None), None)
        if data is not None and len(data) > MAX_TEXT:
            raise ValueError(f"{name} is larger than this reader opens")
        return None if data is None else _text(data)

    out = {}
    if (fdf := get(MENU_FILE)) is not None:
        out.update(menu_keys(fdf))
    if (strings := get(STRINGS_FILE)) is not None:
        out.update(tooltip_keys(strings))
    commands = command_keys(get(COMMANDS_FILE) or "")
    if "customkeys.txt" in files:
        path = files["customkeys.txt"]
        if os.path.getsize(path) > MAX_TEXT:
            raise ValueError(f"{Path(path).name} is larger than this reader opens")
        with open(path, "rb") as f:
            commands.update(command_keys(_text(f.read())))
    out.update(commands)
    return {k: [v] for k, v in out.items()} or None
