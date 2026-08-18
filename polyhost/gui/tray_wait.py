"""Wait for the system tray before showing the tray icon.

The bug this exists for (field, 2026-08-18): the Windows logon scheduled task
starts the app before Explorer's notification area is ready. ``Shell_NotifyIcon``
then fails, and because Qt only re-adds the icon when Explorer broadcasts
``TaskbarCreated`` — which it sends when it RESTARTS, not when it finishes
starting — losing that race is permanent. The app runs perfectly for the whole
session with no icon: the daemon keeps driving the keyboard, so nothing looks
broken except that the menu is unreachable. It read as a crash, and it took a
process list to disprove.

``QSystemTrayIcon.isSystemTrayAvailable()`` answers whether the notification
area exists, so the fix is to ask, and to keep asking on a backoff until it does.

⚠️ Residual risk, deliberately not papered over: on Windows that check only looks
for the shell's tray window, so it can report available while ``Shell_NotifyIcon``
still refuses the add — and Qt reports no error either way, so we cannot tell.
If a missing icon is ever seen again WITH "icon shown" in the log, the next step
is a forced re-add (``hide()`` then ``show()``); that is not done pre-emptively
because it blinks the icon for everyone to cover a case we have not observed.

Qt-free by construction (PyQt5 is imported lazily, only by the default
scheduler), so the retry state machine is unit-testable without a display —
which matters here, because the failure only reproduces during a real logon.
"""
import time

TRAY_RETRY_FIRST_MS = 1000
TRAY_RETRY_MAX_MS = 15_000
# Explorer is normally up within seconds; five minutes is "the session is
# genuinely tray-less" (a bare WM on Linux, a locked-down shell), not "slow".
TRAY_WAIT_TIMEOUT_S = 300.0


def plan_tray_retry(attempt, elapsed_s, timeout_s=TRAY_WAIT_TIMEOUT_S):
    """Pure decision: ``(keep_waiting, delay_ms)`` for the next probe.

    Exponential backoff from 1 s to 15 s, so a normal logon costs one or two
    cheap probes while a genuinely tray-less session settles into idle polling
    instead of spinning.
    """
    if elapsed_s >= timeout_s:
        return False, 0
    delay = TRAY_RETRY_FIRST_MS * (2 ** max(0, attempt))
    return True, min(delay, TRAY_RETRY_MAX_MS)


class TrayVisibilityWaiter:
    """Show a tray icon as soon as the notification area accepts it.

    All Qt contact is injected, so the whole loop can be driven in a test:

    * ``show`` — make the icon visible (``tray.setVisible(True)``)
    * ``is_available`` — ``QSystemTrayIcon.isSystemTrayAvailable``
    * ``schedule`` — ``(delay_ms, callback)``; defaults to ``QTimer.singleShot``
    """

    def __init__(self, show, is_available, log, schedule=None,
                 clock=time.monotonic, timeout_s=TRAY_WAIT_TIMEOUT_S):
        self._show = show
        self._is_available = is_available
        self._log = log
        self._schedule = schedule or _qt_single_shot
        self._clock = clock
        self._timeout_s = timeout_s
        self._attempt = 0
        self._started = None
        self._waiting = False
        self.shown = False
        self.gave_up = False

    def start(self):
        """Show the icon, or begin waiting for the tray. Safe to call again.

        Later calls (the second one lands once the context menu is attached)
        re-assert an icon that is already up, and are a no-op while a wait is in
        flight — one retry chain only.
        """
        if self._waiting:
            return
        if self._started is None:
            self._started = self._clock()
        self._tick()

    def _tick(self):
        self._waiting = False
        if self._is_available():
            self._show()
            if self._attempt:
                self._log.info("System tray became available after %.1f s (%d probe(s)); "
                               "icon shown.", self._clock() - self._started, self._attempt)
            self.shown = True
            return

        keep, delay_ms = plan_tray_retry(self._attempt, self._clock() - self._started,
                                         self._timeout_s)
        if not keep:
            self.gave_up = True
            self._log.error(
                "No system tray after %.0f s — running WITHOUT a tray icon. The app "
                "is otherwise fine (the keyboard keeps working); restart it once the "
                "desktop is up to get the menu back.", self._clock() - self._started)
            return

        if self._attempt == 0:
            # First miss is the interesting one: it dates the logon race.
            self._log.warning("System tray not available yet (Explorer still starting?) "
                              "— waiting before showing the icon.")
        self._attempt += 1
        self._waiting = True
        self._schedule(delay_ms, self._tick)


def _qt_single_shot(delay_ms, callback):
    from PyQt5.QtCore import QTimer
    QTimer.singleShot(delay_ms, callback)
