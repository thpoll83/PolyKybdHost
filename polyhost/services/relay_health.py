"""Whether to attempt a window report now, and what — if anything — to say.

⚠️ **A DAEMON THAT IS DOWN IS ONE CONDITION, NOT ONE PER WINDOW.** The forwarder
used to attempt a 3 s connect on every window change and log an ERROR for each
one. A field log (2026-09-18) carried **216 identical "timed out" lines** in a
single stretch and 125 in another, and `RepeatCollapseHandler` could not fold
them because the `Active App:` line between each pair differs every time. The
noise was the visible half; the expensive half is that each attempt BLOCKS the
window poll for the whole socket timeout, so a dead daemon stalled the tick on
every focus change.

⚠️ **This module is where that logic lives because `polyhost/forwarder.py` is
UNTESTABLE in the documented environment** — it imports pywinctl at module load,
so a test gated on that is permanently skipped, which reads as coverage. Same
seam as `polyhost/core/decisions.py`: the state machine is pure and the Qt/socket
half calls it.
"""

from __future__ import annotations

# Doubling, from the first failure to the cap.
MIN_BACKOFF_SEC = 2.0
MAX_BACKOFF_SEC = 30.0
# ⚠️ One line at the start and then silence for four hours reads as the forwarder
# having stopped, so a long outage still gets a periodic reminder. This is the
# compromise, not an oversight.
STILL_DOWN_EVERY_SEC = 300.0


class RelayHealth:
    """The up/down state of the window-report relay.

    `should_attempt()` answers whether to spend a socket timeout right now;
    `note()` records the outcome and returns the ONE thing worth logging, or
    None. Nothing here logs, formats a host name, or knows what a socket is.
    """

    def __init__(self, min_backoff: float = MIN_BACKOFF_SEC,
                 max_backoff: float = MAX_BACKOFF_SEC,
                 still_down_every: float = STILL_DOWN_EVERY_SEC):
        self.min_backoff = min_backoff
        self.max_backoff = max_backoff
        self.still_down_every = still_down_every
        # None = nothing attempted yet, False = down, True = up.
        # ⚠️ Only `is False` is ever tested, so None and True behave alike HERE —
        # the tri-state is the forwarder's (`relay_ok` drives a three-way tray
        # mark). Do not write a test for the difference; there isn't one.
        self.ok = None
        self.reason = None
        self.failures = 0
        self._down_since = 0.0
        self._said_down_at = 0.0
        self._retry_at = 0.0
        self._backoff = min_backoff

    def reset(self) -> None:
        """Forget the outage — the next attempt happens immediately.

        ⚠️ For a DELIBERATE user action only (un-pausing, a changed host). A
        backoff is a rate limit on the machine's own retries; making someone who
        just pressed Resume wait out a 30 s timer is the wrong answer to a
        question they already answered.
        """
        self.__init__(self.min_backoff, self.max_backoff, self.still_down_every)

    # ------------------------------------------------------------------ query

    def should_attempt(self, now: float) -> bool:
        """False only while the relay is known-down and the backoff has not expired."""
        return not (self.ok is False and now < self._retry_at)

    # ----------------------------------------------------------------- record

    def note(self, ok: bool, now: float, reason: str | None = None):
        """Record an attempt. Returns (level, message) to log, or None.

        `level` is one of "error" (it just went down), "warning" (still down,
        periodic reminder) or "info" (it came back).
        """
        if ok:
            recovered = self.ok is False
            failures, down_for = self.failures, now - self._down_since
            self.ok = True
            self.reason = None
            self.failures = 0
            # ⚠️ The backoff ladder is NOT reset here, and that is deliberate
            # rather than an omission: the next failure takes the `first` branch
            # below (because `ok` is no longer False) and starts the ladder at
            # `min_backoff` anyway. A mutation sweep showed resetting it here as
            # well changes nothing, and state that cannot matter reads as if it
            # does.
            if recovered:
                return ("info", "reports are landing again — %d failed over %s"
                        % (failures, duration(down_for)))
            return None

        first = self.ok is not False
        self.reason = reason
        if first:
            self._down_since = now
            self._said_down_at = now
            self.failures = 0
        self.ok = False
        self.failures += 1
        # ⚠️ The FIRST retry waits `min_backoff`, not double it — doubling from
        # the start means the shortest outage anyone notices already costs 4 s.
        self._backoff = (self.min_backoff if first
                         else min(self.max_backoff, self._backoff * 2))
        self._retry_at = now + self._backoff
        if first:
            return ("error", "reports are not landing: %s — retrying with a"
                    " backoff; logged once, not once per window" % (reason,))
        return self.tick(now)

    def tick(self, now: float):
        """The periodic still-down reminder. Returns (level, message) or None.

        ⚠️ Called on the SKIPPED attempts too, or a relay that is down long
        enough for the backoff to swallow every attempt would never speak again.
        """
        if self.ok is not False:
            return None
        if now - self._said_down_at < self.still_down_every:
            return None
        self._said_down_at = now
        return ("warning", "reports still not landing after %s (%d attempts): %s"
                % (duration(now - self._down_since), self.failures, self.reason))


def duration(seconds: float) -> str:
    """A short human duration for a log line — "42s", "7m12s", "4h05m"."""
    seconds = int(max(0.0, seconds))
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm%02ds" % (seconds // 60, seconds % 60)
    return "%dh%02dm" % (seconds // 3600, (seconds % 3600) // 60)
