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

from polyhost.services.shortcut_source.model import Shortcut

#: How often a waiting harvest checks `cancel()` and whether the helper died.
POLL_SECONDS = 0.25

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

    # -- process lifecycle --------------------------------------------------

    def _start(self):
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
        proc = self._popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, **kwargs)
        lines: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, args=(proc, lines),
                         name="poly-shortcut-helper-reader", daemon=True).start()
        self._proc, self._lines = proc, lines
        log.info("Shortcut harvest helper started (pid %s)", proc.pid)

    @staticmethod
    def _read(proc, lines):
        """Move the helper's answers onto a queue; None marks its end."""
        try:
            for line in iter(proc.stdout.readline, b""):
                lines.put(line)
        except Exception:
            pass
        lines.put(None)

    def _kill(self):
        proc, self._proc, self._lines = self._proc, None, None
        if proc is None:
            return
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception:
            pass
        for pipe in (proc.stdin, proc.stdout):
            try:
                pipe.close()
            except Exception:
                pass

    def stop(self):
        """End the helper. Safe twice, never raises, and never waits on a read.

        ⚠️ Killed BEFORE taking the request lock: a harvest in flight holds it
        for as long as the walk takes (over two minutes on a long Chrome tab),
        and shutting the host down must not wait that out. The in-flight
        harvest then reads end-of-file and answers "the helper exited".
        """
        proc = self._proc
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        if self._lock.acquire(timeout=2):
            try:
                self._kill()
            finally:
                self._lock.release()

    # -- one harvest --------------------------------------------------------

    def harvest(self, app: str, reason: dict | None = None,
                pid: int | None = None, cancel=None) -> list[Shortcut]:
        reason = reason if reason is not None else {}
        while not self._lock.acquire(timeout=POLL_SECONDS):
            if cancel is not None and cancel():
                return self._abandoned(reason, "it was cancelled before it ran")
        try:
            return self._harvest_locked(app, reason, pid, cancel)
        finally:
            self._lock.release()

    def _harvest_locked(self, app, reason, pid, cancel):
        try:
            if self._proc is None or self._proc.poll() is not None:
                self._start()
            self._next_id += 1
            request_id = self._next_id
            self._proc.stdin.write(json.dumps(
                {"id": request_id, "app": app, "pid": pid}).encode("utf-8") + b"\n")
            self._proc.stdin.flush()
        except Exception as exc:
            self._kill()
            return self._abandoned(reason, f"the harvest helper could not be "
                                           f"reached: {type(exc).__name__}: {exc}")
        while True:
            try:
                line = self._lines.get(timeout=POLL_SECONDS)
            except queue.Empty:
                if cancel is not None and cancel():
                    self._kill()
                    log.info("Shortcut harvest for '%s' abandoned: focus moved "
                             "on (helper stopped)", app)
                    return self._abandoned(reason, "focus moved on before it "
                                                   "finished")
                continue
            if line is None:
                self._kill()
                return self._abandoned(reason, "the harvest helper exited")
            try:
                answer = json.loads(line)
            except ValueError:
                continue
            if not isinstance(answer, dict) or answer.get("id") != request_id:
                continue
            return self._accept(app, answer, reason)

    @staticmethod
    def _accept(app, answer, reason):
        found = decode(answer.get("shortcuts"))
        elements, seconds = answer.get("elements"), answer.get("seconds")
        if answer.get("why"):
            reason["why"] = str(answer["why"])
        if elements is not None:
            reason["elements"] = elements
        log.info("Shortcut harvest for '%s': %s UI element(s) read in %s s, "
                 "%d shortcut(s)", app,
                 elements if elements is not None else "?",
                 seconds if seconds is not None else "?", len(found))
        return found

    @staticmethod
    def _abandoned(reason, why):
        reason["why"] = f"the shortcut harvest did not run: {why}"
        reason["retry"] = True
        return []


_client: HelperClient | None = None
_client_lock = threading.Lock()


def client() -> HelperClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = HelperClient()
        return _client


def harvest(app: str, reason: dict | None = None, pid: int | None = None,
            cancel=None) -> list[Shortcut]:
    """`shortcut_source.harvest` for the UIA backend, through the helper."""
    return client().harvest(app, reason=reason, pid=pid, cancel=cancel)


def stop() -> None:
    """End the helper if one runs. Never raises."""
    with _client_lock:
        current = _client
    if current is not None:
        current.stop()
