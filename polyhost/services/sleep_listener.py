"""Qt-free systemd-logind sleep listener.

Subscribes to ``org.freedesktop.login1.Manager.PrepareForSleep`` on the system
bus and invokes a callback just before the system suspends, so callers can
persist state (the keyboard MRU) before the device loses power.

This replaces the former QtDBus-based listener in ``host.py`` (headless-core
plan H0c) — it has **zero Qt imports** and runs its receive loop on a daemon
thread. It is Linux-only and degrades gracefully (returns ``None``) on other
platforms or when no system D-Bus is reachable.
"""

import sys
import threading

# logind signal coordinates — the PrepareForSleep(b) signal carries a single
# boolean: True just before suspend, False just after resume.
_LOGIND_INTERFACE = "org.freedesktop.login1.Manager"
_PREPARE_FOR_SLEEP = "PrepareForSleep"

# How long recv_until_filtered blocks before we re-check the stop flag. Keeps
# shutdown responsive without busy-looping.
_RECV_POLL_SECONDS = 1.0


def should_fire_on_sleep(message):
    """Pure decision: given a received PrepareForSleep D-Bus message, return
    True iff it means "the system is about to sleep" (body argument True).

    Factored out so the dispatch logic is unit-testable without a live bus.
    Tolerates malformed/empty bodies by returning False.
    """
    body = getattr(message, "body", None)
    if not body:
        return False
    return bool(body[0])


class SleepListener:
    """Owns the jeepney connection + receive thread. Best-effort lifecycle."""

    def __init__(self, conn, on_sleep, log):
        self._conn = conn
        self._on_sleep = on_sleep
        self._log = log
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="sleep-listener", daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        # Import here so the module stays importable (and testable) even if the
        # transport pieces are unavailable; the connection is already open.
        from jeepney.bus_messages import MatchRule, message_bus

        rule = MatchRule(
            type="signal",
            interface=_LOGIND_INTERFACE,
            member=_PREPARE_FOR_SLEEP,
        )
        try:
            # Register the match so the bus actually routes the signal to us.
            self._conn.send_and_get_reply(message_bus.AddMatch(rule))
        except Exception as e:
            self._log.debug(
                "Could not register PrepareForSleep match: %s: %s",
                type(e).__name__, e)
            return

        try:
            with self._conn.filter(rule) as queue:
                while not self._stop.is_set():
                    try:
                        msg = self._conn.recv_until_filtered(
                            queue, timeout=_RECV_POLL_SECONDS)
                    except TimeoutError:
                        continue
                    except Exception as e:
                        # Connection closed (e.g. close() during shutdown) or any
                        # other transport error — leave the loop quietly.
                        if not self._stop.is_set():
                            self._log.debug(
                                "Sleep listener receive ended: %s: %s",
                                type(e).__name__, e)
                        return
                    try:
                        if should_fire_on_sleep(msg):
                            self._log.info(
                                "System is about to sleep — notifying handler.")
                            self._on_sleep()
                    except Exception as e:  # a bad handler must never kill the loop
                        self._log.debug(
                            "Sleep handler raised: %s: %s", type(e).__name__, e)
        except Exception as e:
            self._log.debug(
                "Sleep listener loop ended: %s: %s", type(e).__name__, e)

    def close(self):
        """Stop the thread and close the connection (best effort)."""
        self._stop.set()
        try:
            self._conn.close()
        except Exception as e:
            self._log.debug(
                "Closing sleep-listener connection failed: %s: %s",
                type(e).__name__, e)
        # The receive thread wakes within _RECV_POLL_SECONDS (or immediately, as
        # close() breaks the blocking recv) and exits; join briefly, but never
        # block shutdown if it lingers.
        if self._thread.is_alive():
            self._thread.join(timeout=_RECV_POLL_SECONDS + 0.5)


def install_sleep_listener(on_sleep, log):
    """Install a logind PrepareForSleep listener.

    :param on_sleep: zero-arg callable invoked (on the listener thread) just
        before the system suspends. Must be thread-safe — it does not run on the
        Qt main thread.
    :param log: a logger.
    :returns: a started :class:`SleepListener`, or ``None`` if unavailable
        (non-Linux platform, or no reachable system D-Bus). Never raises.
    """
    if not sys.platform.startswith("linux"):
        log.debug("Sleep listener is Linux-only; skipping on %s.", sys.platform)
        return None
    try:
        from jeepney.io.blocking import open_dbus_connection
        conn = open_dbus_connection(bus="SYSTEM")
    except Exception as e:
        # No system bus in this environment (containers, headless without
        # logind) — degrade silently to "no sleep listener".
        log.debug("System D-Bus not available; no sleep listener (%s: %s).",
                  type(e).__name__, e)
        return None
    listener = SleepListener(conn, on_sleep, log)
    listener.start()
    log.debug("logind PrepareForSleep listener installed.")
    return listener
