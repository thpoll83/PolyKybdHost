"""Collect PolyHost's log files into something a user can actually hand over.

The logs are useful but awkward to gather by hand: they are **six** files
(``host_log.txt``, ``daemon_log.txt``, ``polykybd_console.txt``,
``startup_log.txt``, ``forwarder_log.txt`` and ``crash_log.txt``) written to
the app's working directory, the rotating ones with up to three
``.1``/``.2``/``.3`` backups — so the lines that matter are routinely split
across a rotation boundary, and under daemon-by-default the interesting half
lives in ``daemon_log.txt`` while the GUI writes ``host_log.txt``. "Send me
your log" is therefore a request nobody can reliably satisfy.

This module is the one place that knows how to do it, and is **Qt-free** so the
tray GUI, ``polyctl`` and the headless daemon all share it:

- :func:`build_bundle` writes a ``.zip`` (logs + diagnostics + redacted
  settings) sliced to a timeframe,
- :func:`collect_text` / :func:`recent_text` return the same content as text,
  for the log viewer's clipboard button,
- :func:`redact_text` strips window titles, which are the one genuinely
  sensitive thing in a host log.
"""

from __future__ import annotations

import platform
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from polyhost.util import crash_log


class LogSource(NamedTuple):
    """One collectable log file.

    The label names the file inside the bundle and the section in the clipboard
    text; the filename is what the logging handlers in host.py / headless.py /
    main_app.py / forwarder.py actually open.

    ``sliced`` lives on the entry rather than in a lookup table beside it, so
    adding a source has to answer the question at the point of declaration — a
    parallel list of exceptions is exactly the kind of guard that goes stale.
    """

    label: str
    filename: str
    sliced: bool = True
    title: str = ""      # tab name in the GUI log viewers; see viewer_files()


LOG_SOURCES: tuple[LogSource, ...] = (
    LogSource("host", "host_log.txt", title="PolyHost Log"),
    LogSource("daemon", "daemon_log.txt", title="Daemon Log"),
    LogSource("keyboard-console", "polykybd_console.txt", title="PolyKybd Console Log"),
    LogSource("startup", "startup_log.txt", title="Startup Log"),
    LogSource("forwarder", "forwarder_log.txt", title="Forwarder Log"),
    # ⚠️ NEVER time-sliced, and that is not a convenience. `faulthandler` writes
    # its native dump directly on the fault, with no marker line of its own, so
    # under slice_lines it inherits the keep/drop decision of the `session
    # start` above it — which may be hours older than the window and would drop
    # precisely the crash being reported. The file is small and unrotated, so
    # carrying it whole costs nothing. The filename comes from crash_log so the
    # writer and the collector cannot disagree about it.
    LogSource("crash", crash_log.CRASH_LOG, sliced=False, title="Crash Log"),
)

# Derived from the declaration above — never hand-maintained.
_SLICED: dict[str, bool] = {s.label: s.sliced for s in LOG_SOURCES}

# RotatingFileHandler(backupCount=3) — the highest suffix is the OLDEST.
MAX_BACKUPS = 9

DEFAULT_SINCE = "24h"

# Settings values that are secrets or identifiers rather than configuration.
# These are masked ALWAYS, independent of the window-title redaction flag: a
# shared token stays a secret whether or not the user ticked "redact".
_ALWAYS_MASKED_SETTINGS = ("browser_report_token", "telemetry_install_id")

# "[2026-08-17 12:34:56,789] INFO ..." — every handler formats with the default
# asctime, including MultiLineFormatter's continuation-line prefix.
_TIMESTAMP_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})\]")


class LogBundleError(Exception):
    """Raised when a bundle cannot be produced at all (e.g. no logs found)."""


@dataclass
class SourceResult:
    """One log source after slicing: what went in, and what it cost."""
    label: str
    files: list[Path] = field(default_factory=list)
    lines: int = 0
    bytes: int = 0


@dataclass
class BundleResult:
    path: Path
    sources: list[SourceResult] = field(default_factory=list)
    redacted: bool = False
    since: datetime | None = None

    @property
    def total_lines(self) -> int:
        return sum(s.lines for s in self.sources)

    def summary(self) -> str:
        size_kb = max(1, self.path.stat().st_size // 1024) if self.path.exists() else 0
        parts = [f"{s.label} ({s.lines} line{'' if s.lines == 1 else 's'})"
                 for s in self.sources if s.lines]
        body = ", ".join(parts) if parts else "no log lines in range"
        return f"{self.path.name} — {size_kb} KB: {body}"


# --------------------------------------------------------------------------
# Locating the logs
# --------------------------------------------------------------------------

def default_log_dir() -> Path:
    """Best guess at where the logs are.

    The handlers open **relative** filenames, so the real answer is "the cwd of
    the process that wrote them". For the GUI and the daemon it spawns that is
    the repo root (the generated launchers ``cd`` there, and the daemon inherits
    the GUI's cwd). But ``polyctl`` is typically run from somewhere else
    entirely, so prefer whichever candidate actually has logs in it, and only
    fall back to the cwd when neither does.
    """
    candidates = [Path.cwd(), Path(__file__).resolve().parent.parent.parent]
    for cand in candidates:
        try:
            if any((cand / s.filename).exists() for s in LOG_SOURCES):
                return cand
        except OSError:
            continue
    return candidates[0]


def _rotation_chain(log_dir: Path, name: str) -> list[Path]:
    """Every existing file for one source, OLDEST first.

    ``RotatingFileHandler`` moves the live file to ``.1`` and shifts the rest
    up, so ``.3`` is older than ``.1`` and the base name is newest. Reading them
    in that order makes the concatenation chronological, which is what both the
    time slice and a human reading it expect.
    """
    chain: list[Path] = []
    for i in range(MAX_BACKUPS, 0, -1):
        p = log_dir / f"{name}.{i}"
        if p.exists():
            chain.append(p)
    base = log_dir / name
    if base.exists():
        chain.append(base)
    return chain


def viewer_files(always: tuple[str, ...] = (),
                 log_dir: Path | str | None = None) -> dict[str, str]:
    """``{tab title: absolute path}`` for a GUI log viewer, from LOG_SOURCES.

    Values are ABSOLUTE paths, because the viewer opens them as given.
    ``always`` names the sources this app writes itself, which get a tab whether
    or not the file is there yet; every other source appears only once it
    exists. Both tray apps call this instead of hand-building the dict, because
    they had two hand-built dicts and they drifted — the forwarder's was missing
    the crash log, which is the whole reason this change exists. One
    declaration now feeds the bundle, the clipboard text and both viewers.
    """
    d = Path(log_dir) if log_dir else default_log_dir()
    out: dict[str, str] = {}
    for source in LOG_SOURCES:
        if not source.title:
            continue
        path = d / source.filename
        if source.label in always or path.exists():
            # ⚠️ ABSOLUTE, not the bare name. LogViewerDialog opens this value
            # directly, so a bare name resolves against the process cwd while
            # the existence test above resolved against default_log_dir() —
            # different directories mean the viewer shows the wrong file or
            # fails to load it. (It also makes the dialog's "open containing
            # folder" work, which os.path.dirname of a bare name never could.)
            out[source.title] = str(path)
    return out


def discover(log_dir: Path | str | None = None) -> dict[str, list[Path]]:
    """Map each source label to its rotation chain (only sources that exist)."""
    d = Path(log_dir) if log_dir else default_log_dir()
    found = {}
    for source in LOG_SOURCES:
        chain = _rotation_chain(d, source.filename)
        if chain:
            found[source.label] = chain
    return found


# --------------------------------------------------------------------------
# Time slicing
# --------------------------------------------------------------------------

def parse_timestamp(line: str) -> datetime | None:
    """The datetime a log line starts with, or None for a continuation line."""
    m = _TIMESTAMP_RE.match(line)
    if not m:
        return None
    try:
        stamp = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return stamp.replace(microsecond=int(m.group(2)) * 1000)


def crash_summary(log_dir: Path | str | None = None) -> str | None:
    """A factual one-liner about ``crash_log.txt``, or None when there is none.

    Deliberately **not** a verdict. A ``session start`` with no matching
    ``clean exit`` is the crash log's headline signal, but the process writing
    a bug report is itself exactly such a session — and so is a live daemon —
    so any "it crashed" claim derived here would fire on every healthy report
    and be learned to ignore. These counts are unambiguous; the attached file
    carries the pairing, which a reader can interpret with the pids in hand.
    """
    chain = _rotation_chain(Path(log_dir) if log_dir else default_log_dir(),
                            crash_log.CRASH_LOG)
    if not chain:
        return None
    counts = {"session start": 0, "clean exit": 0, "exception": 0}
    faults = 0
    newest = None
    # A native dump has no marker of its own, and spans several lines: a fatal
    # signal prints "Fatal Python error: …" AND then "Current thread 0x…", while
    # a bare dump prints only the latter. Counting both lines reports one crash
    # as two, so a dump runs from its first such line until the next marker.
    in_dump = False
    for line in _read_chain(chain):
        if line.startswith("Fatal Python error") or line.startswith("Current thread 0x"):
            if not in_dump:
                faults += 1
                in_dump = True
            continue
        marker = crash_log.parse_marker(line)
        if marker is None:
            continue
        in_dump = False
        what, _pid, newest = marker
        if what.startswith("session start"):
            counts["session start"] += 1
        elif what.startswith("clean exit"):
            counts["clean exit"] += 1
        elif "exception" in what:
            counts["exception"] += 1
    parts = [f"{counts['session start']} session(s)",
             f"{counts['clean exit']} clean exit(s)"]
    if counts["exception"]:
        parts.append(f"{counts['exception']} unhandled exception(s)")
    if faults:
        parts.append(f"{faults} native fault dump(s)")
    if newest:
        parts.append(f"newest marker {newest}")
    return ", ".join(parts)


def parse_since(spec: str | None, now: datetime | None = None) -> datetime | None:
    """Turn ``30m`` / ``2h`` / ``7d`` / ``all`` into a cutoff datetime.

    ``all`` (or None/empty) means no filtering. A bare number is read as hours,
    since that is the unit people reach for when they omit one.
    """
    if spec is None:
        return None
    spec = str(spec).strip().lower()
    if not spec or spec in ("all", "everything", "0"):
        return None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smhdw]?)", spec)
    if not m:
        raise ValueError(
            f"Unrecognised timeframe {spec!r} — use e.g. 30m, 2h, 7d, or 'all'")
    value = float(m.group(1))
    unit = m.group(2) or "h"
    seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[unit] * value
    try:
        return (now or datetime.now()) - timedelta(seconds=seconds)
    except (OverflowError, OSError) as exc:
        # The regex accepts any number of digits, so both timedelta() and the
        # subtraction can overflow. Callers handle bad input as ValueError.
        raise ValueError(f"Timeframe {spec!r} is out of range") from exc


def slice_lines(lines, since: datetime | None) -> list[str]:
    """Keep lines at/after ``since``.

    Continuation lines (tracebacks, and any line the formatter did not stamp)
    carry no timestamp of their own, so they **inherit the decision made for the
    record they belong to** — otherwise a kept exception line loses its
    traceback, which is the half that says what actually failed. Lines before
    the first timestamp are dropped: they continue a record older than anything
    we are keeping.
    """
    if since is None:
        return list(lines)
    out: list[str] = []
    keep = False
    for line in lines:
        stamp = parse_timestamp(line)
        if stamp is not None:
            keep = stamp >= since
        if keep:
            out.append(line)
    return out


def _read_chain(chain: list[Path]) -> list[str]:
    lines: list[str] = []
    for path in chain:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines.extend(f.read().splitlines())
        except OSError as e:  # a locked/removed rotation file must not abort
            lines.append(f"<could not read {path.name}: {e}>")
    return lines


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------

def _mask(text: str) -> str:
    """Replace a value with a length hint.

    The length is kept deliberately: a lot of title-matching bugs are visible
    from "the title changed / did not change" alone, and a bare ``<redacted>``
    throws that away too.
    """
    return f"<redacted:{len(text)} chars>"


# Each pattern's group 1 is the window title to mask. They are anchored on the
# log message's own wording rather than on "anything in quotes", so an ordinary
# quoted value (a file path, an app name) is left readable.
_TITLE_PATTERNS = (
    # active_window.py / remote_window.py: '... Changed: "app", Title: "the title"'
    re.compile(r'(?<=Title: ")((?:[^"\\]|\\.)*)(?=")'),
    # active_window.py: "in mapping but title did not match (title='...')"
    re.compile(r"(?<=\(title=')((?:[^'\\]|\\.)*)(?=')"),
    # remote_window.py report_window: "... title=<title> os=..."
    re.compile(r"(?<= title=)(.*?)(?= os=)"),
    # remote_window.py remote_changed: "... stored_title=<a>-><b> os=..."
    re.compile(r"(?<=stored_title=)(.*?)(?= os=)"),
)


def redact_text(text: str) -> str:
    """Mask window titles in log text.

    Window titles are the one thing in a host log that routinely names a
    document ("Q3 layoffs.xlsx — Excel"); the host reads them constantly because
    that is how overlay matching works. Application/executable names are kept —
    they are what a support round actually needs, and are far less revealing.
    """
    for pattern in _TITLE_PATTERNS:
        text = pattern.sub(lambda m: _mask(m.group(1)), text)
    return text


def redact_settings(raw: str) -> str:
    """Mask secret-ish settings values in a settings.yaml dump."""
    for key in _ALWAYS_MASKED_SETTINGS:
        raw = re.sub(
            rf"^(\s*{re.escape(key)}\s*:\s*)(\S.*)$",
            lambda m: m.group(1) + ("<redacted>" if m.group(2).strip() not in ("''", '""') else m.group(2)),
            raw, flags=re.MULTILINE)
    return raw


# --------------------------------------------------------------------------
# Collecting
# --------------------------------------------------------------------------

def _collect_source(label: str, chain: list[Path], since: datetime | None,
                    redact: bool) -> tuple[list[str], str]:
    """Read one source's chain, honouring ITS slicing policy, and redact.

    Shared by :func:`collect_text` and :func:`build_bundle` rather than written
    out in each: they had two copies of this loop, so a per-source rule added to
    one would silently not apply to the other — and the bundle is the copy that
    reaches a maintainer.
    """
    lines = _read_chain(chain)
    if _SLICED.get(label, True):
        lines = slice_lines(lines, since)
    text = "\n".join(lines)
    return lines, redact_text(text) if redact else text


def collect_text(log_dir: Path | str | None = None, since: datetime | None = None,
                 redact: bool = False) -> dict[str, str]:
    """Return ``{label: sliced log text}`` for every source that has content."""
    out: dict[str, str] = {}
    for label, chain in discover(log_dir).items():
        lines, text = _collect_source(label, chain, since, redact)
        if lines:
            out[label] = text
    return out


def recent_text(log_dir: Path | str | None = None, since: datetime | None = None,
                max_lines: int = 500, redact: bool = False) -> str:
    """One pasteable blob: the tail of every log, newest source content last.

    Built for the clipboard, so it is capped per source — a chat message with
    20k lines in it helps nobody, and the bundle exists for the full picture.
    """
    chunks = []
    for label, text in collect_text(log_dir, since, redact).items():
        lines = text.splitlines()
        clipped = len(lines) > max_lines
        if clipped:
            lines = lines[-max_lines:]
        head = f"===== {label} " + (f"(last {max_lines} lines of {len(text.splitlines())}) " if clipped else "")
        chunks.append(head + "=" * max(0, 78 - len(head)) + "\n" + "\n".join(lines))
    if not chunks:
        return "(no log content in the selected timeframe)"
    return "\n\n".join(chunks)


def os_detail() -> str:
    """A version string that actually identifies the OS.

    ``platform.release()`` alone is not diagnostic on two of the three
    platforms: it returns **"10" on Windows 11** (only the build in
    ``platform.version()`` — >= 22000 — tells them apart), and on Linux it
    returns the *kernel* version rather than the distribution.
    """
    system = platform.system()
    try:
        if system == "Windows":
            version = platform.version()               # e.g. "10.0.22631"
            build = int(version.split(".")[2]) if version.count(".") >= 2 else 0
            name = "Windows 11" if build >= 22000 else f"Windows {platform.release()}"
            return f"{name} (build {version})"
        if system == "Darwin":
            mac = platform.mac_ver()[0]
            return f"macOS {mac}" if mac else f"macOS (Darwin {platform.release()})"
        if system == "Linux":
            pretty = ""
            try:
                for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
                    if line.startswith("PRETTY_NAME="):
                        pretty = line.split("=", 1)[1].strip().strip('"')
                        break
            except OSError:
                pass
            return (f"{pretty} (kernel {platform.release()})" if pretty
                    else f"Linux {platform.release()}")
    except Exception:  # noqa: BLE001 — never let a version string break the bundle
        pass
    return f"{system} {platform.release()}".strip()


def session_detail() -> str | None:
    """Linux desktop + session type, and the window backend they select.

    This is the single most load-bearing environment fact for a Linux report:
    ``XDG_CURRENT_DESKTOP``/``XDG_SESSION_TYPE`` choose between the KDE D-Bus
    reporter, the GNOME-Wayland extension path and plain pywinctl — so "overlays
    do not follow my windows" cannot be diagnosed without them.
    """
    import os
    if platform.system() != "Linux":
        return None
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "(unset)")
    session = os.environ.get("XDG_SESSION_TYPE", "(unset)")
    if desktop == "KDE":
        backend = "kde_win_reporter (KWin script)"
    elif session == "wayland":
        backend = "gnome_wayland_reporter (needs the Window Reporter extension)"
    else:
        backend = "pywinctl (X11)"
    return f"{desktop} / {session} -> {backend}"


def autostart_detail() -> str | None:
    """Which autostart mechanism is registered, if any.

    ⚠️ On Windows this shells out to the task scheduler, so it is only gathered
    where blocking is safe — inside :func:`build_bundle`, which the GUI runs on a
    worker thread. "It stopped starting at login" is a whole family of reports
    that this one line answers.
    """
    try:
        from polyhost.services.add_to_startup import get_autostart_status
        return get_autostart_status()
    except Exception:  # noqa: BLE001 — a probe failure is not a bundle failure
        return None


def environment_text(include_slow: bool = False,
                     log_dir: Path | str | None = None) -> str:
    """Environment block, available without Qt or a running daemon.

    ``include_slow`` adds probes that may shell out (autostart). Callers on the
    GUI thread leave it off; :func:`build_bundle` turns it on because it runs on
    a worker.
    """
    from polyhost._version import __protocol__, __version__
    lines = [
        f"PolyHost version : {__version__}",
        f"Host protocol    : {__protocol__}",
        f"Python           : {platform.python_version()} ({sys.executable})",
        f"OS               : {os_detail()} ({platform.machine()})",
    ]
    session = session_detail()
    if session:
        lines.append(f"Desktop session  : {session}")
    if include_slow:
        autostart = autostart_detail()
        if autostart:
            lines.append(f"Autostart        : {autostart}")
    # The crash markers are the first thing worth knowing on a "the app
    # vanished" report, and the body is read long before the attachment is
    # opened. Never fatal: diagnostics must not be able to break a bug report.
    try:
        crashes = crash_summary(log_dir)
        if crashes:
            lines.append(f"Crash log        : {crashes}")
    except Exception:  # noqa: BLE001 — diagnostics must never break the bundle
        pass
    lines.append(f"Collected        : {datetime.now().isoformat(timespec='seconds')}")
    try:
        import platformdirs
        lines.append(f"Config dir       : {platformdirs.user_config_dir('PolyHost')}")
    except Exception:  # noqa: BLE001 — diagnostics must never break the bundle
        pass
    return "\n".join(lines)


def _settings_text() -> str | None:
    try:
        import platformdirs
        path = Path(platformdirs.user_config_dir("PolyHost")) / "settings.yaml"
        return redact_settings(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a missing/unreadable config is not fatal
        return None


def default_bundle_name(now: datetime | None = None) -> str:
    return f"polyhost-logs-{(now or datetime.now()).strftime('%Y%m%d-%H%M%S')}.zip"


def _readme(since: datetime | None, redact: bool, sources: list[SourceResult]) -> str:
    span = (f"since {since.isoformat(sep=' ', timespec='seconds')}"
            if since else "everything on disk (no time filter)")
    body = [
        "PolyHost log bundle",
        "===================",
        "",
        f"Timeframe : {span}",
        f"Redaction : {'window titles masked' if redact else 'NONE — window titles are included'}",
        "",
        "Contents",
        "--------",
        "diagnostics.txt  versions, OS and keyboard/connection state",
        "settings.yaml    host configuration (tokens and the install id masked)",
        "logs/*.txt       the logs below, rotation backups concatenated oldest-first",
        "",
    ]
    for s in sources:
        files = ", ".join(p.name for p in s.files)
        body.append(f"  {s.label:<17} {s.lines:>7} lines   from: {files}")
    body += [
        "",
        "Note: with redaction off these logs contain the titles of the windows that",
        "were focused during the timeframe, which can name documents. Check the",
        "contents before posting the bundle somewhere public.",
    ]
    return "\n".join(body) + "\n"


def build_bundle(dest: Path | str, log_dir: Path | str | None = None,
                 since: datetime | None = None, redact: bool = False,
                 diagnostics: str | None = None) -> BundleResult:
    """Write a support bundle to ``dest`` and describe what went into it.

    ``diagnostics`` is the caller's richer status block (the tray passes its
    About text, ``polyctl`` the daemon status); the environment block is always
    appended so a bundle built with no daemon reachable still identifies itself.
    """
    dest = Path(dest)
    chains = discover(log_dir)
    if not chains:
        searched = Path(log_dir) if log_dir else default_log_dir()
        raise LogBundleError(f"No PolyHost log files found in {searched}")

    results: list[SourceResult] = []
    payloads: dict[str, str] = {}
    for label, chain in chains.items():
        lines, text = _collect_source(label, chain, since, redact)
        res = SourceResult(label=label, files=list(chain), lines=len(lines),
                           bytes=len(text.encode("utf-8")))
        results.append(res)
        if lines:
            payloads[label] = text

    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", _readme(since, redact, results))
        # log_dir, so diagnostics.txt describes the crash log this zip
        # actually ships — not whatever default_log_dir() happens to find.
        diag = environment_text(include_slow=True, log_dir=log_dir)
        if diagnostics:
            diag = f"{diagnostics.rstrip()}\n\n{diag}"
        zf.writestr("diagnostics.txt", diag + "\n")
        settings = _settings_text()
        if settings:
            zf.writestr("settings.yaml", settings)
        for label, text in payloads.items():
            zf.writestr(f"logs/{label}.txt", text + "\n")

    return BundleResult(path=dest, sources=results, redacted=redact, since=since)
