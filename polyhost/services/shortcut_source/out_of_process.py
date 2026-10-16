"""Run the Windows UIA harvest in a helper process, so it cannot stall the host.

⚠️ **A background THREAD was not enough.** The harvest already ran on its own
thread (`ShortcutIconFetcher._loop`), and still froze the whole daemon while it
read Chrome: on 2026-10-15 a read of a long Claude Code tab took ~2 min 17 s,
and in that window the window-tracking tick took 63.9 s, 38.4 s and 89.1 s, the
brightness request 12 s instead of 0.3 s, and the tray menu (an RPC into the
daemon) took as long to open. Three unrelated threads stalling together is the
interpreter lock: Python threads in one process share it, so the walk starved
everything else. A separate process has its own.

The helper (`shortcut_source.worker`) is started on the first harvest and kept
for the next ones, because starting Python and importing comtypes costs about
a second. It talks JSON lines over its stdin/stdout. Two more things only a
process allows:

* **A read can be abandoned.** `cancel()` is polled while the answer is
  awaited; when it says so the helper is KILLED (a thread cannot be) and the
  next harvest starts a fresh one. The fetcher cancels when focus has left the
  app being read, so a 2-minute walk of a tab already left no longer runs on.
* **COM leaves the daemon.** The UIA objects and their COM apartment live in the
  helper, so a native fault in them (the `0x80010108` dumps, the 2026-09-23
  access violation) can end only the helper.

Nothing here raises; a failure is an empty list plus `reason["why"]`, with
`reason["retry"]` set because the helper failing says nothing about the app.

⚠️ **Every way a read can end is logged, at INFO or above,** because the
feature runs unattended and a log bundle is all a problem report brings back:
the helper's start (interpreter and pid), each answer (which window, whose
process, how many elements, how long), a read skipped or abandoned for focus,
the helper's exit code, and every line the helper writes to stderr -- its
tracebacks and its `faulthandler` dumps -- forwarded into the host's log as
WARNINGs. The helper writes no log file of its own, which would reach nobody
(`log_bundle.LOG_SOURCES`).
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time

from polyhost.services.shortcut_source.model import Shortcut

#: How often a waiting harvest checks `cancel()` and whether the helper died.
POLL_SECONDS = 0.25
#: The longest one read may take before the helper is killed and the read
#: retried under the fetcher's backoff. The maintainer's number (2026-10-15);
#: the longest read measured in the field was ~2 min 17 s, a long Claude Code
#: tab in Chrome. Bounds a helper that hangs while its app stays focused.
HARVEST_TIMEOUT_SECONDS = 3 * 60

_FIELDS = {f.name for f in dataclasses.fields(Shortcut)}

log = logging.getLogger("PolyHost")


def python_for_helper(executable: str | None = None) -> str:
    """The interpreter to start the helper with.

    ⚠️ `python.exe`, not `pythonw.exe`, when the host runs under the latter: the
    helper talks over its std handles, and a GUI-subsystem interpreter starts
    with no `sys.stdout`. CREATE_NO_WINDOW keeps the console one windowless.
    """
    executable = executable or sys.executable
    folder, name = os.path.split(executable)
    if name.lower() == "pythonw.exe":
        console = os.path.join(folder, "python.exe")
        if os.path.exists(console):
            return console
    return executable


def _package_root() -> str:
    """The directory holding the `polyhost` package, so `-m` finds it."""
    import polyhost
    return os.path.dirname(os.path.dirname(os.path.abspath(polyhost.__file__)))


def decode(items) -> list[Shortcut]:
    """The helper's shortcut dicts -> `Shortcut`s. Drops what does not fit."""
    out = []
    for item in items if isinstance(items, list) else ():
        if not isinstance(item, dict):
            continue
        try:
            out.append(Shortcut(**{k: v for k, v in item.items() if k in _FIELDS}))
        except TypeError:
            continue
    return out


class HelperClient:
    """One helper process, one request at a time."""

    def __init__(self, command=None, popen=subprocess.Popen):
        self._command = command
        self._popen = popen
        self._lock = threading.Lock()      # one request in flight
        self._proc = None
        self._lines: queue.Queue | None = None
        self._next_id = 0
        # Set by `stop()`, so the read it interrupts is not logged as a crash.
        self._stopping = False
        # Set by `stop()` for good: no helper may start after it (Sourcery,
        # #393: a harvest holding the lock could otherwise start one while
        # `stop()` waited for that lock, and it would outlive shutdown).
        self._closed = False

    # -- process lifecycle --------------------------------------------------

    def _start(self):
        if self._closed:
            raise RuntimeError("the harvest helper was stopped")
        command = self._command or [python_for_helper(), "-m",
                                    "polyhost.services.shortcut_source.worker"]
        kwargs = {}
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if self._command is None:
            kwargs["cwd"] = _package_root()
        # Audit: the command is fixed, our own interpreter running our own
        # module (or a test's stand-in); no user or remote input reaches it.
        # nosemgrep: dangerous-subprocess-use-audit
        try:
            proc = self._popen(command, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               **kwargs)
        except Exception as exc:
            log.warning("Shortcut harvest helper could not be started (%s): "
                        "%s: %s", command[0], type(exc).__name__, exc)
            raise
        if self._closed:
            # `stop()` ran while this one was starting: it saw no process to
            # kill, so this is the only place that can.
            proc.kill()
            raise RuntimeError("the harvest helper was stopped")
        lines: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, args=(proc, lines),
                         name="poly-shortcut-helper-reader", daemon=True).start()
        threading.Thread(target=self._forward_stderr, args=(proc,),
                         name="poly-shortcut-helper-stderr", daemon=True).start()
        self._proc, self._lines = proc, lines
        self._stopping = False
        log.info("Shortcut harvest helper started (pid %s, %s)", proc.pid,
                 command[0])

    @staticmethod
    def _read(proc, lines):
        """Move the helper's answers onto a queue; None marks its end."""
        try:
            for line in iter(proc.stdout.readline, b""):
                lines.put(line)
        except Exception:
            # The pipe was closed under us (`_kill`): that is the end of the
            # helper either way, and the None below says so to the waiter.
            pass
        lines.put(None)

    @staticmethod
    def _forward_stderr(proc):
        """Every stderr line of the helper into the host log, as a WARNING.

        The helper writes there only when something went wrong: an uncaught
        traceback, or a `faulthandler` dump of a native fault in UIA/COM.
        """
        try:
            for raw in iter(proc.stderr.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip()
                if line:
                    log.warning("Shortcut harvest helper (pid %s): %s",
                                proc.pid, line)
        except Exception:
            # The pipe was closed under us (`_kill`); nothing is left to read.
            pass

    def _kill(self):
        proc, self._proc, self._lines = self._proc, None, None
        if proc is None:
            return
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception:
            # Already dead, or not reaped within 2 s: either way it is no
            # longer ours, and the next harvest starts a fresh helper.
            pass
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            try:
                pipe.close()
            except Exception:
                # Closing a pipe of a dead process can fail; nothing to undo.
                pass

    def stop(self):
        """End the helper. Safe twice, never raises, and never waits on a read.

        ⚠️ Killed BEFORE taking the request lock: a harvest in flight holds it
        for as long as the walk takes (over two minutes on a long Chrome tab),
        and shutting the host down must not wait that out. The in-flight
        harvest then reads end-of-file and answers "the helper exited".
        """
        self._closed = True
        proc = self._proc
        if proc is not None:
            self._stopping = True
            try:
                proc.kill()
            except Exception:
                # Already exited; `_kill` below still closes its pipes.
                pass
        if self._lock.acquire(timeout=2):
            try:
                self._kill()
            finally:
                self._lock.release()

    # -- one harvest --------------------------------------------------------

    def harvest(self, app: str, reason: dict | None = None,
                pid: int | None = None, cancel=None,
                hwnd: int | None = None) -> list[Shortcut]:
        reason = reason if reason is not None else {}
        while not self._lock.acquire(timeout=POLL_SECONDS):
            if cancel is not None and cancel():
                return self._skipped(app, reason)
        try:
            # ⚠️ Checked BEFORE the request, not only while waiting for its
            # answer: a read queued for an app that has since lost focus would
            # otherwise start on whatever window is in front now (2026-10-15:
            # queued for Zoom, ran seven minutes later on Chrome).
            if cancel is not None and cancel():
                return self._skipped(app, reason)
            return self._harvest_locked(app, reason, pid, cancel, hwnd)
        finally:
            self._lock.release()

    def _harvest_locked(self, app, reason, pid, cancel, hwnd):
        try:
            if self._proc is None or self._proc.poll() is not None:
                self._start()
            self._next_id += 1
            request_id = self._next_id
            self._proc.stdin.write(json.dumps(
                {"id": request_id, "app": app, "pid": pid, "hwnd": hwnd}
            ).encode("utf-8") + b"\n")
            self._proc.stdin.flush()
        except Exception as exc:
            self._kill()
            return self._abandoned(reason, f"the harvest helper could not be "
                                           f"reached: {type(exc).__name__}: {exc}")
        deadline = time.monotonic() + HARVEST_TIMEOUT_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._kill()
                log.warning("Shortcut harvest for '%s' abandoned: no answer in "
                            "%d s (helper stopped)", app, HARVEST_TIMEOUT_SECONDS)
                return self._abandoned(reason, f"no answer in "
                                               f"{HARVEST_TIMEOUT_SECONDS} s")
            try:
                line = self._lines.get(timeout=min(POLL_SECONDS, remaining))
            except queue.Empty:
                if cancel is not None and cancel():
                    self._kill()
                    log.info("Shortcut harvest for '%s' abandoned: focus moved "
                             "on (helper stopped)", app)
                    return self._abandoned(reason, "focus moved on before it "
                                                   "finished")
                continue
            if line is None:
                code = self._exit_code()
                if self._stopping:
                    log.info("Shortcut harvest for '%s' ended: the host stopped "
                             "the helper", app)
                else:
                    log.warning("Shortcut harvest helper exited (code %s) while "
                                "reading '%s'", code, app)
                self._kill()
                return self._abandoned(reason, f"the harvest helper exited "
                                               f"(code {code})")
            try:
                answer = json.loads(line)
            except ValueError:
                continue
            if not isinstance(answer, dict) or answer.get("id") != request_id:
                continue
            return self._accept(app, answer, reason)

    def _exit_code(self):
        """The helper's exit code, once it has ended; None if it has not."""
        try:
            return self._proc.wait(timeout=2) if self._proc is not None else None
        except Exception:
            return None

    @staticmethod
    def _accept(app, answer, reason):
        found = decode(answer.get("shortcuts"))
        elements, seconds = answer.get("elements"), answer.get("seconds")
        why = answer.get("why")
        if why:
            reason["why"] = str(why)
        if answer.get("retry"):
            reason["retry"] = True
        if elements is not None:
            reason["elements"] = elements
        log.info("Shortcut harvest for '%s': %s -> %s UI element(s) read in "
                 "%s s, %d shortcut(s)%s", app, _describe_root(answer),
                 elements if elements is not None else "?",
                 seconds if seconds is not None else "?", len(found),
                 f" ({why})" if why else "")
        return found

    @staticmethod
    def _skipped(app, reason):
        log.info("Shortcut harvest for '%s' skipped: focus moved on before it "
                 "started", app)
        return HelperClient._abandoned(reason, "focus moved on before it started")

    @staticmethod
    def _abandoned(reason, why):
        reason["why"] = f"the shortcut harvest did not run: {why}"
        reason["retry"] = True
        return []


def _describe_root(answer: dict) -> str:
    """Which window the helper read, for the log: handle, process, class.

    The class name (`Chrome_WidgetWin_1`) names the toolkit, never a document,
    so it is safe in a log bundle; the window's NAME is its title and is left
    out for that reason.
    """
    hwnd = answer.get("hwnd")
    where = (f"window 0x{int(hwnd):X}" if isinstance(hwnd, int)
             else "the focused window")
    parts = []
    if answer.get("root_pid") is not None:
        parts.append(f"pid {answer['root_pid']}")
    if answer.get("root_class"):
        # Escaped: any local app chooses its class name, and a CR/LF in it
        # would forge lines in the host log (Sourcery, #393).
        cls = str(answer["root_class"])[:80].encode("unicode_escape").decode("ascii")
        parts.append(f"class {cls}")
    return f"{where} ({', '.join(parts)})" if parts else where


_client: HelperClient | None = None
_client_lock = threading.Lock()


def client() -> HelperClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = HelperClient()
        return _client


def harvest(app: str, reason: dict | None = None, pid: int | None = None,
            cancel=None, hwnd: int | None = None) -> list[Shortcut]:
    """`shortcut_source.harvest` for the UIA backend, through the helper."""
    return client().harvest(app, reason=reason, pid=pid, cancel=cancel, hwnd=hwnd)


def stop() -> None:
    """End the helper if one runs. Never raises.

    The stopped client is dropped, so a later harvest (a new fetcher) gets a
    fresh one rather than a client that refuses to start.
    """
    global _client
    with _client_lock:
        current, _client = _client, None
    if current is not None:
        current.stop()
