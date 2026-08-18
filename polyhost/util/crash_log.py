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
``clean exit``. A start with no matching exit is, by itself, the diagnosis (the
process crashed, was killed, or bailed out early — the latter always logs its
own error first, so the two are easy to tell apart) —
which is exactly what was missing when a tray icon went missing in the field
(2026-08-18) and neither ``host_log.txt`` nor ``daemon_log.txt`` could say
whether the process had crashed or was still running, invisible.

Qt-free by construction: the Qt-side companion (``qInstallMessageHandler``,
which catches Qt's own fatals before the abort) is
:mod:`polyhost.gui.qt_crash`, so the daemon and the CLI can use this module.

⚠️ The GUI and the co-located daemon share one ``crash_log.txt``. Every line
carries the pid for that reason; don't "tidy" it away.
"""
import logging
import os
import sys
import threading
import time

CRASH_LOG = "crash_log.txt"

# The faulthandler file must stay open and referenced for the life of the
# process: faulthandler keeps only the file DESCRIPTOR, so letting the object be
# garbage-collected closes the fd and the dump lands nowhere (or, worse, in
# whatever has since inherited that number).
_crash_file = None
_installed = False


def _stamp(what):
    """Append one pid-stamped marker line to the crash file (best effort)."""
    if _crash_file is None:
        return
    try:
        _crash_file.write("=== %s | pid %d | %s ===\n"
                          % (what, os.getpid(),
                             time.strftime("%Y-%m-%d %H:%M:%S")))
        _crash_file.flush()
    except Exception:  # noqa: BLE001 — reporting must never raise
        pass


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
    global _crash_file, _installed
    if _installed:
        return False
    log = log or logging.getLogger("PolyHost")

    try:
        # line buffering: a dump must reach disk before the process dies.
        _crash_file = open(filename, "a", buffering=1, encoding="utf-8")
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
    _stamp("session start")
    _installed = True
    return True


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
    def _thread_hook(args):
        if args.exc_type is SystemExit:
            return
        try:
            log.critical("UNHANDLED EXCEPTION in thread %r",
                         getattr(args.thread, "name", "?"),
                         exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
            _flush_logging()
            _stamp("thread exception (%s): %s"
                   % (getattr(args.thread, "name", "?"), args.exc_value))
        except Exception:  # noqa: BLE001
            pass

    threading.excepthook = _thread_hook


def note_clean_exit(log=None, what="process", rc=None):
    """Record that this process is exiting on purpose.

    The value is entirely in its ABSENCE: a ``session start`` with no matching
    ``clean exit`` line means the process was killed or crashed. Call it on
    every deliberate exit path.
    """
    log = log or logging.getLogger("PolyHost")
    if rc is None:
        log.info("%s exited cleanly.", what)
        _stamp("clean exit (%s)" % what)
    else:
        log.info("%s exited cleanly (rc=%s).", what, rc)
        _stamp("clean exit (%s, rc=%s)" % (what, rc))
    _flush_logging()
