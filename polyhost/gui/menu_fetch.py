"""Menu state fetched, and menu clicks sent, off the GUI thread.

A tray submenu that shows device state (the ticked idle style, legend size,
glyph script, emoji search dictionary, the font row under Updates, the
brightness "automatic" row) asks the core when it opens. In client mode that
is an RPC to the daemon, and an RPC has no timeout: a daemon that stalls would
freeze the whole tray while the menu waits. :class:`MenuFetcher` runs the call
on a background thread and applies the answer on the GUI thread. Until the
answer arrives the menu shows what it showed last time.

Rules for a caller:

* ``fetch`` runs the core call off the GUI thread and nothing else there.
  ``apply`` gets the result (or the exception it raised) on the GUI thread and
  is the only place that touches Qt objects.
* One call per key is in flight at a time. Opening the menu again while it is
  pending starts nothing new; the pending answer still updates it.
* The threads are daemon threads, so a call that never returns does not keep
  the process alive at exit.

A menu CLICK that changes something on the keyboard goes through ``call(fn,
apply)`` instead. Clicks run one at a time, in the order they were made, on one
background thread: two quick clicks on Keycap Size must reach the keyboard in
that order. ``apply`` again runs on the GUI thread.
"""
import logging
import queue
import threading
import time

from PyQt5.QtCore import QCoreApplication, QObject, pyqtSignal


class MenuFetcher(QObject):
    """Runs ``fn()`` on a background thread, then ``apply(result)`` on the GUI thread."""

    # (key, result or exception, apply). Emitted from the fetch thread; the
    # receiver lives on the GUI thread, so Qt queues the call there.
    _done = pyqtSignal(str, object, object)

    def __init__(self, parent=None, log=None):
        super().__init__(parent)
        self.log = log or logging.getLogger("PolyHost")
        self._busy = set()          # keys with a call in flight; GUI thread only
        self._calls = queue.Queue()  # (fn, apply) of clicks, in click order
        self._calls_pending = 0     # GUI thread only
        self._call_thread = None
        self._done.connect(self._deliver)

    def fetch(self, key, fn, apply):
        """Start ``fn`` for ``key`` unless one is already running. Returns
        whether a new call was started."""
        if key in self._busy:
            return False
        self._busy.add(key)

        def run():
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001 — handed to apply, never lost
                result = exc
            self._done.emit(key, result, apply)

        threading.Thread(target=run, name=f"menu-fetch-{key}", daemon=True).start()
        return True

    def call(self, fn, apply=None):
        """Queue a click's core call. Calls run one at a time in this order, off
        the GUI thread; ``apply(result)`` then runs on the GUI thread."""
        self._calls_pending += 1
        self._calls.put((fn, apply))
        if self._call_thread is None:
            self._call_thread = threading.Thread(target=self._run_calls, name="menu-call",
                                                 daemon=True)
            self._call_thread.start()

    def _run_calls(self):
        while True:
            fn, apply = self._calls.get()
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001 — handed to apply, never lost
                result = exc
            self._done.emit("", result, apply)

    def _deliver(self, key, result, apply):
        if key:
            self._busy.discard(key)
        else:
            self._calls_pending -= 1
            if apply is None:
                if isinstance(result, Exception):
                    self.log.warning("Menu action failed: %s", result)
                return
        if isinstance(result, Exception):
            self.log.debug("Menu state %s unavailable: %s", key, result)
        try:
            apply(result)
        except Exception:  # noqa: BLE001 — one bad menu must not break the tray
            self.log.exception("Applying the %s menu state failed", key)

    def busy(self):
        return bool(self._busy) or self._calls_pending > 0

    def wait_idle(self, timeout=5.0):
        """Process Qt events until no call is in flight (for tests). Returns
        whether it finished within ``timeout`` seconds."""
        end = time.monotonic() + timeout
        while self.busy() and time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.005)
        QCoreApplication.processEvents()
        return not self.busy()


def ok_value(result):
    """The ``(ok, value)`` pair of a core call's result: ``(False, message)`` for
    an exception, ``(False, None)`` for anything else that is not a pair."""
    if isinstance(result, (tuple, list)) and len(result) == 2:
        return bool(result[0]), result[1]
    if isinstance(result, Exception):
        return False, str(result)
    return False, None
