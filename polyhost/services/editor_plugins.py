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
- Binary Ninja: ``polykybd_mode_reporter/`` (``binaryninja-plugin/``) into
  the user plugins folder, ``<user folder>/plugins/`` (``BN_USER_DIRECTORY``,
  else ``~/.binaryninja``, ``%APPDATA%/Binary Ninja`` or
  ``~/Library/Application Support/Binary Ninja``). It reports the view type and
  IL level of the focused pane.

Each copy gets a stamp file with the SHA-256 of every file written.
:func:`refresh_installed` runs at every start: it copies the shipped files
again where a stamp exists and the shipped files changed (an update). A copy
whose files differ from the stamp was changed by hand and is left alone.

The init file is the user's own: it is changed the way ``shell_title``
changes a shell startup file (bytes outside the block are kept, a timestamped
copy is written first), with that module's helpers.

Qt-free and stdlib-only: ``polyctl`` imports it without PyQt5, and the tray
dialog (``gui/shell_title_dialog.py``) only shows it.
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
from collections import namedtuple
from pathlib import Path

from polyhost.i18n import M_
from polyhost.services.shell_title import _backup, _Text, _write

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VIM_SOURCE = REPO_ROOT / "vim-plugin"
EMACS_SOURCE = REPO_ROOT / "emacs-package"
GDB_SOURCE = REPO_ROOT / "gdb-plugin"
BINJA_SOURCE = REPO_ROOT / "binaryninja-plugin" / "polykybd_mode_reporter"

VIM = "vim"
NEOVIM = "neovim"
EMACS = "emacs"
GDB = "gdb"
BINARYNINJA = "binaryninja"
EDITORS = (VIM, NEOVIM, EMACS, GDB, BINARYNINJA)
# The ones loaded through a marked block in an init file, beside a copy.
INIT_EDITORS = (EMACS, GDB)

# The plugin folders a Vim package needs. README.md stays behind.
_VIM_DIRS = ("plugin", "lua", "doc")
_EMACS_FILES = ("polykybd.el",)
_GDB_FILES = ("polykybd.py",)
_BINJA_FILES = ("__init__.py", "core.py")

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

EditorStatus = namedtuple("EditorStatus", "editor state target detail")
EditorStatus.__doc__ = """One editor's state. ``target`` is the plugin folder
(Vim, Neovim) or the init file (Emacs), a Path or None. ``detail`` is the
other copy's path for STATE_MANUAL and STATE_STALE, "" otherwise."""

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


def _copy_dir(editor, home, env, system):
    """The plugin folder of a copy-only editor (Vim, Neovim, Binary Ninja)."""
    if editor == BINARYNINJA:
        return binaryninja_dir(home, env, system)
    return vim_dir(editor, home, env, system)


def _present(editor, which, system):
    which = which or shutil.which
    names = {VIM: ("vim", "gvim"), NEOVIM: ("nvim",), EMACS: ("emacs", "runemacs"),
             GDB: ("gdb", "gdb-multiarch"), BINARYNINJA: ("binaryninja",)}[editor]
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
    if editor in INIT_EDITORS:
        names = _EMACS_FILES if editor == EMACS else _GDB_FILES
        source = Path(source or (EMACS_SOURCE if editor == EMACS else GDB_SOURCE))
        if not all((source / name).is_file() for name in names):
            return None
        return {name: (source / name).read_bytes() for name in names}
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


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def read_stamp(folder):
    """The stamp's ``{relative path: sha256}``, or None when there is none."""
    try:
        data = json.loads((Path(folder) / STAMP_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    files = data.get("files") if isinstance(data, dict) else None
    return files if isinstance(files, dict) else None


def _copy_state(folder, shipped):
    """STATE_INSTALLED, STATE_OUTDATED, STATE_MODIFIED or STATE_MANUAL for a
    folder that exists, STATE_NOT_INSTALLED for one that does not."""
    folder = Path(folder)
    stamp = read_stamp(folder)
    if stamp is None:
        return STATE_MANUAL if folder.is_dir() and any(folder.iterdir()) else STATE_NOT_INSTALLED
    for rel, digest in stamp.items():
        try:
            if _sha((folder / rel).read_bytes()) != digest:
                return STATE_MODIFIED
        except FileNotFoundError:
            return STATE_OUTDATED
        except OSError:
            return STATE_MODIFIED
    want = {rel: _sha(data) for rel, data in shipped.items()}
    return STATE_INSTALLED if want == stamp else STATE_OUTDATED


def _write_copy(folder, shipped, old_stamp=None):
    """Write ``shipped`` into ``folder``, each file through a temporary file
    and a rename, and the stamp last. Files an older stamp listed and the
    new copy has not are deleted."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
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
    (folder / STAMP_NAME).write_text(json.dumps(stamp, indent=1, sort_keys=True), encoding="utf-8")


def _delete_copy(folder):
    """Delete this app's copy: the stamped files, the stamp, then every
    folder that is left empty, up to the ``pack`` folder."""
    folder = Path(folder)
    for rel in read_stamp(folder) or {}:
        try:
            (folder / rel).unlink()
        except FileNotFoundError:
            pass
    (folder / STAMP_NAME).unlink()
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


def _sources(vim_source, emacs_source, gdb_source):
    return {VIM: vim_source, NEOVIM: vim_source, EMACS: emacs_source, GDB: gdb_source,
            BINARYNINJA: None}     # BINJA_SOURCE


def status(editors=None, home=None, env=None, which=None, system=None,
           vim_source=None, emacs_source=None, gdb_source=None):
    """An EditorStatus for each editor (``editors`` filters by id)."""
    env = os.environ if env is None else env
    system = system or platform.system()
    sources = _sources(vim_source, emacs_source, gdb_source)
    out = []
    for editor in EDITORS:
        if editors is not None and editor not in editors:
            continue
        out.append(_status_one(editor, home, env, which, system, sources[editor]))
    return out


def _status_one(editor, home, env, which, system, source):
    shipped = shipped_files(editor, source)
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
    folder = _copy_dir(editor, home, env, system)
    if shipped is None:
        default = BINJA_SOURCE if editor == BINARYNINJA else VIM_SOURCE
        return EditorStatus(editor, STATE_NO_SOURCE, folder, str(source or default))
    # Binary Ninja is rarely on PATH: its user folder shows it was run here.
    present = _present(editor, which, system) or (
        editor == BINARYNINJA and binaryninja_user_dir(home, env, system).is_dir())
    if not present and not folder.exists():
        return EditorStatus(editor, STATE_NOT_PRESENT, folder, "")
    state = _copy_state(folder, shipped)
    detail = str(folder) if state == STATE_MANUAL else ""
    if state == STATE_NOT_INSTALLED and editor != BINARYNINJA:
        other = _other_vim_copies(editor, folder)
        if other is not None:
            state, detail = STATE_MANUAL, str(other)
    return EditorStatus(editor, state, folder, detail)


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
    if st.state == STATE_MODIFIED:
        return Result(st.editor, False, False, MSG_MODIFIED.format(path=folder), None)
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


def _change(st, install, sources, now=None, home=None, env=None, system=None):
    if st.state == STATE_NOT_PRESENT:
        return Result(st.editor, False, False, MSG_NOT_PRESENT.format(editor=st.editor), None)
    if st.state == STATE_NO_SOURCE:
        return Result(st.editor, False, False, MSG_NO_SOURCE.format(path=st.detail), None)
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
           gdb_source=None):
    if statuses is None:
        statuses = status(editors, home=home, env=env, which=which, system=system,
                          vim_source=vim_source, emacs_source=emacs_source, gdb_source=gdb_source)
    sources = _sources(vim_source, emacs_source, gdb_source)
    results = []
    for st in statuses:
        if editors is not None and st.editor not in editors:
            continue
        if editors is None:
            if install and not default_selection(st):
                continue
            if not install and st.state not in (STATE_INSTALLED, STATE_OUTDATED, STATE_STALE):
                continue
        results.append(_change(st, install, sources, home=home, env=env, system=system))
    return results


def install(editors=None, statuses=None, home=None, env=None, which=None,
            system=None, vim_source=None, emacs_source=None, gdb_source=None):
    """Copy the plugin for each editor (the ones default_selection() picks
    when ``editors`` is None). Returns a list of Result."""
    return _apply(True, editors, statuses, home, env, which, system, vim_source, emacs_source,
                  gdb_source)


def remove(editors=None, statuses=None, home=None, env=None, which=None,
           system=None, vim_source=None, emacs_source=None, gdb_source=None):
    """Delete this app's copy and, for Emacs and GDB, the marked block."""
    return _apply(False, editors, statuses, home, env, which, system, vim_source, emacs_source,
                  gdb_source)


def refresh_installed(home=None, env=None, which=None, system=None,
                      vim_source=None, emacs_source=None, gdb_source=None):
    """Copy the shipped files again for each editor whose copy is this app's
    and older than them. Runs at every start, so an update reaches the
    editors without a visit to the dialog. Returns the editors refreshed.
    Never raises."""
    refreshed = []
    try:
        statuses = status(None, home=home, env=env, which=which, system=system,
                          vim_source=vim_source, emacs_source=emacs_source, gdb_source=gdb_source)
    except Exception:  # noqa: BLE001 - a start must not fail for this
        log.warning("Editor plugin refresh: status failed", exc_info=True)
        return refreshed
    sources = _sources(vim_source, emacs_source, gdb_source)
    for st in statuses:
        if st.state != STATE_OUTDATED:
            continue
        try:
            r = _change(st, True, sources, home=home, env=env, system=system)
        except Exception:  # noqa: BLE001
            log.warning("Editor plugin refresh failed for %s", st.editor, exc_info=True)
            continue
        if r.changed:
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
