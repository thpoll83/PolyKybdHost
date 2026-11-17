"""Editor plugins: copy the Vim/Neovim plugin, the Emacs package and the GDB
script shipped with this installation to where the program loads them.

The plugins (``vim-plugin/``, ``emacs-package/``) tell the host which mode the
editor is in, so the keycaps follow Normal and Insert mode in Vim or the Org
and Dired keys in Emacs. Without them an editor in a terminal shows the
terminal's keys. This module does the copy that their READMEs describe:

- Vim: ``~/.vim/pack/polykybd/start/polykybd`` (``~/vimfiles`` on Windows).
- Neovim: ``$XDG_DATA_HOME/nvim/site/pack/polykybd/start/polykybd``
  (``%LOCALAPPDATA%/nvim-data/site`` on Windows).
- Emacs: ``polykybd.el`` into ``<emacs dir>/polykybd/``, and a marked block in
  the init file that loads it and turns ``polykybd-mode`` on.
- GDB: ``polykybd.py`` (``gdb-plugin/``) into ``<config>/gdb/polykybd/``, and
  a marked block in the GDB init file that sources it. The script writes GDB's
  state (prompt or running) into the terminal title.
- IDA: ``polykybd_ida.py`` and ``ida-plugin.json`` (``ida-plugin/``) into
  ``<IDAUSR>/plugins/polykybd/``, which IDA 8.5 and later load as a plugin
  folder. The plugin reports which IDA view has the focus.
- Binary Ninja: ``polykybd_mode_reporter/`` (``binaryninja-plugin/``) into
  the user plugins folder, ``<user folder>/plugins/`` (``BN_USER_DIRECTORY``,
  else ``~/.binaryninja``, ``%APPDATA%/Binary Ninja`` or
  ``~/Library/Application Support/Binary Ninja``). It reports the view type and
  IL level of the focused pane.
- DaVinci Resolve: ``polykybd_context_reporter.py`` (``resolve-plugin/``)
  into ``<Fusion>/Scripts/Utility/PolyKybd/``, where Resolve lists it under
  Workspace > Scripts. It reports the current page (Media, Cut, Edit ...).
- Ableton Live 12: the remote script (``ableton-remote-script/PolyKybd/``) into
  ``<User Library>/Remote Scripts/PolyKybd/`` at Live's default User Library
  (``~/Documents/Ableton`` on Windows, ``~/Music/Ableton`` on macOS). Live
  lists it under Control Surface after a restart; the user selects it there.
- Houdini: the package (``houdini-package/``) into ``<prefs>/packages/``: the
  package file ``polykybd.json`` and the ``polykybd/`` folder it names, in the
  newest Houdini preferences folder (:func:`houdini_pref_dir`).
- JetBrains IDEs: the built plugin (``polyhost/res/jetbrains/
  polykybd-context-reporter.zip``, from ``jetbrains-plugin/``) unpacked as
  ``polykybd-context-reporter/`` into the plugins folder of every IntelliJ
  Platform IDE found, build 242 (2024.2) or newer (:func:`jetbrains_ides`).
- FreeCAD: the ``PolyKybd`` add-on (``freecad-addon/``) into FreeCAD's user
  ``Mod`` folder (:func:`freecad_mod_dir`). FreeCAD loads every folder there
  at start; the add-on reports the active workbench.

The programs added after these (:mod:`polyhost.services.editor_targets` has
their folders) work in three ways:

- A copy per version or profile, like JetBrains: Blender (``blender-addon/``,
  the ``user_default`` extension repository from 4.2, ``scripts/addons``
  before), Maya (``maya-plugin/``, a module in ``<MAYA_APP_DIR>/<version>/
  modules``), QGIS (``qgis-plugin/``, ``python/plugins`` of each profile) and
  Bitwig Studio (the built ``.bwextension`` in the Extensions folder).
- Through the editor's own command line program: VS Code, Cursor and
  Windsurf (``code --install-extension`` with the ``.vsix`` in
  ``polyhost/res/vscode/``, built from ``vscode-extension/``).
- Per project: Godot (``addons/``), Unity (an embedded package in
  ``Packages/``) and Obsidian (``.obsidian/plugins/``). The project folders
  the user chose are remembered (:class:`editor_targets.State`).

JupyterLab is a Python package for the environment that runs JupyterLab,
which this app cannot know: it gets the ``pip`` command to run
(STATE_COMMAND), not an install.

Each copy gets a stamp file with the SHA-256 of every file written.
:func:`refresh_installed` runs at every start: it copies the shipped files
again where a stamp exists and the shipped files changed (an update). A copy
whose files differ from the stamp was changed by hand and is left alone.

The init file is the user's own: it is changed the way ``shell_title``
changes a shell startup file (bytes outside the block are kept, a timestamped
copy is written first), with that module's helpers.

Qt-free and stdlib-only: ``polyctl`` imports it without PyQt5, and the tray
page (Integrations > Editors, ``gui/shell_editor_pages.py``) only shows it.
"""
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from collections import namedtuple
from pathlib import Path

from polyhost.i18n import M_
from polyhost.services import editor_targets as et
from polyhost.services.shell_title import _backup, _Text, _write

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VIM_SOURCE = REPO_ROOT / "vim-plugin"
EMACS_SOURCE = REPO_ROOT / "emacs-package"
GDB_SOURCE = REPO_ROOT / "gdb-plugin"
IDA_SOURCE = REPO_ROOT / "ida-plugin"
BINJA_SOURCE = REPO_ROOT / "binaryninja-plugin" / "polykybd_mode_reporter"
RESOLVE_SOURCE = REPO_ROOT / "resolve-plugin"
ABLETON_SOURCE = REPO_ROOT / "ableton-remote-script" / "PolyKybd"
HOUDINI_SOURCE = REPO_ROOT / "houdini-package"
# Built by `gradle shipPlugin` in jetbrains-plugin/; CI checks it is current
# (.github/workflows/jetbrains-plugin.yml).
JETBRAINS_SOURCE = REPO_ROOT / "polyhost" / "res" / "jetbrains" / "polykybd-context-reporter.zip"
FREECAD_SOURCE = REPO_ROOT / "freecad-addon" / "PolyKybd"
BLENDER_SOURCE = REPO_ROOT / "blender-addon" / et.BLENDER_PACKAGE
MAYA_SOURCE = REPO_ROOT / "maya-plugin"
QGIS_SOURCE = REPO_ROOT / "qgis-plugin" / et.QGIS_PACKAGE
BITWIG_SOURCE = REPO_ROOT / "bitwig-extension" / et.BITWIG_FILE
# Built by vscode-extension/build.sh and obsidian-plugin/build.sh; CI checks
# they are current (.github/workflows/built-plugins.yml).
VSCODE_SOURCE = REPO_ROOT / "polyhost" / "res" / "vscode" / "polykybd-mode-reporter.vsix"
VSCODE_REMOTE_SOURCE = REPO_ROOT / "polyhost" / "res" / "vscode" / "polykybd-mode-reporter-remote.vsix"
OBSIDIAN_SOURCE = REPO_ROOT / "polyhost" / "res" / "obsidian" / "polykybd-mode-reporter"
JUPYTERLAB_SOURCE = REPO_ROOT / "jupyterlab-extension"
GODOT_SOURCE = REPO_ROOT / "godot-plugin" / "addons" / "polykybd_reporter"
UNITY_SOURCE = REPO_ROOT / "unity-package"

VIM = "vim"
NEOVIM = "neovim"
EMACS = "emacs"
GDB = "gdb"
IDA = "ida"
HOUDINI = "houdini"
ABLETON = "ableton"
RESOLVE = "resolve"
BINARYNINJA = "binaryninja"
JETBRAINS = "jetbrains"
FREECAD = "freecad"
BLENDER = "blender"
MAYA = "maya"
QGIS = "qgis"
BITWIG = "bitwig"
VSCODE = "vscode"
CURSOR = "cursor"
WINDSURF = "windsurf"
JUPYTERLAB = "jupyterlab"
GODOT = "godot"
UNITY = "unity"
OBSIDIAN = "obsidian"
EDITORS = (VIM, NEOVIM, EMACS, GDB, IDA, BINARYNINJA, RESOLVE, ABLETON, HOUDINI, JETBRAINS, FREECAD,
           BLENDER, MAYA, QGIS, BITWIG, VSCODE, CURSOR, WINDSURF, JUPYTERLAB, GODOT, UNITY,
           OBSIDIAN)
# One copy per version or profile found (like JETBRAINS, see _change_multi).
COPY_EDITORS = (BLENDER, MAYA, QGIS, BITWIG)
# One copy per project folder the user chose.
PROJECT_EDITORS = (GODOT, UNITY, OBSIDIAN)
MULTI_EDITORS = COPY_EDITORS + PROJECT_EDITORS
# Installed with the editor's command line program.
CLI_EDITORS = (VSCODE, CURSOR, WINDSURF)
# The editors added with editor_targets; their sources come in ``sources``.
NEW_EDITORS = MULTI_EDITORS + CLI_EDITORS + (JUPYTERLAB,)
_NEW_SOURCES = {BLENDER: BLENDER_SOURCE, MAYA: MAYA_SOURCE, QGIS: QGIS_SOURCE,
                BITWIG: BITWIG_SOURCE, VSCODE: VSCODE_SOURCE, CURSOR: VSCODE_SOURCE,
                WINDSURF: VSCODE_SOURCE, JUPYTERLAB: JUPYTERLAB_SOURCE, GODOT: GODOT_SOURCE,
                UNITY: UNITY_SOURCE, OBSIDIAN: OBSIDIAN_SOURCE}
# The ones loaded through a marked block in an init file, beside a copy.
INIT_EDITORS = (EMACS, GDB)

# The plugin folders a Vim package needs. README.md stays behind.
_VIM_DIRS = ("plugin", "lua", "doc")
_EMACS_FILES = ("polykybd.el",)
_GDB_FILES = ("polykybd.py",)
_IDA_FILES = ("polykybd_ida.py", "ida-plugin.json")
_BINJA_FILES = ("__init__.py", "core.py")
_RESOLVE_FILES = ("polykybd_context_reporter.py",)
_ABLETON_FILES = ("__init__.py", "core.py", "reporter.py")
_FREECAD_FILES = ("InitGui.py", "polykybd_freecad_core.py", "polykybd_freecad_gui.py")

STAMP_NAME = ".polykybd-host.json"
BEGIN_MARKER = ";; >>> PolyKybd editor integration >>>"
END_MARKER = ";; <<< PolyKybd editor integration <<<"
GDB_BEGIN_MARKER = "# >>> PolyKybd editor integration >>>"
GDB_END_MARKER = "# <<< PolyKybd editor integration <<<"

# The port and token the plugins use when nothing is set. A host with another
# port or a token needs the same values in the editor's own settings.
DEFAULT_PORT = 50164

STATE_INSTALLED = "installed"
STATE_NOT_INSTALLED = "not-installed"
STATE_OUTDATED = "outdated"        # this app's copy, older than the shipped files
STATE_MODIFIED = "modified"        # this app's copy, changed by hand since
STATE_STALE = "stale"              # the init block loads another folder
STATE_MANUAL = "manual"            # loaded from somewhere this app did not write
STATE_NOT_PRESENT = "not-present"
STATE_NO_SOURCE = "no-source"      # this installation has no plugin files
STATE_NO_PROJECT = "no-project"    # a per-project plugin, no project folder chosen yet
STATE_COMMAND = "command"          # installed with a command the user runs (``detail``)

EditorStatus = namedtuple("EditorStatus", "editor state target detail")
EditorStatus.__doc__ = """One editor's state. ``target`` is the plugin folder
(Vim, Neovim) or the init file (Emacs), a Path or None. ``detail`` is the
other copy's path for STATE_MANUAL and STATE_STALE, "" otherwise.

For JETBRAINS, which has one copy per IDE, ``target`` is the folder that
holds the IDEs' folders, ``state`` sums up the IDEs' states
(:func:`_jetbrains_summary`) and ``detail`` names the IDE folders
(``IntelliJIdea2025.2, PyCharm2025.2``), or the folder for STATE_MANUAL."""

Result = namedtuple("Result", "editor ok changed message backup")
Result.__doc__ = """What install()/remove() did for one editor. ``message``
is English text from an ``M_()`` template, ``backup`` the copy of the init
file or of the replaced folder, or None."""

MSG_INSTALLED = M_("Copied the plugin to {path}.")
MSG_UPDATED = M_("Replaced the plugin in {path} with the one from this installation.")
MSG_ALREADY = M_("Already set up in {path}.")
MSG_REMOVED = M_("Removed the plugin from {path}.")
MSG_NOT_INSTALLED = M_("Nothing to remove in {path}.")
MSG_NOT_PRESENT = M_("{editor} was not found on this computer.")
MSG_NO_SOURCE = M_("This installation has no plugin files ({path}).")
MSG_MODIFIED = M_("{path} was changed by hand. Remove or update it by hand.")
MSG_NO_END_MARKER = M_("{path} has a start marker without an end marker. Remove the block by hand.")
MSG_WRITE_FAILED = M_("Could not change {path}: {error}")
MSG_EMACS_INSTALLED = M_("Copied the plugin to {path} and added the lines that load it to {init}.")
MSG_EMACS_REMOVED = M_("Removed the lines that load the plugin from {init}.")
MSG_EMACS_REMOVED_ALL = M_("Removed the lines that load the plugin from {init}, and the plugin from {path}.")
MSG_NOT_OURS = M_("{path} has a copy of the plugin that this app did not write. It is left alone.")
MSG_NOT_A_PROJECT = M_("{path} is not a {editor} project folder: it has no {marker}.")
MSG_NO_PROJECT = M_("No {editor} project folder was chosen.")
MSG_CLI_INSTALLED = M_("Installed the extension with {command}.")
MSG_CLI_REMOVED = M_("Removed the extension with {command}.")
MSG_CLI_FAILED = M_("{command} failed: {error}")
MSG_CLI_NOT_OURS = M_("{editor} has the extension {extension} from another source. It is left alone.")
MSG_STATE_NOT_SAVED = M_("The change was made, but {path} could not be written, so this app "
                         "does not remember it.")
MSG_RUN_COMMAND = M_("Run this command in the Python environment that runs JupyterLab: {command}")


# --- where the editors look -----------------------------------------------

def _home(home, env, system):
    if home is not None:
        return Path(home)
    if system == "Windows" and env.get("HOME"):
        # Vim, Neovim and Emacs on Windows all use HOME when it is set.
        return Path(env["HOME"])
    return Path.home()


def vim_dir(editor, home=None, env=None, system=None):
    """The package folder ``editor`` (VIM or NEOVIM) loads the plugin from."""
    env = os.environ if env is None else env
    system = system or platform.system()
    h = _home(home, env, system)
    if editor == VIM:
        base = h / ("vimfiles" if system == "Windows" else ".vim")
    elif system == "Windows":
        local = env.get("LOCALAPPDATA")
        base = (Path(local) if local else h / "AppData" / "Local") / "nvim-data" / "site"
    else:
        data = env.get("XDG_DATA_HOME")
        base = (Path(data) if data else h / ".local" / "share") / "nvim" / "site"
    return base / "pack" / "polykybd" / "start" / "polykybd"


def resolve_scripts_dir(home=None, env=None, system=None):
    """The per-user ``Fusion/Scripts`` folder DaVinci Resolve scans at start
    (README.txt of Resolve's scripting API)."""
    env = os.environ if env is None else env
    system = system or platform.system()
    h = Path(home) if home is not None else Path.home()
    if system == "Windows":
        appdata = env.get("APPDATA")
        base = Path(appdata) if appdata else h / "AppData" / "Roaming"
        return base / "Blackmagic Design" / "DaVinci Resolve" / "Support" / "Fusion" / "Scripts"
    if system == "Darwin":
        return (h / "Library" / "Application Support" / "Blackmagic Design"
                / "DaVinci Resolve" / "Fusion" / "Scripts")
    return h / ".local" / "share" / "DaVinciResolve" / "Fusion" / "Scripts"


def resolve_plugin_dir(home=None, env=None, system=None):
    """The folder the Resolve script is copied to: a ``Utility`` subfolder of
    its own, so removing it never touches the user's other scripts."""
    return resolve_scripts_dir(home, env, system) / "Utility" / "PolyKybd"


# Where Resolve itself is installed, to tell "not installed" from "never run".
_RESOLVE_APPS = {
    "Windows": (r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",),
    "Darwin": ("/Applications/DaVinci Resolve/DaVinci Resolve.app",),
}
_RESOLVE_APPS_LINUX = ("/opt/resolve/bin/resolve", "/home/resolve/bin/resolve")


def _resolve_present(home, env, system):
    """Resolve is installed, or has run for this user (it creates the
    ``Fusion`` folder above the scripts folder)."""
    if resolve_scripts_dir(home, env, system).parent.is_dir():
        return True
    if home is not None:        # a test's home: the real install does not count
        return False
    return any(Path(p).exists() for p in _RESOLVE_APPS.get(system, _RESOLVE_APPS_LINUX))


def emacs_init_file(home=None, env=None, system=None):
    """The init file Emacs reads, in Emacs's own order: ``~/.emacs``,
    ``~/.emacs.el``, ``~/.emacs.d/init.el``, ``$XDG_CONFIG_HOME/emacs/init.el``.
    When none exists, ``~/.emacs.d/init.el``, or the XDG one if only that
    folder exists."""
    env = os.environ if env is None else env
    system = system or platform.system()
    h = _home(home, env, system)
    xdg = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else h / ".config"
    dot_d = h / ".emacs.d"
    for candidate in (h / ".emacs", h / ".emacs.el", dot_d / "init.el", xdg / "emacs" / "init.el"):
        if candidate.is_file():
            return candidate
    if not dot_d.is_dir() and (xdg / "emacs").is_dir():
        return xdg / "emacs" / "init.el"
    return dot_d / "init.el"


def emacs_lisp_dir(init_file):
    """The folder ``polykybd.el`` is copied to, beside the init file."""
    init_file = Path(init_file)
    if init_file.name in (".emacs", ".emacs.el"):
        return init_file.parent / ".emacs.d" / "polykybd"
    return init_file.parent / "polykybd"


GDB_PROBE_TIMEOUT_S = 10
# The version is the first number.number after any parenthesised vendor text and
# any vendor words: "GNU gdb (GDB; openSUSE Leap 15.4) 11.1", "GNU gdb (Debian
# 10.1-1.7) 10.1.90.20210103-git", "GNU gdb (GDB) Red Hat Enterprise Linux 8.2-2.el7".
_GDB_VERSION_RE = re.compile(r"^GNU gdb(?: \([^)]*\))*[^\d\n]*?(\d+)\.\d+", re.M)
_GDB_PY_MARK = "PK-GDB-PYTHON"
_gdb_probe_cache = {}


def _gdb_exe(which=None):
    """The GDB the plugin would run under: ``gdb``, else ``gdb-multiarch``."""
    which = which or shutil.which
    return which("gdb") or which("gdb-multiarch")


def _gdb_probe(exe):
    """(major version or None, Python support True/False/None) of the GDB at
    `exe`, from one ``gdb --nx --batch`` run. None means it did not answer.
    An answer is kept per executable; no answer is asked again next time.
    Never raises."""
    if not exe:
        return None, None
    if exe not in _gdb_probe_cache:
        kwargs = {}
        if platform.system() == "Windows":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = (None, None)
        try:
            # Audit (Sourcery dangerous-subprocess-use): argv is a fixed list; exe
            # is what shutil.which found for "gdb" or "gdb-multiarch". No shell
            # parses it, and --nx keeps GDB from reading any init file.
            # nosemgrep
            proc = subprocess.run([exe, "--nx", "--batch", "-ex", f"python print('{_GDB_PY_MARK}')",
                                   "-ex", "show version"], capture_output=True,
                                  timeout=GDB_PROBE_TIMEOUT_S, **kwargs)
            out = proc.stdout.decode("utf-8", "replace")
            m = _GDB_VERSION_RE.search(out)
            if m:
                result = (int(m.group(1)), _GDB_PY_MARK in out)
        except (subprocess.TimeoutExpired, OSError) as exc:
            log.info("gdb did not answer the probe: %s", exc)
        if result == (None, None):
            return result       # not cached: a later status check asks again
        _gdb_probe_cache[exe] = result
    return _gdb_probe_cache[exe]


def _gdb_major(exe):
    """The major version of the GDB at `exe`, or None."""
    return _gdb_probe(exe)[0]



def gdb_init_file(home=None, env=None, system=None, gdb_major=None):
    """The init file GDB reads from the home folder.

    GDB 11 and later read ONE config-folder file and then ``~/.gdbinit``, the
    first that exists (``find_gdb_home_config_file()`` and
    ``get_standard_config_dir()`` in ``gdbsupport/pathstuff.cc``):

    - macOS: ``~/Library/Preferences/gdb/gdbinit``. ``XDG_CONFIG_HOME`` and
      ``~/.config`` are not read there.
    - elsewhere: ``$XDG_CONFIG_HOME/gdb/gdbinit`` when that variable is set,
      else ``~/.config/gdb/gdbinit``. With the variable set, ``~/.config`` is
      not read.

    GDB 10 and earlier read only ``~/.gdbinit``, so `gdb_major` below 11 selects
    it even when a config-folder file exists. When none exists, ``~/.gdbinit``,
    which every version reads. `gdb_major` None (version unknown) uses the GDB
    11 order."""
    env = os.environ if env is None else env
    system = system or platform.system()
    h = _home(home, env, system)
    if gdb_major is not None and gdb_major < 11:
        return h / ".gdbinit"
    if system == "Darwin":
        config = h / "Library" / "Preferences" / "gdb" / "gdbinit"
    elif env.get("XDG_CONFIG_HOME"):
        config = Path(env["XDG_CONFIG_HOME"]) / "gdb" / "gdbinit"
    else:
        config = h / ".config" / "gdb" / "gdbinit"
    return config if config.is_file() else h / ".gdbinit"


def gdb_plugin_dir(home=None, env=None, system=None):
    """The folder ``polykybd.py`` is copied to."""
    env = os.environ if env is None else env
    system = system or platform.system()
    h = _home(home, env, system)
    config = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else h / ".config"
    return config / "gdb" / "polykybd"


_FREECAD_VERSION_RE = re.compile(r"^v(\d+)-(\d+)$")


def freecad_data_dir(home=None, env=None, system=None):
    """FreeCAD's user data folder (``App.getUserAppDataDir()``), or None when
    FreeCAD has not run for this user.

    From ``ApplicationDirectories::configurePaths`` (FreeCAD 1.1.4): the base
    is ``$FREECAD_USER_DATA`` as given, else ``FreeCAD`` under ``%APPDATA%``
    (Windows), ``~/Library/Application Support`` (macOS) or
    ``$XDG_DATA_HOME`` / ``~/.local/share`` (elsewhere; the Flatpak's
    ``~/.var/app/org.freecad.FreeCAD/data`` when only that one exists). Since
    1.1 a ``v<major>-<minor>`` folder in the base, the newest one, is used
    when there is one."""
    env = os.environ if env is None else env
    system = system or platform.system()
    if env.get("FREECAD_USER_DATA"):
        custom = Path(env["FREECAD_USER_DATA"])
        return custom if custom.is_dir() else None
    h = _home(home, env, system)
    if system == "Windows":
        appdata = env.get("APPDATA")
        bases = [(Path(appdata) if appdata else h / "AppData" / "Roaming") / "FreeCAD"]
    elif system == "Darwin":
        bases = [h / "Library" / "Application Support" / "FreeCAD"]
    else:
        data = Path(env["XDG_DATA_HOME"]) if env.get("XDG_DATA_HOME") else h / ".local" / "share"
        bases = [data / "FreeCAD",
                 h / ".var" / "app" / "org.freecad.FreeCAD" / "data" / "FreeCAD"]
    base = next((b for b in bases if b.is_dir()), None)
    if base is None:
        return None
    versions = []
    for d in base.iterdir():
        m = _FREECAD_VERSION_RE.match(d.name)
        if m and d.is_dir():
            versions.append(((int(m.group(1)), int(m.group(2))), d))
    return max(versions)[1] if versions else base


def freecad_mod_dir(home=None, env=None, system=None):
    """The folder the add-on is copied to: ``<user data>/Mod/PolyKybd``, or
    None when FreeCAD has not run for this user."""
    data = freecad_data_dir(home, env, system)
    return None if data is None else data / "Mod" / "PolyKybd"


_HOUDINI_VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")
# The package file Houdini reads from <prefs>/packages, beside the folder it
# names. Its key in the stamp is relative to that folder.
HOUDINI_PACKAGE_FILE = "../polykybd.json"


def houdini_pref_dir(home=None, env=None, system=None):
    """The newest Houdini user preferences folder that exists, or None.

    ``$HOUDINI_USER_PREF_DIR`` when set (``__HVER__`` in its last part stands
    for the version), else ``~/houdiniX.Y`` (Linux), ``houdiniX.Y`` in
    ``%HOME%`` when set or else in ``Documents`` (Windows), and
    ``~/Library/Preferences/houdini/X.Y`` (macOS). Houdini creates the folder
    at its first start."""
    env = os.environ if env is None else env
    system = system or platform.system()
    custom = env.get("HOUDINI_USER_PREF_DIR")
    if custom and "__HVER__" not in custom:
        return Path(custom) if Path(custom).is_dir() else None
    if custom:
        base = Path(custom).parent
        prefix, _sep, suffix = Path(custom).name.partition("__HVER__")
    else:
        h = _home(home, env, system)
        if system == "Darwin":
            base, prefix = h / "Library" / "Preferences" / "houdini", ""
        elif system == "Windows" and not env.get("HOME"):
            base, prefix = h / "Documents", "houdini"
        else:
            base, prefix = h, "houdini"
        suffix = ""
    found = []
    try:
        entries = list(base.iterdir()) if base.is_dir() else []
    except OSError:
        entries = []
    for p in entries:
        name = p.name
        if not (name.startswith(prefix) and name.endswith(suffix)) or not p.is_dir():
            continue
        m = _HOUDINI_VERSION_RE.match(name[len(prefix):len(name) - len(suffix)])
        if m:
            found.append(((int(m.group(1)), int(m.group(2))), p))
    return max(found)[1] if found else None


def houdini_package_dir(pref_dir):
    """The folder the package is copied to: ``<prefs>/packages/polykybd``."""
    return Path(pref_dir) / "packages" / "polykybd"



def ida_user_dir(home=None, env=None, system=None):
    """IDA's user directory: the first entry of ``IDAUSR``, else
    ``%APPDATA%/Hex-Rays/IDA Pro`` on Windows and ``~/.idapro`` elsewhere
    (Hex-Rays, "Environment variables": IDAUSR)."""
    env = os.environ if env is None else env
    system = system or platform.system()
    first = (env.get("IDAUSR") or "").split(";" if system == "Windows" else ":")[0]
    if first:
        return Path(first)
    h = _home(home, env, system)
    if system == "Windows":
        appdata = env.get("APPDATA")
        return (Path(appdata) if appdata else h / "AppData" / "Roaming") / "Hex-Rays" / "IDA Pro"
    return h / ".idapro"


def ida_plugin_dir(home=None, env=None, system=None):
    """The plugin folder IDA loads ``polykybd_ida.py`` from."""
    return ida_user_dir(home, env, system) / "plugins" / "polykybd"


def ableton_script_dir(home=None, system=None):
    """The folder Live loads the remote script from, in Live's default User
    Library, or None where Live does not run (Linux). A User Library moved in
    Live's settings is not found; the README says to copy the folder there."""
    system = system or platform.system()
    h = Path(home) if home is not None else Path.home()
    if system == "Windows":
        lib = h / "Documents" / "Ableton" / "User Library"
    elif system == "Darwin":
        lib = h / "Music" / "Ableton" / "User Library"
    else:
        return None
    return lib / "Remote Scripts" / "PolyKybd"


def binaryninja_user_dir(home=None, env=None, system=None):
    """Binary Ninja's user folder (user guide, "User Folder")."""
    env = os.environ if env is None else env
    system = system or platform.system()
    if env.get("BN_USER_DIRECTORY"):
        return Path(env["BN_USER_DIRECTORY"])
    h = _home(home, env, system)
    if system == "Windows":
        appdata = env.get("APPDATA")
        return (Path(appdata) if appdata else h / "AppData" / "Roaming") / "Binary Ninja"
    if system == "Darwin":
        return h / "Library" / "Application Support" / "Binary Ninja"
    return h / ".binaryninja"


def binaryninja_dir(home=None, env=None, system=None):
    """The folder the Binary Ninja plugin is copied to, in the user plugins folder."""
    return binaryninja_user_dir(home, env, system) / "plugins" / "polykybd_mode_reporter"


JETBRAINS_PLUGIN_NAME = "polykybd-context-reporter"
# The oldest IDE build the plugin declares (jetbrains-plugin/build.gradle.kts,
# sinceBuild = "242", IntelliJ 2024.2).
JETBRAINS_MIN_BUILD = 242
# <product><year>.<release>, for example IntelliJIdea2025.2 or PyCharmCE2024.3.
_JETBRAINS_DIR_RE = re.compile(r"^([A-Za-z][A-Za-z-]*?)(20\d\d)\.(\d)$")
# IntelliJ-based programs that are not IDEs: Gateway and the remote
# development client run no project, so the plugin has nothing to report.
_JETBRAINS_NOT_IDES = ("JetBrainsGateway", "JetBrainsClient")


def _jetbrains_base(home, env, system, xdg_var, xdg_default):
    """``<base>/JetBrains`` as IntelliJ's ``PathManager.platformPath()`` builds
    it: ``%APPDATA%`` on Windows, ``~/Library/Application Support`` on macOS,
    ``$<xdg_var>`` or ``~/<xdg_default>`` elsewhere."""
    h = Path(home) if home is not None else Path.home()
    if system == "Windows":
        appdata = env.get("APPDATA")
        base = Path(appdata) if appdata else h / "AppData" / "Roaming"
    elif system == "Darwin":
        base = h / "Library" / "Application Support"
    else:
        xdg = env.get(xdg_var)
        base = Path(xdg) if xdg else h / xdg_default
    return base / "JetBrains"


def jetbrains_config_base(home=None, env=None, system=None):
    """The folder that holds each IDE's configuration folder (JetBrains,
    "Directories used by the IDE": Configuration directory)."""
    env = os.environ if env is None else env
    return _jetbrains_base(home, env, system or platform.system(), "XDG_CONFIG_HOME", ".config")


def jetbrains_plugins_base(home=None, env=None, system=None):
    """The folder that holds each IDE's plugins folder: the configuration
    folders on Windows and macOS, ``~/.local/share/JetBrains`` on Linux."""
    env = os.environ if env is None else env
    return _jetbrains_base(home, env, system or platform.system(), "XDG_DATA_HOME",
                           ".local/share")


def jetbrains_plugins_dir(selector, home=None, env=None, system=None):
    """The plugins folder of the IDE whose folders are named ``selector``
    (``IntelliJIdea2025.2``): ``%APPDATA%/JetBrains/<selector>/plugins`` on
    Windows, ``~/Library/Application Support/JetBrains/<selector>/plugins`` on
    macOS and ``~/.local/share/JetBrains/<selector>`` on Linux (JetBrains,
    "Directories used by the IDE": Plugins directory). An IDE started with
    ``idea.plugins.path`` set is not followed."""
    system = system or platform.system()
    base = jetbrains_plugins_base(home, env, system) / selector
    return base if system not in ("Windows", "Darwin") else base / "plugins"


def jetbrains_build(selector):
    """The build branch of an IDE folder name (``PyCharm2024.2`` -> 242), or
    None when the name is not ``<product><year>.<release>``."""
    m = _JETBRAINS_DIR_RE.match(selector)
    if not m or m.group(1) in _JETBRAINS_NOT_IDES:
        return None
    return (int(m.group(2)) % 100) * 10 + int(m.group(3))


def jetbrains_ides(home=None, env=None, system=None):
    """``[(selector, plugin folder)]`` of each JetBrains IDE that has run here,
    build JETBRAINS_MIN_BUILD or newer, sorted by name. An IDE writes its
    configuration folder at its first start; its plugins folder on Linux only
    once it has a plugin, so both are searched."""
    env = os.environ if env is None else env
    system = system or platform.system()
    names = set()
    for base in (jetbrains_config_base(home, env, system), jetbrains_plugins_base(home, env, system)):
        try:
            names.update(p.name for p in base.iterdir() if p.is_dir())
        except OSError:
            # A missing or unreadable base folder means no IDE has run there;
            # the other base folder may still list one.
            pass
    out = []
    for name in sorted(names):
        build = jetbrains_build(name)
        if build is not None and build >= JETBRAINS_MIN_BUILD:
            out.append((name, jetbrains_plugins_dir(name, home, env, system) / JETBRAINS_PLUGIN_NAME))
    return out


def _copy_dir(editor, home, env, system):
    """The plugin folder of a copy-only editor (Vim, Neovim, IDA, Binary Ninja)."""
    if editor == BINARYNINJA:
        return binaryninja_dir(home, env, system)
    if editor == IDA:
        return ida_plugin_dir(home, env, system)
    return vim_dir(editor, home, env, system)


def _present(editor, which, system, home=None, env=None):
    which = which or shutil.which
    names = {VIM: ("vim", "gvim"), NEOVIM: ("nvim",), EMACS: ("emacs", "runemacs"),
             GDB: ("gdb", "gdb-multiarch"), IDA: ("ida", "ida64"),
             BINARYNINJA: ("binaryninja",)}[editor]
    if editor == IDA and ida_user_dir(home, env, system).is_dir():
        return True          # IDA is rarely on PATH; it writes its user dir at first start
    return any(which(n) for n in names)


# --- the files to copy ------------------------------------------------------

_TAG_RE = re.compile(r"(?:^|(?<=[\s]))\*([^\s|*]+)\*(?=\s|$)", re.M)


def help_tags(doc_name, text):
    """The ``tags`` file Vim's ``:helptags`` writes for one help file:
    ``tag<Tab>file<Tab>/*tag*``, sorted by byte value. Written here so no
    editor has to be started."""
    tags = sorted(set(_TAG_RE.findall(text)), key=lambda t: t.encode("utf-8"))
    lines = []
    for tag in tags:
        pattern = tag.replace("\\", "\\\\").replace("/", "\\/")
        lines.append(f"{tag}\t{doc_name}\t/*{pattern}*\n")
    return "".join(lines).encode("utf-8")


def shipped_files(editor, source=None):
    """``{relative path: bytes}`` to write for ``editor``, or None when this
    installation has no plugin files."""
    if editor == FREECAD:
        source = Path(source or FREECAD_SOURCE)
        if not all((source / name).is_file() for name in _FREECAD_FILES):
            return None
        return {name: (source / name).read_bytes() for name in _FREECAD_FILES}
    if editor == RESOLVE:
        source = Path(source or RESOLVE_SOURCE)
        if not all((source / name).is_file() for name in _RESOLVE_FILES):
            return None
        return {name: (source / name).read_bytes() for name in _RESOLVE_FILES}
    if editor == ABLETON:
        source = Path(source or ABLETON_SOURCE)
        if not all((source / name).is_file() for name in _ABLETON_FILES):
            return None
        return {name: (source / name).read_bytes() for name in _ABLETON_FILES}
    if editor == HOUDINI:
        return _houdini_files(source)
    if editor == JETBRAINS:
        return _jetbrains_files(source)
    if editor in INIT_EDITORS:
        names = _EMACS_FILES if editor == EMACS else _GDB_FILES
        source = Path(source or (EMACS_SOURCE if editor == EMACS else GDB_SOURCE))
        if not all((source / name).is_file() for name in names):
            return None
        return {name: (source / name).read_bytes() for name in names}
    if editor == IDA:
        source = Path(source or IDA_SOURCE)
        if not all((source / name).is_file() for name in _IDA_FILES):
            return None
        return {name: (source / name).read_bytes() for name in _IDA_FILES}
    if editor == BINARYNINJA:
        source = Path(source or BINJA_SOURCE)
        if not all((source / name).is_file() for name in _BINJA_FILES):
            return None
        return {name: (source / name).read_bytes() for name in _BINJA_FILES}
    source = Path(source or VIM_SOURCE)
    if not (source / "plugin" / "polykybd.vim").is_file():
        return None
    files = {}
    for sub in _VIM_DIRS:
        for path in sorted((source / sub).rglob("*")):
            if path.is_file() and path.name != "tags":
                files[path.relative_to(source).as_posix()] = path.read_bytes()
    for rel, data in list(files.items()):
        if rel.startswith("doc/") and rel.endswith(".txt"):
            tags = help_tags(rel[len("doc/"):], data.decode("utf-8", "replace"))
            files["doc/tags"] = files.get("doc/tags", b"") + tags
    return files


def _houdini_files(source=None):
    """The Houdini package: every file of ``polykybd/`` (no bytecode), and
    the package file, keyed ``../polykybd.json`` because it sits beside the
    folder in ``packages/``."""
    source = Path(source or HOUDINI_SOURCE)
    folder = source / "polykybd"
    if not (source / "polykybd.json").is_file() or not folder.is_dir():
        return None
    files = {HOUDINI_PACKAGE_FILE: (source / "polykybd.json").read_bytes()}
    for path in sorted(folder.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            files[path.relative_to(folder).as_posix()] = path.read_bytes()
    return files


def _jetbrains_files(source=None):
    """The files of the built plugin zip, keyed relative to its top folder
    ``polykybd-context-reporter/`` (``lib/<name>.jar``). None when there is no
    zip (a checkout where it was deleted) or it is not one this app reads:
    every entry must be a plain path inside that folder."""
    source = Path(source or JETBRAINS_SOURCE)
    if not source.is_file():
        return None
    prefix = JETBRAINS_PLUGIN_NAME + "/"
    files = {}
    try:
        with zipfile.ZipFile(source) as zf:
            for info in zf.infolist():
                name = info.filename
                if info.is_dir():
                    continue
                rel = name[len(prefix):] if name.startswith(prefix) else ""
                parts = rel.split("/")
                if not rel or "\\" in rel or any(p in ("", ".", "..") for p in parts) or ":" in rel:
                    log.warning("JetBrains plugin zip %s: unexpected entry %r", source, name)
                    return None
                files[rel] = zf.read(info)
    except (OSError, zipfile.BadZipFile) as exc:
        log.warning("JetBrains plugin zip %s cannot be read: %s", source, exc)
        return None
    return files or None


def _sha(data):
    return hashlib.sha256(data).hexdigest()


# The only stamp entries outside the stamped folder: a package or module file
# beside the folder, for the folder name and parent folder name given.
# (entry, folder name, parent folder name)
_SIDECARS = (("../polykybd.json", "polykybd", "packages"),     # HOUDINI_PACKAGE_FILE
             ("../polykybd.mod", "polykybd", "modules"))       # MAYA_MOD_FILE


def stamp_path_ok(folder, rel):
    """Whether ``rel`` is a file of the copy in ``folder`` that this app may
    read, write or delete: a plain relative path ("a/b.py": no absolute path,
    drive, backslash, "." or ".." part) that, with every symbolic link
    followed, stays inside ``folder``. A Houdini or Maya sidecar file
    (_SIDECARS) may be beside the folder instead.

    A stamp is a file in the folder, and a per-project folder (Godot, Unity,
    Obsidian) is in a project the user may have downloaded: its entries are
    not trusted."""
    if not isinstance(rel, str) or not rel:
        return False
    folder = Path(folder)
    base, target = folder, None
    for entry, name, parent in _SIDECARS:
        if rel == entry and folder.name == name and folder.parent.name == parent:
            base, target = folder.parent, folder.parent / entry[3:]
    if target is None:
        if "\\" in rel or ":" in rel or rel.startswith("/"):
            return False
        if any(part in ("", ".", "..") for part in rel.split("/")):
            return False
        target = folder / rel
    try:
        real_base, real = base.resolve(), target.resolve()
    except (OSError, ValueError, RuntimeError):
        return False
    return real != real_base and real_base in real.parents


def read_stamp(folder, stamp_name=STAMP_NAME):
    """The stamp's ``{relative path: sha256}``, or None when there is none,
    it cannot be read, or an entry is not a path :func:`stamp_path_ok`
    accepts (then the copy is not this app's, and nothing is touched)."""
    try:
        data = json.loads((Path(folder) / stamp_name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict):
        return None
    for rel, digest in files.items():
        if not isinstance(digest, str) or not stamp_path_ok(folder, rel):
            log.warning("Editor plugin: %s lists %r, which is outside the folder or not a "
                        "plain file name; the copy is left alone.",
                        Path(folder) / stamp_name, rel)
            return None
    return files


def _copy_state(folder, shipped, stamp_name=STAMP_NAME, shared=False):
    """STATE_INSTALLED, STATE_OUTDATED, STATE_MODIFIED or STATE_MANUAL for a
    folder that exists, STATE_NOT_INSTALLED for one that does not.

    ``shared``: without a stamp, the copy is STATE_MANUAL only when one of
    the shipped files is there, not for any file in the folder (a folder the
    program shares with other plugins, or where it keeps its own settings
    file beside the plugin's)."""
    folder = Path(folder)
    stamp = read_stamp(folder, stamp_name)
    if stamp is None and (folder / stamp_name).exists():
        # A stamp that cannot be read or names files outside the folder.
        return STATE_MANUAL
    if stamp is None:
        if shared:
            return (STATE_MANUAL if any((folder / rel).exists() for rel in shipped)
                    else STATE_NOT_INSTALLED)
        return STATE_MANUAL if folder.is_dir() and any(folder.iterdir()) else STATE_NOT_INSTALLED
    missing = False
    for rel, digest in stamp.items():
        # Every file is checked: a missing one must not hide a later file
        # that was changed by hand, which an update would then overwrite.
        try:
            if _sha((folder / rel).read_bytes()) != digest:
                return STATE_MODIFIED
        except FileNotFoundError:
            missing = True
        except OSError:
            return STATE_MODIFIED
    if missing:
        return STATE_OUTDATED
    want = {rel: _sha(data) for rel, data in shipped.items()}
    return STATE_INSTALLED if want == stamp else STATE_OUTDATED


def _write_copy(folder, shipped, old_stamp=None, stamp_name=STAMP_NAME):
    """Write ``shipped`` into ``folder``, each file through a temporary file
    and a rename, and the stamp last. Files an older stamp listed and the
    new copy has not are deleted."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for rel in list(shipped) + list(old_stamp or {}):
        if not stamp_path_ok(folder, rel):
            raise OSError(f"{rel!r} is outside {folder}")
    for rel, data in shipped.items():
        dest = folder / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".polykybd-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dest)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    for rel in (old_stamp or {}):
        if rel not in shipped:
            try:
                (folder / rel).unlink()
            except OSError:
                pass
    stamp = {"files": {rel: _sha(data) for rel, data in shipped.items()}}
    # Through a temporary file and a rename: a status check running at the
    # same time never reads half a stamp (which would make the copy manual).
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".polykybd-stamp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(stamp, indent=1, sort_keys=True))
        os.replace(tmp, folder / stamp_name)
    except OSError:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass     # os.replace may have moved it already
        raise


def _delete_copy(folder, stamp_name=STAMP_NAME, keep_folder=False):
    """Delete this app's copy: the stamped files, the stamp, then every
    folder that is left empty, up to the ``pack`` folder. ``keep_folder``
    keeps ``folder`` itself and its other subfolders (a folder the program
    shares with other plugins)."""
    folder = Path(folder)
    for rel in read_stamp(folder, stamp_name) or {}:
        try:
            (folder / rel).unlink()
        except FileNotFoundError:
            pass
    (folder / stamp_name).unlink()
    if keep_folder:
        return
    # Python writes compiled copies beside a loaded script (Live does for
    # the remote script); they belong to the copy.
    shutil.rmtree(folder / "__pycache__", ignore_errors=True)
    dirs = sorted((p for p in folder.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True)
    for d in dirs + [folder]:
        try:
            d.rmdir()
        except OSError:
            pass
    for parent in (folder.parent, folder.parent.parent):     # start/, polykybd/
        if parent.name in ("start", "polykybd"):
            try:
                parent.rmdir()
            except OSError:
                break


def _set_aside(folder, now=None):
    """Move a folder this app did not write out of the way, beside the
    package's ``start`` folder, where Vim does not load it."""
    folder = Path(folder)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    dest = folder.parent.parent / f"polykybd-backup-{stamp}"
    n = 1
    while dest.exists():
        dest = folder.parent.parent / f"polykybd-backup-{stamp}-{n}"
        n += 1
    shutil.move(str(folder), str(dest))
    return dest


# --- the init blocks (Emacs, GDB) ---------------------------------------------

def _marker_re(begin, end):
    return re.compile(
        r"(?m)^" + re.escape(begin) + r"[ \t]*\r?\n(.*?)^"
        + re.escape(end) + r"[ \t]*(?:\r?\n|\Z)", re.S)


_BLOCK_RE = _marker_re(BEGIN_MARKER, END_MARKER)
_GDB_BLOCK_RE = _marker_re(GDB_BEGIN_MARKER, GDB_END_MARKER)
_GDB_FILE_RE = re.compile(r'^_pk_file = ("(?:[^"\\]|\\.)*")[ \t]*\r?$', re.M)
_LOAD_PATH_RE = re.compile(r"\(add-to-list 'load-path \"((?:[^\"\\]|\\.)*)\"\)")


def _lisp_string(path):
    s = Path(path).as_posix()
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def init_block(lisp_dir, nl="\n"):
    """The lines that load the copied package. ``file-readable-p`` keeps
    Emacs starting without an error when the folder has gone."""
    d = _lisp_string(lisp_dir)
    f = _lisp_string(Path(lisp_dir) / "polykybd.el")
    lines = [BEGIN_MARKER,
             f"(when (file-readable-p {f})",
             f"  (add-to-list 'load-path {d})",
             "  (require 'polykybd)",
             "  (polykybd-mode 1))",
             END_MARKER]
    return nl.join(lines) + nl


def gdb_init_block(plugin_dir, nl="\n"):
    """The lines that source the copied GDB script. The Python check keeps
    GDB starting without an error when the file has gone."""
    f = json.dumps((Path(plugin_dir) / "polykybd.py").as_posix())
    lines = [GDB_BEGIN_MARKER,
             "python",
             "import os as _pk_os",
             f"_pk_file = {f}",
             "if _pk_os.path.isfile(_pk_file):",
             '    gdb.execute("source " + _pk_file)',
             "end",
             GDB_END_MARKER]
    return nl.join(lines) + nl


def _read_init(path):
    try:
        raw = Path(path).read_bytes()
    except FileNotFoundError:
        return None
    return _Text(raw, "utf-8")


def _init_blocks(text, editor=EMACS):
    block_re = _GDB_BLOCK_RE if editor == GDB else _BLOCK_RE
    begin = GDB_BEGIN_MARKER if editor == GDB else BEGIN_MARKER
    found = [(m.start(), m.end(), m.group(1)) for m in block_re.finditer(text)]
    rest = block_re.sub("", text)
    orphan = re.search(r"(?m)^" + re.escape(begin), rest) is not None
    return found, orphan, rest


def _block_dir(inner, editor=EMACS):
    """The folder a marked block loads the plugin from, as a string."""
    if editor == GDB:
        g = _GDB_FILE_RE.search(inner)
        if not g:
            return ""
        try:
            return str(Path(json.loads(g.group(1))).parent)
        except ValueError:
            return ""
    m = _LOAD_PATH_RE.search(inner)
    if not m:
        return ""
    return re.sub(r"\\(.)", r"\1", m.group(1))


_GDB_LOADS_RE = re.compile(r"polykybd\.py\b")


def _mentions_polykybd(rest, comment=";"):
    """Whether the init file loads the package outside the marked block.
    For GDB that is a line naming ``polykybd.py`` (``source …/polykybd.py``),
    so a setting that merely contains the word is not taken for a load."""
    for line in rest.splitlines():
        code = line.split(comment, 1)[0]
        if comment == "#":
            if _GDB_LOADS_RE.search(code):
                return True
        elif "polykybd" in code:
            return True
    return False


def _init_paths(editor, home, env, system, gdb_probe=(None, None)):
    """(init file, plugin folder) of an INIT_EDITORS editor. `gdb_probe` is the
    (major, python) answer of `_gdb_probe` for this status call."""
    if editor == GDB:
        return (gdb_init_file(home, env, system, gdb_probe[0]),
                gdb_plugin_dir(home, env, system))
    init = emacs_init_file(home, env, system)
    return init, emacs_lisp_dir(init)


def _block_for(editor, plugin_dir, nl):
    return gdb_init_block(plugin_dir, nl) if editor == GDB else init_block(plugin_dir, nl)


# --- status -----------------------------------------------------------------

def _other_vim_copies(editor, folder):
    """Plugin copies another plugin manager or a hand copy put elsewhere."""
    base = Path(folder).parents[3]          # ~/.vim, .../nvim/site
    patterns = ["pack/*/start/*/plugin/polykybd.vim", "pack/*/opt/*/plugin/polykybd.vim",
                "plugged/*/plugin/polykybd.vim", "bundle/*/plugin/polykybd.vim"]
    searches = [(base, p) for p in patterns]
    if editor == NEOVIM:
        # lazy.nvim keeps its plugins beside site/, not in it.
        searches.append((base.parent / "lazy", "*/plugin/polykybd.vim"))
    own = Path(folder) / "plugin" / "polykybd.vim"
    for root, pattern in searches:
        for hit in sorted(root.glob(pattern)):
            if hit != own:
                return hit.parent.parent
    return None


def _sources(vim_source, emacs_source, gdb_source, ida_source=None, ableton_source=None,
             houdini_source=None, jetbrains_source=None, freecad_source=None):
    return {VIM: vim_source, NEOVIM: vim_source, EMACS: emacs_source, GDB: gdb_source,
            IDA: ida_source,
            BINARYNINJA: None,     # BINJA_SOURCE
            RESOLVE: None,
            ABLETON: ableton_source,
            HOUDINI: houdini_source,
            JETBRAINS: jetbrains_source,
            FREECAD: freecad_source}


def status(editors=None, home=None, env=None, which=None, system=None,
           vim_source=None, emacs_source=None, gdb_source=None, ida_source=None,
           ableton_source=None, houdini_source=None, jetbrains_source=None,
           freecad_source=None, sources=None, state_file=None, run=None):
    """An EditorStatus for each editor (``editors`` filters by id).

    For NEW_EDITORS: ``sources`` maps an editor to its plugin source (tests),
    ``state_file`` is the remembered projects and installs (:func:`_state`),
    ``run`` runs the editor's command line program (:func:`_run_cli`)."""
    env = os.environ if env is None else env
    system = system or platform.system()
    new_sources = sources or {}
    sources = _sources(vim_source, emacs_source, gdb_source, ida_source, ableton_source,
                       houdini_source, jetbrains_source, freecad_source)
    state = None
    out = []
    for editor in EDITORS:
        if editors is not None and editor not in editors:
            continue
        if editor in NEW_EDITORS:
            if state is None:
                state = _state(home, state_file)
            out.append(_status_new(editor, home, env, which, system, new_sources.get(editor),
                                   state, run or _run_cli))
            continue
        if editor == FREECAD:
            out.append(_status_freecad(home, env, system, sources[editor]))
            continue
        out.append(_status_one(editor, home, env, which, system, sources[editor]))
    return out


# The order in which the IDEs' states sum up to one: an IDE to update or to
# set up comes first, so default_selection() offers Install.
_JETBRAINS_ORDER = (STATE_OUTDATED, STATE_NOT_INSTALLED, STATE_MODIFIED, STATE_MANUAL,
                    STATE_INSTALLED)


def _jetbrains_states(shipped, home, env, system):
    """``[(selector, folder, state)]`` for each IDE of :func:`jetbrains_ides`."""
    return [(sel, folder, _copy_state(folder, shipped))
            for sel, folder in jetbrains_ides(home, env, system)]


def _jetbrains_summary(states):
    """One state for all IDEs: the first of _JETBRAINS_ORDER that any has."""
    have = {st for _sel, _folder, st in states}
    return next(st for st in _JETBRAINS_ORDER if st in have)


def _status_jetbrains(home, env, system, source):
    shipped = shipped_files(JETBRAINS, source)
    base = jetbrains_plugins_base(home, env, system)
    if shipped is None:
        return EditorStatus(JETBRAINS, STATE_NO_SOURCE, base, str(source or JETBRAINS_SOURCE))
    states = _jetbrains_states(shipped, home, env, system)
    if not states:
        return EditorStatus(JETBRAINS, STATE_NOT_PRESENT, base, "")
    state = _jetbrains_summary(states)
    if state == STATE_MANUAL:
        detail = next(str(folder) for _sel, folder, st in states if st == STATE_MANUAL)
    else:
        detail = ", ".join(sel for sel, _folder, _st in states)
    return EditorStatus(JETBRAINS, state, base, detail)
def _status_freecad(home, env, system, source):
    """FreeCAD: a plain folder copy in the user Mod folder, like Vim's.
    Not present until FreeCAD has run once and made its user data folder."""
    folder = freecad_mod_dir(home, env, system)
    shipped = shipped_files(FREECAD, source)
    if shipped is None:
        return EditorStatus(FREECAD, STATE_NO_SOURCE, folder, str(source or FREECAD_SOURCE))
    if folder is None:
        return EditorStatus(FREECAD, STATE_NOT_PRESENT, None, "")
    state = _copy_state(folder, shipped)
    return EditorStatus(FREECAD, state, folder, str(folder) if state == STATE_MANUAL else "")


def _status_one(editor, home, env, which, system, source):
    if editor == JETBRAINS:
        return _status_jetbrains(home, env, system, source)
    shipped = shipped_files(editor, source)
    if editor == HOUDINI:
        pref = houdini_pref_dir(home, env, system)
        folder = houdini_package_dir(pref) if pref is not None else None
        if shipped is None:
            return EditorStatus(editor, STATE_NO_SOURCE, folder, str(source or HOUDINI_SOURCE))
        if folder is None:
            return EditorStatus(editor, STATE_NOT_PRESENT, None, "")
        state, detail = _copy_state(folder, shipped), ""
        if state == STATE_MANUAL:
            detail = str(folder)
        elif state == STATE_NOT_INSTALLED and (folder.parent / "polykybd.json").exists():
            # A package file of the same name that this app did not write.
            state, detail = STATE_MANUAL, str(folder.parent / "polykybd.json")
        return EditorStatus(editor, state, folder, detail)
    if editor == RESOLVE:
        folder = resolve_plugin_dir(home, env, system)
        if shipped is None:
            return EditorStatus(editor, STATE_NO_SOURCE, folder, str(source or RESOLVE_SOURCE))
        if not folder.exists() and not _resolve_present(home, env, system):
            return EditorStatus(editor, STATE_NOT_PRESENT, folder, "")
        state = _copy_state(folder, shipped)
        return EditorStatus(editor, state, folder, str(folder) if state == STATE_MANUAL else "")
    if editor in INIT_EDITORS:
        # One probe per status call, so the init file and the Python check
        # never rest on two different answers.
        probe = _gdb_probe(_gdb_exe(which)) if editor == GDB else (None, None)
        init, want = _init_paths(editor, home, env, system, probe)
        if shipped is None:
            default = EMACS_SOURCE if editor == EMACS else GDB_SOURCE
            return EditorStatus(editor, STATE_NO_SOURCE, init, str(source or default))
        doc = _read_init(init)
        if not _present(editor, which, system) and doc is None:
            return EditorStatus(editor, STATE_NOT_PRESENT, init, "")
        found, _orphan, rest = _init_blocks(doc.text, editor) if doc is not None else ([], False, "")
        if not found and editor == GDB and probe[1] is False:
            # The script needs Python, and in a GDB built without it the
            # block's `python` line stops the init file with an error. Only
            # when there is no block: an existing one must stay removable.
            return EditorStatus(editor, STATE_NOT_PRESENT, init, "GDB without Python")
        if not found:
            if _mentions_polykybd(rest, "#" if editor == GDB else ";"):
                return EditorStatus(editor, STATE_MANUAL, init, str(init))
            return EditorStatus(editor, STATE_NOT_INSTALLED, init, "")
        named = _block_dir(doc.unpiece(found[0][2]), editor)
        if Path(named) != want or len(found) > 1:
            return EditorStatus(editor, STATE_STALE, init, named)
        state = _copy_state(want, shipped)
        if state in (STATE_NOT_INSTALLED, STATE_MANUAL):
            # The block is there and the copy is gone or not ours.
            state = STATE_OUTDATED if state == STATE_NOT_INSTALLED else STATE_MANUAL
        return EditorStatus(editor, state, init, str(want) if state == STATE_MANUAL else "")
    if editor == ABLETON:
        folder = ableton_script_dir(home, system)
        if folder is None:
            return EditorStatus(editor, STATE_NOT_PRESENT, None, "")
        if shipped is None:
            return EditorStatus(editor, STATE_NO_SOURCE, folder, str(source or ABLETON_SOURCE))
        # Live creates its User Library at the first start.
        if not folder.parent.parent.is_dir():
            return EditorStatus(editor, STATE_NOT_PRESENT, folder, "")
        state = _copy_state(folder, shipped)
        return EditorStatus(editor, state, folder, str(folder) if state == STATE_MANUAL else "")
    folder = _copy_dir(editor, home, env, system)
    if shipped is None:
        default = {BINARYNINJA: BINJA_SOURCE, IDA: IDA_SOURCE}.get(editor, VIM_SOURCE)
        return EditorStatus(editor, STATE_NO_SOURCE, folder, str(source or default))
    # Binary Ninja is rarely on PATH: its user folder shows it was run here.
    present = _present(editor, which, system, home, env) or (
        editor == BINARYNINJA and binaryninja_user_dir(home, env, system).is_dir())
    if not present and not folder.exists():
        return EditorStatus(editor, STATE_NOT_PRESENT, folder, "")
    state = _copy_state(folder, shipped)
    detail = str(folder) if state == STATE_MANUAL else ""
    if state == STATE_NOT_INSTALLED and editor not in (IDA, BINARYNINJA):
        other = _other_vim_copies(editor, folder)
        if other is not None:
            state, detail = STATE_MANUAL, str(other)
    return EditorStatus(editor, state, folder, detail)


# --- the programs of editor_targets -----------------------------------------------

# English names for the messages (the dialog has its own, editor_label()).
EDITOR_NAMES = {BLENDER: "Blender", MAYA: "Maya", QGIS: "QGIS", BITWIG: "Bitwig Studio",
                VSCODE: "VS Code", CURSOR: "Cursor", WINDSURF: "Windsurf",
                JUPYTERLAB: "JupyterLab", GODOT: "Godot", UNITY: "Unity", OBSIDIAN: "Obsidian"}
# The Extensions folder holds every Bitwig extension: a stamp of its own name.
BITWIG_STAMP_NAME = ".polykybd-host-bitwig.json"
# The module file Maya reads from <version>/modules, beside the module folder.
# Its key in the stamp is relative to that folder, like HOUDINI_PACKAGE_FILE.
MAYA_MOD_FILE = "../polykybd.mod"
_MAYA_PLUGIN = "plug-ins/polykybd_mode_reporter.py"
# The files without which a source folder is not the plugin.
_REQUIRED = {BLENDER: ("__init__.py", "blender_manifest.toml"),
             QGIS: ("__init__.py", "metadata.txt"),
             GODOT: ("plugin.cfg",),
             UNITY: ("package.json",),
             OBSIDIAN: ("main.js", "manifest.json")}
CLI_LIST_TIMEOUT_S = 60
CLI_INSTALL_TIMEOUT_S = 180


def _stamp_name(editor):
    return BITWIG_STAMP_NAME if editor == BITWIG else STAMP_NAME


def _tree_files(folder):
    """``{relative path: bytes}`` of every file under ``folder``, without
    bytecode, dot files and folders ending in ``~`` (Unity skips those:
    ``Tests~``)."""
    folder = Path(folder)
    files = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder)
        if not path.is_file() or path.suffix == ".pyc":
            continue
        if any(p == "__pycache__" or p.startswith(".") or p.endswith("~") for p in rel.parts):
            continue
        files[rel.as_posix()] = path.read_bytes()
    return files or None


def new_shipped_files(editor, source=None, folder=None):
    """``{relative path: bytes}`` to copy for a COPY_EDITORS or
    PROJECT_EDITORS editor, or None when this installation has no plugin
    files. ``folder`` (the folder it is copied to) is not used: every copy
    is the same."""
    source = Path(source or _NEW_SOURCES[editor])
    if editor == BITWIG:
        return {et.BITWIG_FILE: source.read_bytes()} if source.is_file() else None
    if editor == MAYA:
        plugin, mod = source / _MAYA_PLUGIN, source / "polykybd.mod"
        if not (plugin.is_file() and mod.is_file()):
            return None
        # The module path is relative to the .mod file, which sits beside the
        # module folder ("The location can be specified either as an absolute
        # path or as a path relative to the location of the .mod file being
        # read", Maya SDK, "Maya module paths, folders and versions"). So the
        # line never holds the user's home path, which can have a space, and
        # Maya documents no quoting for one.
        text = mod.read_text(encoding="utf-8").replace("PATH_TO_THIS_FOLDER",
                                                       "./" + et.MAYA_MODULE_DIR)
        return {_MAYA_PLUGIN: plugin.read_bytes(), MAYA_MOD_FILE: text.encode("utf-8")}
    if not all((source / name).is_file() for name in _REQUIRED[editor]):
        return None
    return _tree_files(source)


def _multi_base(editor, home, env, system):
    """The folder the Editors page shows for the editor, or None (projects)."""
    env = os.environ if env is None else env
    if editor == BLENDER:
        custom = env.get("BLENDER_USER_RESOURCES")
        return Path(custom) if custom else et.blender_config_bases(home, env, system)[0][1]
    if editor == MAYA:
        return et.maya_app_dir(home, env, system)
    if editor == QGIS:
        return et.qgis_profiles_dirs(home, env, system)[0][1]
    if editor == BITWIG:
        return et.bitwig_extensions_dir(home, env, system)
    return None


_PROJECT_PRESENT = {GODOT: et.godot_present, UNITY: et.unity_present,
                    OBSIDIAN: et.obsidian_present}


def _multi_targets(editor, home, env, system, state):
    """(program found, ``[(label, plugin folder)]``)."""
    if editor == BLENDER:
        targets = et.blender_targets(home, env, system)
    elif editor == MAYA:
        targets = et.maya_targets(home, env, system)
    elif editor == QGIS:
        targets = et.qgis_targets(home, env, system)
    elif editor == BITWIG:
        folder = et.bitwig_extensions_dir(home, env, system)
        targets = [("Bitwig Studio", folder)] if folder is not None else []
    else:
        targets = [(p, et.project_plugin_dir(editor, p)) for p in state.projects(editor)
                   if et.is_project(editor, p)]
        return bool(targets) or _PROJECT_PRESENT[editor](home, env, system), targets
    return bool(targets), targets


def _other_copy(editor, folder):
    """A copy of the plugin that this app did not write, which the program
    loads beside or instead of ours, or None."""
    folder = Path(folder)
    if editor == MAYA:
        # <appdir>/<version>/modules/polykybd -> <appdir>/modules/polykybd.mod
        for mod in (folder.parent / "polykybd.mod", folder.parents[2] / "modules" / "polykybd.mod"):
            if mod.exists():
                return mod
    elif editor == BLENDER:
        # Both places are <version>/<two folders>/polykybd_context_reporter.
        version_dir = folder.parents[2]
        others = [version_dir / "scripts" / "addons" / et.BLENDER_PACKAGE]
        others += sorted((version_dir / "extensions").glob("*/" + et.BLENDER_PACKAGE))
        for other in others:
            if other != folder and other.exists():
                return other
    elif editor == UNITY:
        project = folder.parents[1]
        if et.unity_manifest_names_package(project):
            return project / "Packages" / "manifest.json"
    return None


def _inside_project(folder, project):
    """The plugin folder, with every symbolic link followed, is inside the
    project folder: a project can hold a link (``addons`` -> ``~``) that
    would send the copy and its removal elsewhere."""
    try:
        return Path(project).resolve() in Path(folder).resolve().parents
    except (OSError, RuntimeError):
        return False


def _target_state(editor, folder, shipped, project=None):
    """(state, detail) of one copy of a MULTI_EDITORS editor. ``project`` is
    the project folder of a PROJECT_EDITORS copy."""
    if project is not None and not _inside_project(folder, project):
        log.warning("Editor plugin: %s leads out of the project %s; left alone.", folder, project)
        return STATE_MANUAL, str(folder)
    state = _copy_state(folder, shipped, _stamp_name(editor), shared=True)
    if state == STATE_MANUAL:
        return state, str(folder)
    if state == STATE_NOT_INSTALLED:
        other = _other_copy(editor, folder)
        if other is not None:
            return STATE_MANUAL, str(other)
    return state, ""


def _multi_states(editor, targets, source):
    """``[(label, folder, state, detail, shipped)]``."""
    out = []
    for label, folder in targets:
        shipped = new_shipped_files(editor, source, folder)
        project = label if editor in PROJECT_EDITORS else None
        state, detail = _target_state(editor, folder, shipped, project)
        out.append((label, folder, state, detail, shipped))
    return out


def _status_multi(editor, home, env, system, source, state):
    base = _multi_base(editor, home, env, system)
    if new_shipped_files(editor, source) is None:
        return EditorStatus(editor, STATE_NO_SOURCE, base, str(source or _NEW_SOURCES[editor]))
    present, targets = _multi_targets(editor, home, env, system, state)
    if not targets:
        if editor in PROJECT_EDITORS and present:
            return EditorStatus(editor, STATE_NO_PROJECT, None, "")
        return EditorStatus(editor, STATE_NOT_PRESENT, base, "")
    states = _multi_states(editor, targets, source)
    summary = _jetbrains_summary([(label, folder, st) for label, folder, st, _d, _s in states])
    if summary == STATE_MANUAL:
        detail = next(d for _l, _f, st, d, _s in states if st == STATE_MANUAL)
    else:
        detail = ", ".join(label for label, *_rest in states)
    return EditorStatus(editor, summary, base, detail)


def _install_target(editor, folder, state, detail, shipped):
    folder = Path(folder)
    if state == STATE_INSTALLED:
        return Result(editor, True, False, MSG_ALREADY.format(path=folder), None)
    if state == STATE_MODIFIED:
        return Result(editor, False, False, MSG_MODIFIED.format(path=folder), None)
    if state == STATE_MANUAL:
        return Result(editor, False, False, MSG_NOT_OURS.format(path=detail or folder), None)
    stamp = _stamp_name(editor)
    try:
        _write_copy(folder, shipped, read_stamp(folder, stamp), stamp)
    except OSError as exc:
        return Result(editor, False, False, MSG_WRITE_FAILED.format(path=folder, error=exc), None)
    log.info("Editor plugin: %s %s", editor, folder)
    msg = MSG_UPDATED if state == STATE_OUTDATED else MSG_INSTALLED
    return Result(editor, True, True, msg.format(path=folder), None)


def _remove_target(editor, folder, state):
    folder = Path(folder)
    if state == STATE_MODIFIED:
        return Result(editor, False, False, MSG_MODIFIED.format(path=folder), None)
    stamp = _stamp_name(editor)
    try:
        if editor == GODOT:
            # Godot 4.4 and later write <script>.uid beside each script.
            for rel in read_stamp(folder, stamp) or {}:
                try:
                    (folder / (rel + ".uid")).unlink()
                except FileNotFoundError:
                    # Godot before 4.4, or a script it has not opened yet,
                    # has no .uid file: nothing to delete.
                    continue
        if editor != BITWIG:
            for cache in sorted(folder.rglob("__pycache__")):
                shutil.rmtree(cache, ignore_errors=True)
        _delete_copy(folder, stamp, keep_folder=editor == BITWIG)
    except OSError as exc:
        return Result(editor, False, False, MSG_WRITE_FAILED.format(path=folder, error=exc), None)
    log.info("Editor plugin: removed %s from %s", editor, folder)
    return Result(editor, True, True, MSG_REMOVED.format(path=folder), None)


def _change_multi(editor, install, source, home=None, env=None, system=None, state=None,
                  only_outdated=False, projects=None):
    """Install or remove one copy per version, profile or project; one Result
    per copy acted on or that could not be. ``projects`` (PROJECT_EDITORS)
    names the project folders to act on instead of the remembered ones; a
    folder is remembered after a successful install and forgotten after a
    removal. ``only_outdated`` (the refresh at start) updates this app's older
    copies and touches nothing else."""
    name = EDITOR_NAMES[editor]
    if new_shipped_files(editor, source) is None:
        return [Result(editor, False, False,
                       MSG_NO_SOURCE.format(path=source or _NEW_SOURCES[editor]), None)]
    results = []
    if editor in PROJECT_EDITORS and projects:
        targets = []
        for p in projects:
            if et.is_project(editor, p):
                targets.append((str(Path(p)), et.project_plugin_dir(editor, p)))
            else:
                results.append(Result(editor, False, False, MSG_NOT_A_PROJECT.format(
                    path=p, editor=name, marker=et.PROJECT_MARKERS[editor]), None))
    else:
        _present, targets = _multi_targets(editor, home, env, system, state)
    for label, folder, st, detail, shipped in _multi_states(editor, targets, source):
        if only_outdated and st != STATE_OUTDATED:
            continue
        if install:
            r = _install_target(editor, folder, st, detail, shipped)
            if editor in PROJECT_EDITORS and r.ok and not state.add_project(editor, label):
                r = Result(editor, False, r.changed, MSG_STATE_NOT_SAVED.format(path=state.path), None)
            results.append(r)
        elif st in (STATE_INSTALLED, STATE_OUTDATED, STATE_MODIFIED):
            r = _remove_target(editor, folder, st)
            if editor in PROJECT_EDITORS and r.ok and not state.forget_project(editor, label):
                r = Result(editor, False, r.changed, MSG_STATE_NOT_SAVED.format(path=state.path), None)
            results.append(r)
        elif editor in PROJECT_EDITORS and st == STATE_NOT_INSTALLED:
            # A stale entry; if it cannot be forgotten now, the next pass tries again.
            state.forget_project(editor, label)
    if not results and not only_outdated:
        if install:
            msg = (MSG_NO_PROJECT.format(editor=name) if editor in PROJECT_EDITORS
                   else MSG_NOT_PRESENT.format(editor=name))
            results.append(Result(editor, False, False, msg, None))
        else:
            where = targets[0][1] if targets else _multi_base(editor, home, env, system)
            results.append(Result(editor, True, False,
                                  MSG_NOT_INSTALLED.format(path=where or name), None))
    return results


def vsix_digest(path):
    """SHA-256 over the names and bytes of the ``.vsix``'s entries, so a
    rebuild that only changes the zip's file times reads as the same."""
    h = hashlib.sha256()
    with zipfile.ZipFile(path) as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            if info.is_dir():
                continue
            h.update(info.filename.encode("utf-8") + b"\0")
            h.update(hashlib.sha256(zf.read(info)).digest())
    return h.hexdigest()


def vsix_version(path):
    """The ``version`` of the ``.vsix``'s ``extension/package.json``: what
    ``--list-extensions --show-versions`` shows once it is installed."""
    with zipfile.ZipFile(path) as zf:
        return str(json.loads(zf.read("extension/package.json")).get("version", ""))


def _run_cli(argv, timeout):
    """(exit code, stdout, stderr) of the editor's command line program."""
    kwargs = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # Audit (Sourcery dangerous-subprocess-use): argv is a list, no shell
    # parses it. argv[0] is what vscode_cli() found for code, cursor or
    # windsurf; the other items are fixed options, the extension id and the
    # .vsix path inside this installation.
    # nosemgrep
    proc = subprocess.run(argv, capture_output=True, timeout=timeout, **kwargs)
    return (proc.returncode, proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


def _status_cli(editor, which, home, env, system, source, state, run):
    vsix = Path(source or VSCODE_SOURCE)
    try:
        vsix_digest(vsix)
        vsix_version(vsix)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return EditorStatus(editor, STATE_NO_SOURCE, None, str(vsix))
    cli = et.vscode_cli(editor, which, home, env, system)
    if cli is None:
        return EditorStatus(editor, STATE_NOT_PRESENT, None, "")
    try:
        code, out, err = run([str(cli), "--list-extensions", "--show-versions"], CLI_LIST_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return EditorStatus(editor, STATE_NOT_PRESENT, cli, f"{cli.name} did not answer: {exc}")
    if code != 0:
        return EditorStatus(editor, STATE_NOT_PRESENT, cli,
                            f"{cli.name} did not answer: {err.strip() or code}")
    version = et.parse_extension_list(out)
    if version is None:
        return EditorStatus(editor, STATE_NOT_INSTALLED, cli, "")
    recorded = state.cli_digest(editor)
    if recorded is None or version != state.cli_version(editor):
        # Not installed by this app, or replaced since (the Marketplace or
        # Open VSX installs another version under the same id): left alone.
        return EditorStatus(editor, STATE_MANUAL, cli, f"{et.VSCODE_EXTENSION_ID}@{version}")
    state_ = STATE_INSTALLED if recorded == vsix_digest(vsix) else STATE_OUTDATED
    return EditorStatus(editor, state_, cli, "")


def _change_cli(st, install, source, state, run):
    editor, name = st.editor, EDITOR_NAMES[st.editor]
    vsix, cli = Path(source or VSCODE_SOURCE), Path(st.target)
    if install:
        if st.state == STATE_INSTALLED:
            return Result(editor, True, False, MSG_ALREADY.format(path=name), None)
        if st.state == STATE_MANUAL:
            return Result(editor, False, False,
                          MSG_CLI_NOT_OURS.format(editor=name, extension=st.detail), None)
        argv = [str(cli), "--install-extension", str(vsix), "--force"]
        shown = f"{cli.name} --install-extension {vsix.name}"
    else:
        if st.state == STATE_MANUAL:
            return Result(editor, False, False,
                          MSG_CLI_NOT_OURS.format(editor=name, extension=st.detail), None)
        if st.state not in (STATE_INSTALLED, STATE_OUTDATED):
            return Result(editor, True, False, MSG_NOT_INSTALLED.format(path=name), None)
        argv = [str(cli), "--uninstall-extension", et.VSCODE_EXTENSION_ID]
        shown = f"{cli.name} --uninstall-extension {et.VSCODE_EXTENSION_ID}"
    try:
        code, _out, err = run(argv, CLI_INSTALL_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Result(editor, False, False, MSG_CLI_FAILED.format(command=shown, error=exc), None)
    if code != 0:
        error = err.strip().splitlines()[-1] if err.strip() else f"exit code {code}"
        return Result(editor, False, False, MSG_CLI_FAILED.format(command=shown, error=error), None)
    log.info("Editor plugin: %s", shown)
    recorded = (state.set_cli(editor, vsix_digest(vsix), vsix_version(vsix)) if install
                else state.set_cli(editor, None))
    if not recorded:
        return Result(editor, False, True, MSG_STATE_NOT_SAVED.format(path=state.path), None)
    return Result(editor, True, True,
                  (MSG_CLI_INSTALLED if install else MSG_CLI_REMOVED).format(command=shown), None)


def _status_jupyterlab(which, home, env, system, source):
    src = Path(source or JUPYTERLAB_SOURCE)
    if not (src / "pyproject.toml").is_file():
        return EditorStatus(JUPYTERLAB, STATE_NO_SOURCE, None, str(src))
    if not et.jupyterlab_present(which, home, env, system):
        return EditorStatus(JUPYTERLAB, STATE_NOT_PRESENT, None, "")
    return EditorStatus(JUPYTERLAB, STATE_COMMAND, None, et.jupyterlab_install_command(src))


def _status_new(editor, home, env, which, system, source, state, run):
    if editor in MULTI_EDITORS:
        return _status_multi(editor, home, env, system, source, state)
    if editor in CLI_EDITORS:
        return _status_cli(editor, which, home, env, system, source, state, run)
    return _status_jupyterlab(which, home, env, system, source)


def _change_new(st, install, source, home, env, system, state, run, projects):
    """What install or remove did for a NEW_EDITORS editor: a list of Result."""
    editor, name = st.editor, EDITOR_NAMES[st.editor]
    explicit = editor in PROJECT_EDITORS and bool(projects)
    if st.state == STATE_NOT_PRESENT and not explicit:
        return [Result(editor, False, False, MSG_NOT_PRESENT.format(editor=name), None)]
    if st.state == STATE_NO_SOURCE:
        return [Result(editor, False, False, MSG_NO_SOURCE.format(path=st.detail), None)]
    if editor in MULTI_EDITORS:
        return _change_multi(editor, install, source, home, env, system, state, projects=projects)
    if editor in CLI_EDITORS:
        return [_change_cli(st, install, source, state, run)]
    command = st.detail if install else et.JUPYTERLAB_REMOVE_COMMAND
    return [Result(editor, True, False, MSG_RUN_COMMAND.format(command=command), None)]


def _state(home, state_file):
    """The remembered projects and installs: ``state_file`` (a path or a
    State), else the app's file; in memory only for a test's ``home``."""
    if isinstance(state_file, et.State):
        return state_file
    if state_file is not None:
        return et.State(state_file)
    return et.State(None if home is not None else et.default_state_file())


def default_selection(st):
    """Whether "all editors" includes ``st``: an editor found on this computer
    that this app can set up and has not yet, or set up with older files.

    GDB is never included: its script changes the terminal title in every GDB
    session, also one an IDE or a script starts. It is installed only when
    named (``--editor gdb``, or its box ticked in the dialog)."""
    if st.editor == GDB:
        return False
    return st.state in (STATE_NOT_INSTALLED, STATE_OUTDATED, STATE_STALE)


def needs_settings(port, token):
    """Whether the editors need the host's port or token set by hand: the
    plugins default to port 50164 and no token."""
    return int(port or DEFAULT_PORT) != DEFAULT_PORT or bool(token)


# --- install / remove -------------------------------------------------------

def _install_vim(st, shipped, now):
    folder = Path(st.target)
    backup = None
    if st.state == STATE_INSTALLED:
        return Result(st.editor, True, False, MSG_ALREADY.format(path=folder), None)
    if st.state == STATE_MODIFIED or (st.editor == HOUDINI and st.state == STATE_MANUAL):
        # A Houdini package this app did not write is the user's: never replaced.
        return Result(st.editor, False, False,
                      MSG_MODIFIED.format(path=st.detail or folder), None)
    try:
        if st.state == STATE_MANUAL and Path(st.detail) == folder:
            backup = _set_aside(folder, now)
        _write_copy(folder, shipped, read_stamp(folder))
    except OSError as exc:
        return Result(st.editor, False, False, MSG_WRITE_FAILED.format(path=folder, error=exc), backup)
    msg = MSG_UPDATED if st.state == STATE_OUTDATED or backup else MSG_INSTALLED
    log.info("Editor plugin: %s %s (backup %s)", st.editor, folder, backup)
    return Result(st.editor, True, True, msg.format(path=folder), backup)


def _install_init(st, shipped, now, home=None, env=None, system=None):
    init = Path(st.target)
    if st.editor == GDB:
        lisp_dir = gdb_plugin_dir(home, env, system)
    else:
        lisp_dir = emacs_lisp_dir(init)
    if st.state == STATE_INSTALLED:
        return Result(st.editor, True, False, MSG_ALREADY.format(path=init), None)
    if st.state == STATE_MODIFIED:
        return Result(st.editor, False, False, MSG_MODIFIED.format(path=lisp_dir), None)
    doc = _read_init(init)
    exists = doc is not None
    if doc is None:
        doc = _Text(b"", "utf-8")
    text = doc.text
    found, orphan, _rest = _init_blocks(text, st.editor)
    if orphan:
        return Result(st.editor, False, False, MSG_NO_END_MARKER.format(path=init), None)
    nl = "\r\n" if "\r\n" in text else "\n"
    try:
        if _copy_state(lisp_dir, shipped) != STATE_INSTALLED:
            _write_copy(lisp_dir, shipped, read_stamp(lisp_dir))
    except OSError as exc:
        return Result(st.editor, False, False, MSG_WRITE_FAILED.format(path=lisp_dir, error=exc), None)
    block = doc.piece(_block_for(st.editor, lisp_dir, nl))
    if found:
        new = text[:found[0][0]] + block
        prev = found[0][1]
        for s, e, _inner in found[1:]:
            new += text[prev:s]
            prev = e
        new += text[prev:]
    else:
        sep = nl if text and not text.endswith("\n") else ""
        new = text + doc.piece(sep) + block
    backup = None
    if new != text:
        try:
            if exists:
                backup = _backup(init, now)
            _write(init, doc.to_bytes(new))
        except OSError as exc:
            return Result(st.editor, False, False, MSG_WRITE_FAILED.format(path=init, error=exc), backup)
    log.info("Editor plugin: %s %s, init %s (backup %s)", st.editor, lisp_dir, init, backup)
    msg = MSG_EMACS_INSTALLED.format(path=lisp_dir, init=init)
    return Result(st.editor, True, True, msg, backup)


def _remove_vim(st):
    folder = Path(st.target)
    if st.state not in (STATE_INSTALLED, STATE_OUTDATED):
        if st.state == STATE_MODIFIED:
            return Result(st.editor, False, False, MSG_MODIFIED.format(path=folder), None)
        return Result(st.editor, True, False, MSG_NOT_INSTALLED.format(path=folder), None)
    try:
        _delete_copy(folder)
    except OSError as exc:
        return Result(st.editor, False, False, MSG_WRITE_FAILED.format(path=folder, error=exc), None)
    log.info("Editor plugin: removed %s from %s", st.editor, folder)
    return Result(st.editor, True, True, MSG_REMOVED.format(path=folder), None)


def _remove_init(st, now, home=None, env=None, system=None):
    init = Path(st.target)
    doc = _read_init(init)
    found, _orphan, _rest = _init_blocks(doc.text, st.editor) if doc is not None else ([], False, "")
    if st.editor == GDB:
        lisp_dir = gdb_plugin_dir(home, env, system)
    else:
        lisp_dir = emacs_lisp_dir(init)
    if not found:
        return Result(st.editor, True, False, MSG_NOT_INSTALLED.format(path=init), None)
    text, new, prev = doc.text, "", 0
    for s, e, _inner in found:
        new += text[prev:s]
        prev = e
    new += text[prev:]
    try:
        backup = _backup(init, now)
        _write(init, doc.to_bytes(new))
    except OSError as exc:
        return Result(st.editor, False, False, MSG_WRITE_FAILED.format(path=init, error=exc), None)
    msg = MSG_EMACS_REMOVED.format(init=init)
    if read_stamp(lisp_dir) is not None and _copy_state(lisp_dir, {}) != STATE_MODIFIED:
        try:
            _delete_copy(lisp_dir)
            msg = MSG_EMACS_REMOVED_ALL.format(init=init, path=lisp_dir)
        except OSError as exc:
            log.warning("Editor plugin: could not delete %s: %s", lisp_dir, exc)
    log.info("Editor plugin: removed %s block from %s (backup %s)", st.editor, init, backup)
    return Result(st.editor, True, True, msg, backup)


def _change_jetbrains(st, install, source, now=None, home=None, env=None, system=None,
                      only_outdated=False):
    """Install or remove the plugin in each IDE; one Result per IDE that was
    acted on or could not be. ``only_outdated`` (the refresh at start) updates
    this app's older copies and touches nothing else."""
    shipped = shipped_files(JETBRAINS, source)
    if shipped is None:
        return [Result(JETBRAINS, False, False,
                       MSG_NO_SOURCE.format(path=source or JETBRAINS_SOURCE), None)]
    results = []
    for sel, folder, state in _jetbrains_states(shipped, home, env, system):
        one = EditorStatus(JETBRAINS, state, folder, str(folder) if state == STATE_MANUAL else "")
        if only_outdated and state != STATE_OUTDATED:
            continue
        if install:
            results.append(_install_vim(one, shipped, now))
        elif state in (STATE_INSTALLED, STATE_OUTDATED, STATE_MODIFIED):
            results.append(_remove_vim(one))
    if not results and not only_outdated:
        if install:
            results.append(Result(JETBRAINS, False, False,
                                  MSG_NOT_PRESENT.format(editor="JetBrains IDE"), None))
        else:
            results.append(Result(JETBRAINS, True, False,
                                  MSG_NOT_INSTALLED.format(path=st.target), None))
    return results


def _change(st, install, sources, now=None, home=None, env=None, system=None, state=None,
            run=None, projects=None):
    """What install or remove did, as a Result, or for JETBRAINS and the
    NEW_EDITORS a list of them (one per IDE, version, profile or project)."""
    if st.editor in NEW_EDITORS:
        return _change_new(st, install, sources.get(st.editor), home, env, system,
                           state if state is not None else _state(home, None), run or _run_cli,
                           (projects or {}).get(st.editor))
    if st.state == STATE_NOT_PRESENT:
        return Result(st.editor, False, False, MSG_NOT_PRESENT.format(editor=st.editor), None)
    if st.state == STATE_NO_SOURCE:
        return Result(st.editor, False, False, MSG_NO_SOURCE.format(path=st.detail), None)
    if st.editor == JETBRAINS:
        return _change_jetbrains(st, install, sources.get(JETBRAINS), now, home, env, system)
    if not install:
        if st.editor in INIT_EDITORS:
            return _remove_init(st, now, home, env, system)
        return _remove_vim(st)
    shipped = shipped_files(st.editor, sources.get(st.editor))
    if shipped is None:
        return Result(st.editor, False, False, MSG_NO_SOURCE.format(path=st.detail), None)
    if st.editor in INIT_EDITORS:
        return _install_init(st, shipped, now, home, env, system)
    return _install_vim(st, shipped, now)


def _apply(install, editors, statuses, home, env, which, system, vim_source, emacs_source,
           gdb_source=None, ida_source=None, ableton_source=None, houdini_source=None,
           jetbrains_source=None, freecad_source=None, sources=None, state_file=None, run=None,
           projects=None):
    state = _state(home, state_file)
    run = run or _run_cli
    if statuses is None:
        statuses = status(editors, home=home, env=env, which=which, system=system,
                          vim_source=vim_source, emacs_source=emacs_source, gdb_source=gdb_source,
                          ida_source=ida_source, ableton_source=ableton_source,
                          houdini_source=houdini_source, jetbrains_source=jetbrains_source,
                          freecad_source=freecad_source, sources=sources, state_file=state,
                          run=run)
    all_sources = _sources(vim_source, emacs_source, gdb_source, ida_source, ableton_source,
                           houdini_source, jetbrains_source, freecad_source)
    all_sources.update(sources or {})
    results = []
    for st in statuses:
        if editors is not None and st.editor not in editors:
            continue
        if editors is None:
            if install and not default_selection(st):
                continue
            if not install and st.state not in (STATE_INSTALLED, STATE_OUTDATED, STATE_STALE):
                # One IDE's (version's, project's) copy can be this app's while
                # the summary is another state.
                if (st.editor not in (JETBRAINS,) + MULTI_EDITORS
                        or st.state in (STATE_NOT_PRESENT, STATE_NO_SOURCE, STATE_NO_PROJECT)):
                    continue
        r = _change(st, install, all_sources, home=home, env=env, system=system, state=state,
                    run=run, projects=projects)
        if isinstance(r, list):
            results.extend(r)
        else:
            results.append(r)
    return results


def install(editors=None, statuses=None, home=None, env=None, which=None,
            system=None, vim_source=None, emacs_source=None, gdb_source=None,
            ida_source=None, ableton_source=None, houdini_source=None, jetbrains_source=None,
            freecad_source=None, sources=None, state_file=None, run=None, projects=None):
    """Copy the plugin for each editor (the ones default_selection() picks
    when ``editors`` is None). Returns a list of Result; JETBRAINS adds one
    per IDE, the MULTI_EDITORS one per version, profile or project.
    ``projects`` maps a PROJECT_EDITORS editor to the project folders to
    install into (and remember); without it, the remembered ones."""
    return _apply(True, editors, statuses, home, env, which, system, vim_source, emacs_source,
                  gdb_source, ida_source, ableton_source, houdini_source, jetbrains_source,
                  freecad_source, sources, state_file, run, projects)


def remove(editors=None, statuses=None, home=None, env=None, which=None,
           system=None, vim_source=None, emacs_source=None, gdb_source=None,
           ida_source=None, ableton_source=None, houdini_source=None, jetbrains_source=None,
           freecad_source=None, sources=None, state_file=None, run=None, projects=None):
    """Delete this app's copy and, for Emacs and GDB, the marked block.
    ``projects`` limits a PROJECT_EDITORS editor to those project folders."""
    return _apply(False, editors, statuses, home, env, which, system, vim_source, emacs_source,
                  gdb_source, ida_source, ableton_source, houdini_source, jetbrains_source,
                  freecad_source, sources, state_file, run, projects)


def refresh_installed(home=None, env=None, which=None, system=None,
                      vim_source=None, emacs_source=None, gdb_source=None,
                      ida_source=None, ableton_source=None, houdini_source=None,
                      jetbrains_source=None, freecad_source=None, sources=None,
                      state_file=None, run=None):
    """Copy the shipped files again for each editor whose copy is this app's
    and older than them. Runs at every start, so an update reaches the
    editors without a visit to the dialog. Returns the editors refreshed.
    Never raises.

    A VS Code-type editor is asked (its command line program started) only
    when this app installed the extension there; JupyterLab never."""
    refreshed = []
    try:
        state = _state(home, state_file)
        run = run or _run_cli
        editors = [e for e in EDITORS
                   if e != JUPYTERLAB and (e not in CLI_EDITORS or state.cli_digest(e))]
        statuses = status(editors, home=home, env=env, which=which, system=system,
                          vim_source=vim_source, emacs_source=emacs_source, gdb_source=gdb_source,
                          ida_source=ida_source, ableton_source=ableton_source,
                          houdini_source=houdini_source, jetbrains_source=jetbrains_source,
                          freecad_source=freecad_source, sources=sources, state_file=state,
                          run=run)
    except Exception:  # noqa: BLE001 - a start must not fail for this
        log.warning("Editor plugin refresh: status failed", exc_info=True)
        return refreshed
    all_sources = _sources(vim_source, emacs_source, gdb_source, ida_source, ableton_source,
                           houdini_source, jetbrains_source, freecad_source)
    all_sources.update(sources or {})
    for st in statuses:
        if st.state != STATE_OUTDATED:
            continue
        try:
            if st.editor == JETBRAINS:
                # Only the IDEs whose copy is older: Install sets up the others.
                rs = _change_jetbrains(st, True, all_sources.get(JETBRAINS), home=home, env=env,
                                       system=system, only_outdated=True)
            elif st.editor in MULTI_EDITORS:
                # Only the versions, profiles and projects whose copy is older.
                rs = _change_multi(st.editor, True, all_sources.get(st.editor), home=home,
                                   env=env, system=system, state=state, only_outdated=True)
            elif st.editor in CLI_EDITORS:
                rs = [_change_cli(st, True, all_sources.get(st.editor), state, run)]
            else:
                rs = [_change(st, True, all_sources, home=home, env=env, system=system)]
        except Exception:  # noqa: BLE001
            log.warning("Editor plugin refresh failed for %s", st.editor, exc_info=True)
            continue
        for r in rs:
            if r.changed:
                if st.editor not in refreshed:
                    refreshed.append(st.editor)
                log.info("Editor plugin refreshed for %s: %s", st.editor, r.message)
    return refreshed


def start_refresh_thread():
    """Run refresh_installed() on a daemon thread, so a start never waits on
    the file system. The tray app, the daemon and the forwarder each call it;
    two of them on one computer write the same bytes, file by file through a
    rename, so the second finds nothing to do or rewrites identical files."""
    threading.Thread(target=refresh_installed, name="editor-plugin-refresh",
                     daemon=True).start()
