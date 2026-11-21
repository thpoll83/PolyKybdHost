"""Where the programs of Integrations > Editors load a PolyKybd plugin from,
for the programs added after JetBrains and FreeCAD: Blender, Maya, QGIS,
Bitwig Studio, VS Code and its forks, JupyterLab, Godot, Unity and Obsidian.

Only paths and lookups, no copying: :mod:`polyhost.services.editor_plugins`
does the copying and the stamps. Every function takes ``home``, ``env`` and
``system`` so the tests can give a fake home for each OS.

A ``home`` that is given (a test's home) never counts a program installed at
an absolute system path (``/Applications/...``, ``C:\\Program Files\\...``),
as ``_resolve_present`` in editor_plugins does.

The remembered project folders (Godot, Unity, Obsidian) and the record of
which VS Code-type editor this app installed the extension into are in
``editor_plugins.json`` in the app's config folder (:func:`default_state_file`),
not in ``settings.yaml``: they are written by the Editors page and ``polyctl``,
are not a preference the Settings dialog shows, and a project folder name
must not go into a log bundle with the settings.

Qt-free and stdlib-only, except platformdirs for the config folder.
"""
import json
import os
import platform
import re
import shutil
import tempfile
from pathlib import Path

from polyhost.util import filelock

# --- Blender -------------------------------------------------------------------

BLENDER_PACKAGE = "polykybd_context_reporter"
# blender-addon/README.md: Blender 4.2+ as an extension, 3.6-4.1 as an add-on.
BLENDER_MIN = (3, 6)
BLENDER_EXTENSIONS_FROM = (4, 2)
_VERSION_DIR_RE = re.compile(r"^(\d+)\.(\d+)$")


def _home(home):
    return Path(home) if home is not None else Path.home()


def _appdata(home, env):
    appdata = env.get("APPDATA")
    return Path(appdata) if appdata else _home(home) / "AppData" / "Roaming"


def _localappdata(home, env):
    local = env.get("LOCALAPPDATA")
    return Path(local) if local else _home(home) / "AppData" / "Local"


def _xdg(home, env, var, default):
    value = env.get(var)
    return Path(value) if value else _home(home) / default


def blender_config_bases(home=None, env=None, system=None):
    """``[(label prefix, folder)]`` of the folders that hold one
    ``<major>.<minor>`` folder per Blender version (Blender manual, "Blender's
    Directory Layout": ``$XDG_CONFIG_HOME/blender`` or ``~/.config/blender``
    on Linux, ``~/Library/Application Support/Blender`` on macOS,
    ``%APPDATA%\\Blender Foundation\\Blender`` on Windows). On Linux also the
    Flatpak's and the Snap's folders."""
    env = os.environ if env is None else env
    system = system or platform.system()
    h = _home(home)
    if system == "Windows":
        return [("", _appdata(home, env) / "Blender Foundation" / "Blender")]
    if system == "Darwin":
        return [("", h / "Library" / "Application Support" / "Blender")]
    return [("", _xdg(home, env, "XDG_CONFIG_HOME", ".config") / "blender"),
            ("Flatpak ", h / ".var" / "app" / "org.blender.Blender" / "config" / "blender"),
            ("Snap ", h / "snap" / "blender" / "current" / ".config" / "blender")]


def blender_addon_dir(version_dir, version):
    """Where a Blender version loads the add-on from: the ``user_default``
    extension repository (``<version>/extensions/user_default``, where
    Install from Disk puts an extension) from 4.2, the user ``scripts/addons``
    folder before."""
    version_dir = Path(version_dir)
    if version >= BLENDER_EXTENSIONS_FROM:
        return version_dir / "extensions" / "user_default" / BLENDER_PACKAGE
    return version_dir / "scripts" / "addons" / BLENDER_PACKAGE


def blender_targets(home=None, env=None, system=None):
    """``[(label, add-on folder)]`` for each Blender version, 3.6 or newer,
    that has run for this user (Blender writes its version folder at the
    first start). ``BLENDER_USER_RESOURCES`` replaces the versioned folders
    with one folder, taken as 4.2 or newer."""
    env = os.environ if env is None else env
    custom = env.get("BLENDER_USER_RESOURCES")
    if custom:
        return [("BLENDER_USER_RESOURCES", blender_addon_dir(custom, BLENDER_EXTENSIONS_FROM))] \
            if Path(custom).is_dir() else []
    out = []
    for prefix, base in blender_config_bases(home, env, system):
        for version, d in _version_dirs(base):
            if version >= BLENDER_MIN:
                out.append((f"{prefix}{version[0]}.{version[1]}", blender_addon_dir(d, version)))
    return out


def _version_dirs(base):
    """``[((major, minor), folder)]`` of the ``<major>.<minor>`` folders in base."""
    found = []
    try:
        entries = list(Path(base).iterdir())
    except OSError:
        return found
    for d in entries:
        m = _VERSION_DIR_RE.match(d.name)
        if m and d.is_dir():
            found.append(((int(m.group(1)), int(m.group(2))), d))
    return sorted(found)


# --- Maya ----------------------------------------------------------------------

MAYA_MIN = 2022           # maya-plugin/README.md: Maya 2022 and later
MAYA_MODULE_DIR = "polykybd"
_MAYA_VERSION_RE = re.compile(r"^(\d{4})$")


def maya_app_dir(home=None, env=None, system=None):
    """``MAYA_APP_DIR``, else its default (Maya help, "File path variables"):
    ``~/Documents/maya`` (Windows), ``~/Library/Preferences/Autodesk/maya``
    (macOS), ``~/maya`` (Linux)."""
    env = os.environ if env is None else env
    system = system or platform.system()
    if env.get("MAYA_APP_DIR"):
        return Path(env["MAYA_APP_DIR"])
    h = _home(home)
    if system == "Windows":
        return h / "Documents" / "maya"
    if system == "Darwin":
        return h / "Library" / "Preferences" / "Autodesk" / "maya"
    return h / "maya"


def maya_targets(home=None, env=None, system=None):
    """``[(version, module folder)]`` for each Maya version, 2022 or newer,
    that has run for this user. The module goes to
    ``<MAYA_APP_DIR>/<version>/modules/polykybd`` with its ``polykybd.mod``
    beside it, which names the folder as ``./polykybd``: ``<MAYA_APP_DIR>/<version>/modules`` is on the default
    ``MAYA_MODULE_PATH`` of every OS (Maya help, "File path variables")."""
    base = maya_app_dir(home, env, system)
    out = []
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return out
    for d in entries:
        m = _MAYA_VERSION_RE.match(d.name)
        if m and d.is_dir() and int(m.group(1)) >= MAYA_MIN:
            out.append((d.name, d / "modules" / MAYA_MODULE_DIR))
    return out


# --- QGIS ----------------------------------------------------------------------

QGIS_PACKAGE = "polykybd_context_reporter"


def qgis_profiles_dirs(home=None, env=None, system=None):
    """``[(label prefix, profiles folder)]`` (QGIS user manual, "User
    profiles"): ``%APPDATA%\\QGIS\\QGIS3\\profiles`` (Windows),
    ``~/Library/Application Support/QGIS/QGIS3/profiles`` (macOS),
    ``~/.local/share/QGIS/QGIS3/profiles`` (Linux, and the Flatpak's)."""
    env = os.environ if env is None else env
    system = system or platform.system()
    h = _home(home)
    if system == "Windows":
        return [("", _appdata(home, env) / "QGIS" / "QGIS3" / "profiles")]
    if system == "Darwin":
        return [("", h / "Library" / "Application Support" / "QGIS" / "QGIS3" / "profiles")]
    return [("", _xdg(home, env, "XDG_DATA_HOME", ".local/share") / "QGIS" / "QGIS3" / "profiles"),
            ("Flatpak ", h / ".var" / "app" / "org.qgis.qgis" / "data" / "QGIS" / "QGIS3"
             / "profiles")]


def qgis_targets(home=None, env=None, system=None):
    """``[(profile, plugin folder)]``: ``<profile>/python/plugins/
    polykybd_context_reporter`` for each QGIS user profile (QGIS creates
    ``default`` at its first start)."""
    out = []
    for prefix, base in qgis_profiles_dirs(home, env, system):
        try:
            entries = sorted(base.iterdir())
        except OSError:
            continue
        for d in entries:
            if d.is_dir():
                out.append((prefix + d.name, d / "python" / "plugins" / QGIS_PACKAGE))
    return out


# --- Bitwig Studio -------------------------------------------------------------

BITWIG_FILE = "PolyKybdContextReporter.bwextension"


def bitwig_extensions_dir(home=None, env=None, system=None):
    """The Extensions folder (Bitwig, "Installation guide" for controller
    scripts): ``~/Documents/Bitwig Studio/Extensions`` on Windows and macOS,
    ``~/Bitwig Studio/Extensions`` on Linux. None when Bitwig Studio has not
    run for this user (it creates ``Bitwig Studio`` at its first start)."""
    system = system or platform.system()
    h = _home(home)
    base = (h / "Documents" if system in ("Windows", "Darwin") else h) / "Bitwig Studio"
    return base / "Extensions" if base.is_dir() else None


# --- VS Code, Cursor, Windsurf -------------------------------------------------

VSCODE_EXTENSION_ID = "polykybd.polykybd-mode-reporter"


def _cli_candidates(editor, home, env, system):
    """Standard install places of the editor's command line program, after
    PATH. The paths relative to the user's folders count in a test's home;
    the absolute ones only for the real home."""
    h = _home(home)
    local = _localappdata(home, env)
    user, absolute = [], []
    if editor == "vscode":
        if system == "Windows":
            user = [local / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd"]
            absolute = [Path(r"C:\Program Files\Microsoft VS Code\bin\code.cmd")]
        elif system == "Darwin":
            tail = Path("Visual Studio Code.app/Contents/Resources/app/bin/code")
            user = [h / "Applications" / tail]
            absolute = [Path("/Applications") / tail]
        else:
            absolute = [Path("/usr/share/code/bin/code"), Path("/snap/bin/code")]
    elif editor == "cursor":
        if system == "Windows":
            user = [local / "Programs" / "cursor" / "resources" / "app" / "bin" / "cursor.cmd"]
        elif system == "Darwin":
            tail = Path("Cursor.app/Contents/Resources/app/bin/cursor")
            user = [h / "Applications" / tail]
            absolute = [Path("/Applications") / tail]
        else:
            absolute = [Path("/usr/share/cursor/bin/cursor")]
    elif editor == "windsurf":
        if system == "Windows":
            user = [local / "Programs" / "Windsurf" / "bin" / "windsurf.cmd"]
        elif system == "Darwin":
            tail = Path("Windsurf.app/Contents/Resources/app/bin/windsurf")
            user = [h / "Applications" / tail]
            absolute = [Path("/Applications") / tail]
        else:
            absolute = [Path("/usr/share/windsurf/bin/windsurf")]
    return user + (absolute if home is None else [])


def vscode_cli(editor, which=None, home=None, env=None, system=None):
    """The command line program of VS Code (``code``), Cursor (``cursor``) or
    Windsurf (``windsurf``): on PATH, else in the standard install folder.
    None when none is found."""
    env = os.environ if env is None else env
    system = system or platform.system()
    which = which or shutil.which
    found = which(editor if editor != "vscode" else "code")
    if found:
        return Path(found)
    for p in _cli_candidates(editor, home, env, system):
        if p.is_file():
            return p
    return None


_POLICY_WORDS = re.compile(r"allowed list|not allowed|extensions\.allowed|policy|AllowedExtensions", re.I)

_USER_FOLDER = {"vscode": "Code", "cursor": "Cursor", "windsurf": "Windsurf"}


def _user_settings(editor, home, env, system):
    """The editor's user ``settings.json``."""
    name = _USER_FOLDER[editor]
    if system == "Windows":
        return _appdata(home, env) / name / "User" / "settings.json"
    if system == "Darwin":
        return _home(home) / "Library" / "Application Support" / name / "User" / "settings.json"
    xdg = env.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else _home(home) / ".config"
    return base / name / "User" / "settings.json"


def extension_policy_reason(editor, output="", home=None, env=None, system=None):
    """Why the editor may refuse an extension that is not on its allowed list,
    or None. VS Code 1.96+ and its forks install only the extensions named by
    the ``extensions.allowed`` setting or by an organization policy (Windows
    registry ``AllowedExtensions``, Linux ``/etc/vscode/policy.json``). The
    command line program often prints no reason, so this reads the output
    first, then the places the rule is kept. Returns ``"output"``,
    ``"settings"`` or ``"policy"``."""
    env = os.environ if env is None else env
    system = system or platform.system()
    if _POLICY_WORDS.search(output or ""):
        return "output"
    try:
        text = _user_settings(editor, home, env, system).read_text(encoding="utf-8", errors="replace")
        if "extensions.allowed" in text:
            return "settings"
    except OSError:
        pass  # no settings file, or unreadable: the rule is not set there
    if home is not None:
        return None  # a test's home never reads the machine's policy
    if system == "Windows":
        try:
            import winreg
            for key in (r"SOFTWARE\Policies\Microsoft\VSCode", r"SOFTWARE\Policies\Microsoft\Cursor"):
                for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    try:
                        with winreg.OpenKey(hive, key) as k:
                            winreg.QueryValueEx(k, "AllowedExtensions")
                            return "policy"
                    except OSError:
                        continue
        except ImportError:
            pass  # no winreg module (not a real Windows Python): no registry to read
    elif system == "Linux":
        try:
            if "AllowedExtensions" in Path("/etc/vscode/policy.json").read_text(encoding="utf-8"):
                return "policy"
        except OSError:
            pass  # no policy file, or unreadable: no policy here
    return None


def parse_extension_list(text, ext_id=VSCODE_EXTENSION_ID):
    """The version of ``ext_id`` in ``--list-extensions --show-versions``
    output (``publisher.name@1.0.0`` per line), or None."""
    want = ext_id.lower()
    for line in text.splitlines():
        name, _sep, version = line.strip().partition("@")
        if name.lower() == want:
            return version or "?"
    return None


# --- JupyterLab ----------------------------------------------------------------

def jupyterlab_present(which=None, home=None, env=None, system=None):
    """``jupyter-lab`` or ``jupyter`` on PATH, or JupyterLab Desktop's user
    folder (``%APPDATA%\\jupyterlab-desktop``, ``~/Library/jupyterlab-desktop``,
    ``~/.config/jupyterlab-desktop``)."""
    env = os.environ if env is None else env
    system = system or platform.system()
    which = which or shutil.which
    if which("jupyter-lab") or which("jupyter"):
        return True
    if system == "Windows":
        desktop = _appdata(home, env) / "jupyterlab-desktop"
    elif system == "Darwin":
        desktop = _home(home) / "Library" / "jupyterlab-desktop"
    else:
        desktop = _xdg(home, env, "XDG_CONFIG_HOME", ".config") / "jupyterlab-desktop"
    return desktop.is_dir()


def _quote(path):
    return f'"{path}"'


def jupyterlab_install_command(source):
    """The command that installs the extension into the Python environment it
    runs in (jupyterlab-extension/README.md, Install)."""
    return f"python -m pip install {_quote(Path(source))}"


JUPYTERLAB_REMOVE_COMMAND = "python -m pip uninstall polykybd_jupyterlab"


# --- Godot, Unity, Obsidian: per project ------------------------------------------

def _first_dir(paths):
    return any(p.is_dir() for p in paths)


def godot_present(home=None, env=None, system=None):
    """Godot's editor data folder exists (Godot docs, "File paths in Godot
    projects": ``%APPDATA%\\Godot``, ``~/Library/Application Support/Godot``,
    ``~/.config/godot``; also the Flatpak's)."""
    env = os.environ if env is None else env
    system = system or platform.system()
    h = _home(home)
    if system == "Windows":
        return _first_dir([_appdata(home, env) / "Godot"])
    if system == "Darwin":
        return _first_dir([h / "Library" / "Application Support" / "Godot"])
    return _first_dir([_xdg(home, env, "XDG_CONFIG_HOME", ".config") / "godot",
                       h / ".var" / "app" / "org.godotengine.Godot" / "config" / "godot"])


def unity_present(home=None, env=None, system=None):
    """Unity Hub's or the Unity Editor's user folder exists."""
    env = os.environ if env is None else env
    system = system or platform.system()
    h = _home(home)
    if system == "Windows":
        return _first_dir([_appdata(home, env) / "UnityHub",
                           _localappdata(home, env) / "Unity"])
    if system == "Darwin":
        return _first_dir([h / "Library" / "Application Support" / "UnityHub",
                           h / "Library" / "Unity"])
    cfg = _xdg(home, env, "XDG_CONFIG_HOME", ".config")
    return _first_dir([cfg / "UnityHub", cfg / "unity3d"])


def obsidian_present(home=None, env=None, system=None):
    """Obsidian's app folder exists (``%APPDATA%\\obsidian``,
    ``~/Library/Application Support/obsidian``, ``~/.config/obsidian``, and
    the Flatpak's and the Snap's)."""
    env = os.environ if env is None else env
    system = system or platform.system()
    h = _home(home)
    if system == "Windows":
        return _first_dir([_appdata(home, env) / "obsidian"])
    if system == "Darwin":
        return _first_dir([h / "Library" / "Application Support" / "obsidian"])
    return _first_dir([_xdg(home, env, "XDG_CONFIG_HOME", ".config") / "obsidian",
                       h / ".var" / "app" / "md.obsidian.Obsidian" / "config" / "obsidian",
                       h / "snap" / "obsidian" / "current" / ".config" / "obsidian"])


# The file or folder that makes a folder a project of that program, and where
# the plugin goes in it.
PROJECT_MARKERS = {
    "godot": "project.godot",
    "unity": "Packages/manifest.json",
    "obsidian": ".obsidian",
}
PROJECT_PLUGIN_DIRS = {
    # godot-plugin/README.md: <project>/addons/polykybd_reporter/
    "godot": "addons/polykybd_reporter",
    # An embedded package (Unity manual, "Embedded dependencies"): Unity
    # loads every package folder in the project's Packages folder.
    "unity": "Packages/org.polykybd.context-reporter",
    # obsidian-plugin/README.md: <vault>/.obsidian/plugins/<id>/
    "obsidian": ".obsidian/plugins/polykybd-mode-reporter",
}
UNITY_PACKAGE_NAME = "org.polykybd.context-reporter"


def is_project(editor, folder):
    """Whether ``folder`` is a Godot project (``project.godot``), a Unity
    project (``Packages/manifest.json``) or an Obsidian vault (``.obsidian``)."""
    marker = Path(folder) / PROJECT_MARKERS[editor]
    return marker.is_dir() if editor == "obsidian" else marker.is_file()


def project_plugin_dir(editor, folder):
    return Path(folder) / PROJECT_PLUGIN_DIRS[editor]


def unity_manifest_names_package(project):
    """The project's ``Packages/manifest.json`` lists the package as a
    dependency (added by git URL or from disk in the Package Manager)."""
    try:
        data = json.loads((Path(project) / "Packages" / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    deps = data.get("dependencies") if isinstance(data, dict) else None
    return isinstance(deps, dict) and UNITY_PACKAGE_NAME in deps


# --- the state file ------------------------------------------------------------

STATE_FILE_NAME = "editor_plugins.json"


def default_state_file():
    from platformdirs import user_config_dir
    return Path(user_config_dir("PolyHost")) / STATE_FILE_NAME


class State:
    """``{"projects": {editor: [folder]}, "cli": {editor: {"digest": d,
    "version": v}}}``: the content digest and the version of the ``.vsix``
    this app installed with that editor's command line program.

    ``path`` None keeps it in memory only (a test's home)."""

    def __init__(self, path):
        self.path = Path(path) if path is not None else None
        self.data = {"projects": {}, "cli": {}}
        if self.path is not None:
            self.data = self._read()

    def _read(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        projects = data.get("projects") if isinstance(data.get("projects"), dict) else {}
        cli = data.get("cli") if isinstance(data.get("cli"), dict) else {}
        return {"projects": {k: [str(p) for p in v if isinstance(p, str)]
                             for k, v in projects.items() if isinstance(v, list)},
                "cli": {k: v for k, v in cli.items()
                        if isinstance(v, dict) and isinstance(v.get("digest"), str)}}

    def projects(self, editor):
        return list(self.data["projects"].get(editor, []))

    def cli_digest(self, editor):
        return (self.data["cli"].get(editor) or {}).get("digest")

    def cli_version(self, editor):
        return (self.data["cli"].get(editor) or {}).get("version")

    def update(self, change):
        """Apply ``change(data)`` to the file's current content under a lock,
        so the tray, the daemon and polyctl never undo each other's change.
        Never raises: the result says whether it was written."""
        if self.path is None:
            change(self.data)
            return True
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with filelock.exclusive(f"{self.path}.lock"):
                self.data = self._read()
                change(self.data)
                fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".editor_plugins-")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        json.dump(self.data, fh, indent=1, sort_keys=True)
                    os.replace(tmp, self.path)
                except (OSError, TypeError, ValueError):
                    # os.replace or the write failed (OSError), or the data
                    # was not JSON (TypeError, ValueError): delete the
                    # temporary file, then let the caller see the error.
                    try:
                        os.unlink(tmp)
                    except FileNotFoundError:
                        # os.replace may already have moved it.
                        pass
                    raise
            return True
        except (OSError, TypeError, ValueError):
            return False

    def add_project(self, editor, folder):
        folder = str(Path(folder))

        def change(data):
            lst = data["projects"].setdefault(editor, [])
            if folder not in lst:
                lst.append(folder)
        return self.update(change)

    def forget_project(self, editor, folder):
        folder = str(Path(folder))

        def change(data):
            lst = data["projects"].get(editor, [])
            data["projects"][editor] = [p for p in lst if p != folder]
        return self.update(change)

    def set_cli(self, editor, digest, version=None):
        def change(data):
            if digest is None:
                data["cli"].pop(editor, None)
            else:
                data["cli"][editor] = {"digest": digest, "version": version}
        return self.update(change)
