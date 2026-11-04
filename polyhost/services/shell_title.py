"""Shell title integration: make bash, zsh and PowerShell put the running
command line into the terminal window title.

The host sees a program that runs inside a terminal (nano, for example) only
through the terminal's window title. fish, cmd.exe, macOS Terminal.app,
iTerm2 and oh-my-zsh put the command there without setup; plain bash, zsh and
PowerShell show only the prompt's title. The scripts in ``polyhost/res/shell/``
change that, and this module adds or removes the ONE line in each shell's
startup file that sources them:

    # >>> PolyKybd title integration >>>
    if [ -r '/path/to/polyhost/res/shell/polykybd-title.bash' ]; then . '...'; fi
    # <<< PolyKybd title integration <<<

The line names the absolute path of THIS install's script. An update copies
the new files over the same install directory, so the path stays valid; a
moved checkout, a new venv or a second install changes it. The line tests the
file first, so a shell whose script has gone starts without the title and
without an error, and :func:`status` reports such a block as ``stale``.
Installing again replaces it.

The startup files are the user's own: they are read and written as bytes,
everything outside the marked block keeps its bytes, encoding and newlines,
and a timestamped copy is written next to the file before any change.

Qt-free and stdlib-only, like ``linux_udev``: ``polyctl`` imports it without
PyQt5, and the tray dialog (``gui/shell_title_dialog.py``) only shows it.
"""
import codecs
import locale
import logging
import os
import platform
import re
import shlex
import shutil
import subprocess
import time
from collections import namedtuple
from pathlib import Path, PureWindowsPath

from polyhost.i18n import M_

log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "res" / "shell"

BEGIN_MARKER = "# >>> PolyKybd title integration >>>"
END_MARKER = "# <<< PolyKybd title integration <<<"

# The shells this module can set up, in display order.
BASH = "bash"
ZSH = "zsh"
PWSH = "pwsh"               # PowerShell 7
POWERSHELL = "powershell"   # Windows PowerShell 5.1
SHELLS = (BASH, ZSH, PWSH, POWERSHELL)

# Shown for information only: they put the command in the title themselves.
FISH = "fish"
CMD = "cmd"
MACOS_TERMINAL = "macos-terminal"   # Terminal.app and iTerm2

SCRIPT_NAMES = {BASH: "polykybd-title.bash", ZSH: "polykybd-title.zsh",
                PWSH: "polykybd-title.ps1", POWERSHELL: "polykybd-title.ps1"}

# What status() reports per shell.
STATE_INSTALLED = "installed"
STATE_NOT_INSTALLED = "not-installed"
STATE_STALE = "stale"            # a block is there, but names another script path
STATE_NOT_PRESENT = "not-present"
STATE_UNKNOWN = "unknown"        # PowerShell did not tell its $PROFILE path
STATE_BLOCKED = "blocked"        # PowerShell's execution policy runs no profile
STATE_NO_SETUP = "no-setup"      # fish, cmd.exe, Terminal.app/iTerm2

ShellStatus = namedtuple("ShellStatus", "shell state rc_path detail")
ShellStatus.__doc__ = """One shell's state. ``rc_path`` is the startup file
(a Path, or None when unknown). ``detail`` is the stale block's script path,
the execution policy, or the probe's error; "" otherwise."""

Result = namedtuple("Result", "shell ok changed message backup")
Result.__doc__ = """What install()/remove() did for one shell. ``message`` is
English text from an ``M_()`` template (the tray shows translate_message() of
it), ``backup`` the copy written before the change, or None."""

# How long `pwsh -Command $PROFILE` may take. A cold PowerShell start takes
# one to three seconds; a first start after an install can take longer.
PROBE_TIMEOUT_S = 20

# Execution policies under which a profile script does not run. "Undefined"
# for every scope means Restricted on a Windows client.
_BLOCKING_POLICIES = ("restricted", "allsigned", "undefined")

# Messages; module constants on purpose, see M_().
MSG_INSTALLED = M_("Added the line to {path}.")
MSG_UPDATED = M_("Replaced the line in {path} with one for this installation.")
MSG_ALREADY = M_("Already set up in {path}.")
MSG_REMOVED = M_("Removed the line from {path}.")
MSG_NOT_INSTALLED = M_("Nothing to remove in {path}.")
MSG_NOT_PRESENT = M_("{shell} was not found on this computer.")
MSG_PROBE_FAILED = M_("{shell} did not report its profile path: {error}")
MSG_POLICY = M_("PowerShell's execution policy ({policy}) does not run profile scripts. "
                "Run 'Set-ExecutionPolicy -Scope CurrentUser RemoteSigned' in PowerShell first.")
MSG_NO_END_MARKER = M_("{path} has a start marker without an end marker. Remove the block by hand.")
MSG_WRITE_FAILED = M_("Could not change {path}: {error}")
MSG_ENCODING = M_("The script path cannot be written in the encoding of {path} ({encoding}).")
MSG_SCRIPT_MISSING = M_("The script {path} that the line would load is missing.")

_BLOCK_RE = re.compile(
    r"(?m)^" + re.escape(BEGIN_MARKER) + r"[ \t]*\r?\n(.*?)^"
    + re.escape(END_MARKER) + r"[ \t]*(?:\r?\n|\Z)", re.S)
_PS_PATH_RE = re.compile(r"-LiteralPath\s+'((?:[^']|'')*)'")

# The probe answers are cached per executable for the life of the process:
# the profile path does not change while the app runs, and asking costs a
# PowerShell start every time the dialog opens. A blocking execution policy
# is not cached (see probe_powershell).
_probe_cache = {}


def clear_probe_cache():
    _probe_cache.clear()


def script_path(shell, system=None):
    """The shipped script for ``shell``, as the startup file must name it. On
    Windows a bash (Git Bash, MSYS2) reads ``C:/...`` but not ``C:\\...``."""
    path = SCRIPT_DIR / SCRIPT_NAMES[shell]
    if shell in (BASH, ZSH) and (system or platform.system()) == "Windows":
        return PureWindowsPath(path).as_posix()
    return str(path)


def source_line(shell, path):
    """The one line that loads ``path``, quoted for the shell."""
    if shell in (BASH, ZSH):
        q = shlex.quote(path)
        return f"if [ -r {q} ]; then . {q}; fi"
    q = "'" + path.replace("'", "''") + "'"
    return f"if (Test-Path -LiteralPath {q}) {{ . {q} }}"


def _path_in_line(shell, line):
    """The script path a block's line names, or "" if it cannot be read."""
    if shell in (BASH, ZSH):
        try:
            words = shlex.split(line)
        except ValueError:
            return ""
        return words[3] if len(words) > 3 and words[:3] == ["if", "[", "-r"] else ""
    m = _PS_PATH_RE.search(line)
    return m.group(1).replace("''", "'") if m else ""


# --- locating the shells and their startup files ---------------------------

def _home(home):
    return Path(home) if home is not None else Path.home()


def _is_wsl_launcher(path):
    """C:\\Windows\\System32\\bash.exe starts WSL, whose ~/.bashrc is inside
    the Linux file system, not the Windows home."""
    return "system32" in str(path).lower().replace("/", "\\").split("\\")


def _bash_present(which, system):
    exe = which("bash")
    if exe and system == "Windows" and _is_wsl_launcher(exe):
        return False
    return bool(exe)


def rc_file(shell, home=None, env=None):
    """The startup file for bash or zsh (``$ZDOTDIR`` for zsh)."""
    env = os.environ if env is None else env
    if shell == BASH:
        return _home(home) / ".bashrc"
    zdotdir = env.get("ZDOTDIR")
    return (Path(zdotdir) if zdotdir else _home(home)) / ".zshrc"


# How long `zsh -c` may take to report its startup directory.
ZSH_PROBE_TIMEOUT_S = 10


def probe_zsh_dir(exe, run=subprocess.run, env=None, home=None, timeout=ZSH_PROBE_TIMEOUT_S):
    """The directory zsh reads ``.zshrc`` from, asked from zsh itself: a
    ``ZDOTDIR`` set in ``~/.zshenv`` (and not exported to the desktop session
    this app runs in) is seen only this way, because ``zsh -c`` reads
    ``.zshenv``. Returns a Path, or None when zsh did not answer. Never raises."""
    env = dict(os.environ if env is None else env)
    if home is not None:
        env["HOME"] = str(home)
    kwargs = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        # Audit (Sourcery dangerous-subprocess-use): argv is a fixed list; exe
        # is what shutil.which found for "zsh", and the script is a constant.
        # No shell parses it before zsh.
        # nosemgrep
        proc = run([exe, "-c", "print -r -- ${ZDOTDIR:-$HOME}"], capture_output=True,
                   timeout=timeout, env=env, **kwargs)
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.info("zsh did not report its startup directory: %s", exc)
        return None
    out = proc.stdout.decode("utf-8", "replace") if isinstance(proc.stdout, bytes) else (proc.stdout or "")
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if proc.returncode != 0 or not lines or not os.path.isabs(lines[-1]):
        return None
    return Path(lines[-1])


def probe_powershell(exe, run=subprocess.run, timeout=PROBE_TIMEOUT_S, use_cache=True):
    """Ask a PowerShell for its ``$PROFILE`` path and effective execution
    policy. Returns ``(path, policy, error)``: a Path and a str, or None and
    None with the error text. Never raises."""
    if use_cache and exe in _probe_cache:
        return _probe_cache[exe]
    # Print UTF-8, so a profile path with a non-ASCII user name survives.
    script = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
              "$PROFILE; (Get-ExecutionPolicy).ToString()")
    argv = [exe, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script]
    kwargs = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        # Audit (Sourcery dangerous-subprocess-use): argv is a fixed list; exe
        # is what shutil.which found for "pwsh" or "powershell", and the script
        # is a module constant. No shell is involved.
        # nosemgrep
        proc = run(argv, capture_output=True, timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired:
        answer = (None, None, f"no answer within {timeout} s")
    except OSError as exc:
        answer = (None, None, str(exc))
    else:
        out = proc.stdout.decode("utf-8", "replace") if isinstance(proc.stdout, bytes) else (proc.stdout or "")
        lines = [ln.strip().lstrip("\ufeff") for ln in out.splitlines() if ln.strip()]
        if proc.returncode != 0 or len(lines) < 2 or not os.path.isabs(lines[0]):
            err = proc.stderr.decode("utf-8", "replace") if isinstance(proc.stderr, bytes) else (proc.stderr or "")
            answer = (None, None, (err.strip() or out.strip() or f"exit code {proc.returncode}")[:300])
        else:
            answer = (Path(lines[0]), lines[1], "")
    # Cache only an answer that allows an install. A refused one is asked
    # again on the next status, so the dialog's next refresh sees a
    # Set-ExecutionPolicy the user ran in the meantime.
    if answer[0] is not None and answer[1].lower() not in _BLOCKING_POLICIES:
        _probe_cache[exe] = answer
    return answer


# --- reading and changing a startup file ----------------------------------

_BOMS = ((codecs.BOM_UTF8, "utf-8"), (codecs.BOM_UTF16_LE, "utf-16-le"),
         (codecs.BOM_UTF16_BE, "utf-16-be"))


class _Text:
    """A startup file as text that writes back to the same bytes.

    A file with a UTF-16 byte order mark is decoded as UTF-16. Every other file
    is decoded as Latin-1, which maps each byte to one character, so any
    content round-trips byte for byte; the markers are ASCII, and the inserted
    line is encoded in ``encoding`` first and then mapped the same way."""

    def __init__(self, raw, encoding):
        self.bom = b""
        self.codec = "latin-1"
        self.encoding = encoding
        for bom, name in _BOMS:
            if raw.startswith(bom):
                self.bom = bom
                self.encoding = name
                if name.startswith("utf-16"):
                    self.codec = name
                break
        self.text = raw[len(self.bom):].decode(self.codec)

    def piece(self, s):
        """``s`` in the file's encoding, as a piece of ``self.text``."""
        if self.codec != "latin-1":
            return s
        return s.encode(self.encoding).decode("latin-1")

    def unpiece(self, s):
        """A piece of ``self.text`` back as text: the inverse of piece(). A
        byte the encoding cannot decode becomes U+FFFD."""
        if self.codec != "latin-1":
            return s
        return s.encode("latin-1").decode(self.encoding, "replace")

    def to_bytes(self, text):
        return self.bom + text.encode(self.codec)


def _default_encoding(shell, exists):
    """The encoding a line goes into a file WITHOUT a byte order mark in.

    bash and zsh read bytes, and a path is in the platform encoding. PowerShell
    7 reads a BOM-less script as UTF-8; Windows PowerShell 5.1 reads it in
    the ANSI code page, which is the platform default. A NEW 5.1 profile is
    written as UTF-8 with a BOM, which both read."""
    if shell == PWSH or (shell == POWERSHELL and not exists):
        return "utf-8"
    return locale.getpreferredencoding(False)


def _newline(text, shell, system):
    if "\r\n" in text:
        return "\r\n"
    if "\n" in text:
        return "\n"
    # A new or one-line file. A bash on Windows (Git Bash) does not accept
    # CRLF, so only PowerShell gets the Windows line end there.
    return "\r\n" if shell in (PWSH, POWERSHELL) and system == "Windows" else "\n"


def _blocks(text):
    """``[(start, end, inner)]`` for each complete marked block, and whether a
    start marker is left without its end marker."""
    found = [(m.start(), m.end(), m.group(1)) for m in _BLOCK_RE.finditer(text)]
    rest = _BLOCK_RE.sub("", text)
    orphan = re.search(r"(?m)^" + re.escape(BEGIN_MARKER), rest) is not None
    return found, orphan


def _block_line(inner):
    for line in inner.splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            return line.strip()
    return ""


def _backup(path, now=None):
    """Copy ``path`` to ``<name>.polykybd-<YYYYmmdd-HHMMSS>.bak`` beside it."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    dest = path.with_name(f"{path.name}.polykybd-{stamp}.bak")
    n = 1
    while dest.exists():
        dest = path.with_name(f"{path.name}.polykybd-{stamp}-{n}.bak")
        n += 1
    shutil.copy2(path, dest)
    return dest


def _write(path, data):
    """Write in place, through a symlink (dotfile managers link these files),
    so the file keeps its inode, owner and mode."""
    real = Path(os.path.realpath(path))
    real.parent.mkdir(parents=True, exist_ok=True)
    with open(real, "wb") as fh:
        fh.write(data)


def file_state(shell, rc_path, system=None):
    """``(state, detail)`` of the marked block in one startup file."""
    system = system or platform.system()
    try:
        raw = Path(rc_path).read_bytes()
    except FileNotFoundError:
        return STATE_NOT_INSTALLED, ""
    except OSError as exc:
        return STATE_UNKNOWN, str(exc)
    try:
        doc = _Text(raw, _default_encoding(shell, True))
    except UnicodeDecodeError as exc:
        return STATE_UNKNOWN, str(exc)
    found, _orphan = _blocks(doc.text)
    if not found:
        return STATE_NOT_INSTALLED, ""
    want = script_path(shell, system)
    for _s, _e, inner in found:
        line = doc.unpiece(_block_line(inner))
        named = _path_in_line(shell, line)
        if line == source_line(shell, want) and Path(named).is_file():
            return STATE_INSTALLED, ""
    return STATE_STALE, _path_in_line(shell, doc.unpiece(_block_line(found[0][2])))


# --- the public calls -------------------------------------------------------

def status(shells=None, home=None, env=None, which=shutil.which, run=subprocess.run,
           system=None, use_cache=True):
    """A ShellStatus for each shell (``shells`` filters by id), followed by
    the ones that need no setup on this platform."""
    system = system or platform.system()
    env = os.environ if env is None else env
    out = []
    for shell in SHELLS:
        if shells is not None and shell not in shells:
            continue
        out.append(_status_one(shell, home, env, which, run, system, use_cache))
    if shells is None:
        if which("fish"):
            out.append(ShellStatus(FISH, STATE_NO_SETUP, None, ""))
        if system == "Windows":
            out.append(ShellStatus(CMD, STATE_NO_SETUP, None, ""))
        if system == "Darwin":
            out.append(ShellStatus(MACOS_TERMINAL, STATE_NO_SETUP, None, ""))
    return out


def _status_one(shell, home, env, which, run, system, use_cache):
    if shell in (BASH, ZSH):
        rc = rc_file(shell, home, env)
        if shell == BASH:
            present = _bash_present(which, system)
        else:
            exe = which("zsh")
            present = bool(exe)
            zdot = probe_zsh_dir(exe, run=run, env=env, home=home) if exe else None
            if zdot is not None:
                rc = zdot / ".zshrc"
        if not present and not rc.exists():
            return ShellStatus(shell, STATE_NOT_PRESENT, rc, "")
        state, detail = file_state(shell, rc, system)
        return ShellStatus(shell, state, rc, detail)
    exe = which(shell)
    if not exe:
        return ShellStatus(shell, STATE_NOT_PRESENT, None, "")
    profile, policy, error = probe_powershell(exe, run=run, use_cache=use_cache)
    if profile is None:
        return ShellStatus(shell, STATE_UNKNOWN, None, error)
    state, detail = file_state(shell, profile, system)
    if state == STATE_NOT_INSTALLED and policy.lower() in _BLOCKING_POLICIES and system == "Windows":
        return ShellStatus(shell, STATE_BLOCKED, profile, policy)
    return ShellStatus(shell, state, profile, detail)


def _change(st, install, system, now=None):
    """Install or remove the block for one ShellStatus; returns a Result."""
    shell, rc = st.shell, st.rc_path
    if st.state == STATE_NOT_PRESENT:
        return Result(shell, False, False, MSG_NOT_PRESENT.format(shell=shell), None)
    if st.state == STATE_UNKNOWN and rc is None:
        return Result(shell, False, False,
                      MSG_PROBE_FAILED.format(shell=shell, error=st.detail), None)
    if install and st.state == STATE_BLOCKED:
        return Result(shell, False, False, MSG_POLICY.format(policy=st.detail), None)
    rc = Path(rc)
    want_path = script_path(shell, system)
    if install and not (SCRIPT_DIR / SCRIPT_NAMES[shell]).is_file():
        return Result(shell, False, False, MSG_SCRIPT_MISSING.format(path=want_path), None)
    try:
        raw = rc.read_bytes()
        exists = True
    except FileNotFoundError:
        raw, exists = b"", False
    except OSError as exc:
        return Result(shell, False, False, MSG_WRITE_FAILED.format(path=rc, error=exc), None)
    try:
        doc = _Text(raw, _default_encoding(shell, exists))
    except UnicodeDecodeError as exc:
        return Result(shell, False, False, MSG_WRITE_FAILED.format(path=rc, error=exc), None)
    if not exists and shell == POWERSHELL:
        doc.bom = codecs.BOM_UTF8
    text = doc.text
    found, orphan = _blocks(text)
    if orphan:
        return Result(shell, False, False, MSG_NO_END_MARKER.format(path=rc), None)
    nl = _newline(text, shell, system)

    if install:
        try:
            block = doc.piece(BEGIN_MARKER + nl + source_line(shell, want_path) + nl
                              + END_MARKER + nl)
        except UnicodeEncodeError:
            return Result(shell, False, False,
                          MSG_ENCODING.format(path=rc, encoding=doc.encoding), None)
        if found:
            # Replace the first block, drop any others (a hand-made copy).
            s0, e0, _inner = found[0]
            new = text[:s0] + block
            prev = e0
            for s, e, _inner in found[1:]:
                new += text[prev:s]
                prev = e
            new += text[prev:]
            done = MSG_UPDATED
        else:
            sep = nl if text and not text.endswith("\n") else ""
            new = text + doc.piece(sep) + block
            done = MSG_INSTALLED
        if new == text:
            return Result(shell, True, False, MSG_ALREADY.format(path=rc), None)
    else:
        if not found:
            return Result(shell, True, False, MSG_NOT_INSTALLED.format(path=rc), None)
        new, prev = "", 0
        for s, e, _inner in found:
            new += text[prev:s]
            prev = e
        new += text[prev:]
        done = MSG_REMOVED

    data = doc.to_bytes(new)
    backup = None
    try:
        if exists:
            backup = _backup(rc, now)
        _write(rc, data)
    except OSError as exc:
        return Result(shell, False, False, MSG_WRITE_FAILED.format(path=rc, error=exc), backup)
    log.info("Shell title integration: %s %s (backup %s)",
             "installed in" if install else "removed from", rc, backup)
    return Result(shell, True, True, done.format(path=rc), backup)


def default_selection(st, env=None):
    """Whether "all shells" includes ``st``: a shell found on this computer
    that has its startup file already, or is the login shell (``$SHELL``).
    A zsh that is installed but never used gets no new ~/.zshrc, which would
    also skip zsh's first-start setup wizard."""
    env = os.environ if env is None else env
    if st.shell not in SHELLS or st.state in (STATE_NOT_PRESENT, STATE_NO_SETUP):
        return False
    if st.shell in (BASH, ZSH) and st.state == STATE_NOT_INSTALLED:
        login = os.path.basename(env.get("SHELL", ""))
        return st.rc_path is not None and (Path(st.rc_path).exists() or login == st.shell)
    return True


def _apply(install, shells, statuses, home, env, which, run, system):
    system = system or platform.system()
    if statuses is None:
        statuses = status(shells, home=home, env=env, which=which, run=run, system=system)
    results = []
    for st in statuses:
        if st.shell not in SHELLS or (shells is not None and st.shell not in shells):
            continue
        if shells is None:
            # "All shells": install where default_selection() says so, remove
            # wherever a block is.
            if install and not default_selection(st, env):
                continue
            if not install and st.state not in (STATE_INSTALLED, STATE_STALE):
                continue
        results.append(_change(st, install, system))
    return results


def install(shells=None, statuses=None, home=None, env=None, which=shutil.which,
            run=subprocess.run, system=None):
    """Add the block to each shell's startup file (the shells
    default_selection() picks when ``shells`` is None). Pass the ``statuses`` a dialog already
    shows to skip a second PowerShell probe. Returns a list of Result."""
    return _apply(True, shells, statuses, home, env, which, run, system)


def remove(shells=None, statuses=None, home=None, env=None, which=shutil.which,
           run=subprocess.run, system=None):
    """Delete exactly the marked block(s) from each shell's startup file."""
    return _apply(False, shells, statuses, home, env, which, run, system)
