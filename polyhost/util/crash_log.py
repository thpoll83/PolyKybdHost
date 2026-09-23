"""Crash capture for the failure modes that otherwise leave NO trace.

Under ``pythonw.exe`` (the autostart chain launches the app windowless — see
``services/add_to_startup.py``) there is no console and ``sys.stderr`` is a
silent no-op, so the two ways this app can die both vanish without a byte on
disk:

* **an unhandled Python exception in a Qt slot.** PyQt5 calls ``sys.excepthook``
  and then ``qFatal()``, which aborts the process. The traceback goes to stderr
  — i.e. nowhere — and the tray icon simply disappears.
* **a hard fault** (SIGSEGV/SIGABRT from Qt or a C extension). Nothing Python
  ever runs again, so no ``logging`` call can report it.

:func:`install` closes both holes: ``faulthandler`` writes native tracebacks for
every thread into ``crash_log.txt``, and the two ``excepthook``s route Python
tracebacks into the caller's logger *and* that file. Both are best-effort — a
failure to install crash reporting must never stop the app from starting.

The session markers are the point of the file: ``install`` appends a
``session start`` line and :func:`note_clean_exit` appends a matching
``clean exit`` — the latter automatically, via ``atexit``, so every graceful
shutdown is covered rather than an enumerated list of ``sys.exit`` sites. A start
with no matching exit therefore means the interpreter never unwound at all: a
crash, an ``abort()``, or a kill —
which is exactly what was missing when a tray icon went missing in the field
(2026-08-18) and neither ``host_log.txt`` nor ``daemon_log.txt`` could say
whether the process had crashed or was still running, invisible.

Qt-free by construction: the Qt-side companion (``qInstallMessageHandler``,
which catches Qt's own fatals before the abort) is
:mod:`polyhost.gui.qt_crash`, so the daemon and the CLI can use this module.

⚠️ The GUI and the co-located daemon share one ``crash_log.txt``. Every line
carries the pid for that reason; don't "tidy" it away.
"""
import atexit
import logging
import os
import re
import sys
import threading
import time

CRASH_LOG = "crash_log.txt"

# ⚠️ This file is the ONE log source the bundle collector carries WHOLE,
# ignoring the timeframe the user picked (services/log_bundle.LOG_SOURCES marks
# it ``sliced=False``, because a faulthandler dump has no timestamp of its own
# to filter on). Its size is therefore *bundle* size, permanently — and a bundle
# is what gets uploaded to a public issue tracker. Steady state is nothing (two
# ~65-byte markers per session), but a crash LOOP — a fault during startup, with
# the autostart chain or the update relay relaunching — appends an all-threads
# dump of ~6 KB per iteration with nothing bounding it, in precisely the
# situation where this file matters most. Hence a cap, applied at install().
MAX_BYTES = 1024 * 1024
KEEP_BYTES = 256 * 1024

# The marker format lives HERE, with the writer, and readers import it. The
# collector (services/log_bundle.crash_summary) parses these lines; a second
# hand-written copy of the format there would fail silently on any change —
# not by raising, but by counting zero markers and reporting a confidently
# wrong "0 session(s)". Same reasoning as CRASH_LOG itself being imported
# rather than restated.
_MARKER_TIME = "%Y-%m-%d %H:%M:%S"
MARKER_RE = re.compile(
    r"^=== (?P<what>.+?) \| pid (?P<pid>\d+) \| "
    r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ===$")


def format_marker(what, pid, when=None):
    """One marker line, without its trailing newline.

    ``what`` is folded onto a single physical line first. It carries an
    interpolated ``str(exc)`` on the exception paths, and plenty of exception
    messages contain newlines — which would split the marker across lines, so
    the anchored MARKER_RE matches none of them and the crash goes UNCOUNTED in
    the report body. An undercount in the one line that says a crash happened
    is worse than an ugly one.
    """
    what = " ".join(str(what).splitlines()) or "<empty>"
    return "=== %s | pid %d | %s ===" % (
        what, pid, time.strftime(_MARKER_TIME, when or time.localtime()))


# The first line of a faulthandler dump, per platform: a POSIX signal prints
# "Fatal Python error", a Windows SEH exception prints "Windows fatal exception"
# (and, when the faulting thread has no Python state, NO "Current thread" line
# at all), and a bare dump starts at "Current thread". Readers import this
# rather than restating it, for the reason MARKER_RE is imported.
DUMP_START_PREFIXES = ("Fatal Python error", "Windows fatal exception",
                       "Current thread 0x")

# What the dump watch stamps after a dump it found. ⚠️ Must NOT contain the
# word "exception": services/log_bundle.crash_summary counts every marker
# containing it as an unhandled Python exception.
DUMP_DATED = "fault dump(s) above were written before this time"

# How often the watch looks. A dump is dated to within this many seconds.
DUMP_WATCH_SECONDS = 60.0


def parse_marker(line):
    """``(what, pid, timestamp_text)`` for a marker line, else None."""
    m = MARKER_RE.match(line)
    if not m:
        return None
    return m.group("what"), int(m.group("pid")), m.group("ts")

def trim_if_oversized(filename=CRASH_LOG, max_bytes=MAX_BYTES,
                      keep_bytes=KEEP_BYTES):
    """Bound the crash log, keeping the NEWEST whole records. Best effort.

    ⚠️ **Not** a RotatingFileHandler, and the reasons are worth stating because
    rotation is the obvious thing to reach for and it is silently wrong here:

    * ``faulthandler`` keeps the file DESCRIPTOR (see the note below). Rotation
      renames the file and the fd follows the *inode*, so the live process goes
      on dumping into ``crash_log.txt.1`` — and, once that is rotated away in
      turn, into a deleted inode. The dump lands nowhere, with nothing said.
    * ``faulthandler`` bypasses ``logging`` entirely, writing straight to the
      fd. A handler therefore never sees the 6 KB dumps that are the whole
      reason the file grows; it could only ever roll over on the marker lines.
    * The GUI and the daemon share this file, each holding its own append fd,
      so whichever rotated would orphan the other's.

    Called from :func:`install` **before** the file is opened and handed over,
    which is the only safe moment: no fd exists yet and no dump can be in
    flight. That keeps the one-stable-fd-for-the-life-of-the-process invariant
    exactly as it was.

    ⚠️ The rewrite is IN PLACE rather than the usual write-a-temp-file +
    ``os.replace``, for the same reason rotation is out: ``replace`` would swap
    the inode out from under the *other* process's open fd. Truncating instead
    is safe because every writer opens with mode ``"a"`` (O_APPEND), so a
    concurrent append resolves to the new end of file rather than a stale
    offset.

    Returns True if the file was trimmed.
    """
    try:
        size = os.path.getsize(filename)
    except OSError:
        return False  # no file yet, or unreadable — nothing to bound
    if size <= max_bytes:
        return False
    try:
        with open(filename, "rb") as fh:
            fh.seek(size - keep_bytes)
            tail = fh.read()
        # Resume at a record boundary, so half a traceback is never kept: every
        # record starts with a marker line, and a dump always follows the
        # session marker of the process that produced it. Cutting after a
        # newline also guarantees the retained bytes start on a valid UTF-8
        # boundary, whatever the seek landed in the middle of.
        cut = tail.find(b"\n=== ")
        if cut >= 0:
            tail = tail[cut + 1:]
        else:
            nl = tail.find(b"\n")
            tail = tail[nl + 1:] if nl >= 0 else b""
        note = format_marker("crash log trimmed (was %d bytes)" % size,
                             os.getpid()) + "\n"
        with open(filename, "wb") as fh:
            fh.write(note.encode("utf-8"))
            fh.write(tail)
        return True
    except Exception:  # noqa: BLE001 — reporting must never raise
        return False


# The faulthandler file must stay open and referenced for the life of the
# process: faulthandler keeps only the file DESCRIPTOR, so letting the object be
# garbage-collected closes the fd and the dump lands nowhere (or, worse, in
# whatever has since inherited that number).
_crash_file = None
_installed = False
_clean_exit_noted = False


_crash_path = None


class _DumpWatchState:
    """The dump watch's mutable state, held on one object.

    Attributes rather than module globals because each is written in one
    function and read in another, which CodeQL's per-function
    py/unused-global-variable check reports as a dead store.
    """

    def __init__(self):
        self.offset = 0          # bytes of the file already examined
        self.pending = None      # file size when an undated dump was seen
        self.stop = None         # threading.Event that ends the loop
        self.thread = None


_watch = _DumpWatchState()


def _stamp(what, lead=""):
    """Append one pid-stamped marker line to the crash file (best effort).

    Returns True if the line was written. ``lead`` goes in front of it, for a
    marker that must start on a fresh line after an unterminated one.
    """
    if _crash_file is None:
        return False
    try:
        _crash_file.write(lead + format_marker(what, os.getpid()) + "\n")
        _crash_file.flush()
        return True
    except Exception:  # noqa: BLE001 — reporting must never raise
        return False


def _file_size():
    try:
        return os.path.getsize(_crash_path)
    except (OSError, TypeError):
        return None


def check_for_undated_dump():
    """Stamp a timed marker after any faulthandler dump that has none. Best effort.

    A faulthandler dump carries no timestamp, and a non-fatal one (a Windows
    SEH exception the owning DLL then handles, such as RPC_E_DISCONNECTED) can
    repeat for hours with nothing between the dumps to say when each one
    happened. This looks at what was appended since the last call and, if a
    dump starts after the newest marker, appends one ``DUMP_DATED`` marker.

    ⚠️ Why this cannot ping-pong between the GUI and the daemon, which share
    the file and both run it: a marker line is never a dump start, and any
    marker after the dump means it is already dated. So the first process to
    look stamps, and the second sees that stamp and does nothing. Growth made
    of marker lines alone is never answered, so quiet processes write nothing.
    That also dates the dump a FATAL fault leaves behind: the faulting process
    is gone, but the other one sees the dump on its next look.

    ⚠️ A dump is stamped only once the file has not grown for one whole watch
    interval. faulthandler writes a dump in many small writes, so a size that
    is steady for the microseconds of one read can still be a dump mid-write,
    and a marker there would split it. So the first look that finds an
    undated dump only records the size (``pending``), and the next look
    stamps if the size is unchanged. That costs one interval of precision,
    not correctness. The data is deliberately NOT required to end in a
    newline: the fatal dump in the 2026-09-23 field bundle stopped mid-line,
    and that is the dump this exists to date. Instead the marker starts with
    a newline of its own when the file does not end in one.

    Returns True if a marker was written.
    """
    if _crash_file is None:
        return False
    try:
        size = _file_size()
        if size is None:
            return False
        if size < _watch.offset:
            # Truncated, by a starting process (trim_if_oversized) or a
            # "clear logs". Rescan what is left from the top rather than
            # jumping to the new end, or a dump written after the cut is
            # skipped for good. Dated dumps stay dated: their markers are in
            # what is rescanned.
            _watch.offset = 0
            _watch.pending = None
        if size == _watch.offset:
            return False
        with open(_crash_path, "rb") as fh:
            fh.seek(_watch.offset)
            new = fh.read(size - _watch.offset)
        undated = False
        for line in new.decode("utf-8", "replace").splitlines():
            if line.startswith(DUMP_START_PREFIXES):
                undated = True
            elif MARKER_RE.match(line):
                undated = False
        if not undated:
            _watch.offset = size
            _watch.pending = None
            return False
        if _watch.pending != size:
            # Found, or still growing: wait one interval for it to settle.
            # The offset stays put, so the next look reads the whole dump.
            _watch.pending = size
            return False
        lead = "" if new.endswith(b"\n") else "\n"
        if not _stamp(DUMP_DATED, lead):
            return False      # keep offset and pending: retry next time
        _watch.offset = _file_size() or size
        _watch.pending = None
        return True
    except Exception:  # noqa: BLE001 — reporting must never raise
        return False


def _watch_loop(stop, interval):
    while not stop.wait(interval):
        check_for_undated_dump()


def _start_dump_watch(interval=DUMP_WATCH_SECONDS):
    _watch.offset = _file_size() or 0
    _watch.pending = None
    _watch.stop = threading.Event()
    _watch.thread = threading.Thread(
        target=_watch_loop, args=(_watch.stop, interval),
        name="poly-crash-watch", daemon=True)
    _watch.thread.start()


def stop_dump_watch():
    """Stop the dump watch. Safe to call when it never started."""
    if _watch.stop is not None:
        _watch.stop.set()
    if _watch.thread is not None:
        _watch.thread.join(timeout=2)
    _watch.stop = None
    _watch.thread = None


def _flush_logging():
    """Force every log handler out to disk.

    ``sys.excepthook`` runs microseconds before PyQt5's ``qFatal()`` aborts the
    process, so anything still sitting in a buffer is lost. ``StreamHandler``
    flushes per record already; this covers handlers that don't.
    """
    for handler in logging.getLogger().handlers:
        try:
            handler.flush()
        except Exception:  # noqa: BLE001
            pass


def install(log=None, filename=CRASH_LOG):
    """Install faulthandler + the exception hooks. Idempotent.

    Returns True if this call installed them, False if they were already in
    place or installation failed. ``log`` is the logger tracebacks are reported
    through (the startup logger, so a crash during construction is captured too).
    """
    global _crash_file, _crash_path, _installed
    if _installed:
        return False
    log = log or logging.getLogger("PolyHost")

    # Before the open, never after: from here on the fd is faulthandler's and
    # must not be disturbed. See trim_if_oversized's note.
    trim_if_oversized(filename)

    try:
        # line buffering: a dump must reach disk before the process dies.
        _crash_file = open(filename, "a", buffering=1, encoding="utf-8")
        _crash_path = os.path.abspath(filename)
    except OSError as e:
        # A read-only cwd shouldn't stop the app from launching (same stance as
        # the startup log). Carry on with the hooks; they still reach the logger.
        log.warning("Crash log unavailable (%s: %s); hooks still installed.",
                    type(e).__name__, e)
        _crash_file = None

    if _crash_file is not None:
        try:
            import faulthandler
            # `file=` is REQUIRED here, not a nicety: the default is sys.stderr,
            # which is None under pythonw, and faulthandler.enable() then raises.
            faulthandler.enable(file=_crash_file, all_threads=True)
        except Exception as e:  # noqa: BLE001
            log.warning("faulthandler not enabled (%s: %s).", type(e).__name__, e)

    _install_excepthooks(log)
    # Mark every graceful exit, rather than calling note_clean_exit() at each
    # `sys.exit` site. main_app alone has five, three of them entirely routine
    # (a second launch finding the socket already served exits 0 — that would
    # otherwise stamp a "crash" on a normal event), and an enumerated list is
    # exactly the kind of guard that goes stale the next time someone adds a
    # branch. atexit has the semantics we want for free: it runs on any
    # interpreter shutdown including sys.exit, and does NOT run on abort(),
    # SIGSEGV, a kill, or os.execv — which are precisely the cases that must
    # stay unmarked.
    atexit.register(_atexit_marker)
    _stamp("session start")
    if _crash_file is not None:
        # After the session marker, so everything already in the file counts
        # as seen: a dump left by a previous run is dated by that marker.
        try:
            _start_dump_watch()
        except Exception as e:  # noqa: BLE001
            log.warning("Crash dump watch not started (%s: %s).",
                        type(e).__name__, e)
    _installed = True
    return True


def _atexit_marker():
    """Stamp a clean exit unless one was already recorded explicitly."""
    if not _clean_exit_noted:
        _stamp("clean exit (interpreter shutdown)")


def _install_excepthooks(log):
    previous = sys.excepthook

    def _hook(exc_type, exc, tb):
        try:
            log.critical("UNHANDLED EXCEPTION — the process is about to die "
                         "(PyQt aborts after this hook returns)",
                         exc_info=(exc_type, exc, tb))
            _flush_logging()
            _stamp("unhandled exception: %s: %s" % (exc_type.__name__, exc))
            if _crash_file is not None:
                import traceback
                traceback.print_exception(exc_type, exc, tb, file=_crash_file)
                _crash_file.flush()
        except Exception:  # noqa: BLE001 — never raise from the last-resort hook
            pass
        try:
            previous(exc_type, exc, tb)
        except Exception:  # noqa: BLE001
            pass

    sys.excepthook = _hook

    # A thread that dies takes its work with it silently — the worker, the event
    # pump and the updater threads all matter enough to hear about.
    previous_thread_hook = threading.excepthook

    def _thread_hook(args):
        # SystemExit is how a thread asks to stop; the stdlib default ignores it
        # silently, so reporting it would invent noise the app never had.
        if args.exc_type is not SystemExit:
            try:
                log.critical("UNHANDLED EXCEPTION in thread %r",
                             getattr(args.thread, "name", "?"),
                             exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
                _flush_logging()
                _stamp("thread exception (%s): %s"
                       % (getattr(args.thread, "name", "?"), args.exc_value))
            except Exception:  # noqa: BLE001 — never raise from the last-resort hook
                pass
        # Chain, for the same reason sys.excepthook does: we are a reporter, not
        # a replacement, and whatever was installed before (the stdlib default, a
        # test harness, a debugger) keeps its behaviour.
        try:
            previous_thread_hook(args)
        except Exception:  # noqa: BLE001
            pass

    threading.excepthook = _thread_hook


def note_clean_exit(log=None, what="process", rc=None):
    """Record that this process is exiting on purpose.

    The value is entirely in its ABSENCE: a ``session start`` with no matching
    ``clean exit`` line means the process was killed or crashed. Call it on
    every deliberate exit path.
    """
    global _clean_exit_noted
    log = log or logging.getLogger("PolyHost")
    if _clean_exit_noted:
        return
    _clean_exit_noted = True
    if rc is None:
        log.info("%s exited cleanly.", what)
        _stamp("clean exit (%s)" % what)
    else:
        log.info("%s exited cleanly (rc=%s).", what, rc)
        _stamp("clean exit (%s, rc=%s)" % (what, rc))
    _flush_logging()
