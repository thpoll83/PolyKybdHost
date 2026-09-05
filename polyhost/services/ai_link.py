"""Agent ("AI") integration: the keyboard's status light and its callback key.

Two directions, and they use two different channels because the keyboard is a
keyboard:

* **host -> keyboard** is HID cmd 40 (``PolyKybd.set_ai_state``). Whatever drives the
  agent — a Claude Code hook, a Codex ``notify`` program, a one-line shell call —
  pushes a state and the AI key wears it.
* **keyboard -> host** is the firmware CONSOLE. A custom keycode is swallowed by the
  firmware, so pressing the AI key produces no HID traffic of its own, and nothing in
  the protocol lets the keyboard call us. It prints ``ai: open`` instead, and the host
  already drains the console every 250 ms for crash records — so this costs no new
  transport at all. :class:`AiScanner` is the reader.

  ⚠️ Console output is dropped while a firmware or font-pack flash is streaming (the
  worker runs the upload as one long job, so the console periodic never gets a turn),
  so a press during a flash is lost. Nothing to fix — press it again.

Everything here is Qt-free and importable without a device: :class:`PolyCore` owns the
HID half, and the window half is deliberately separable so it can be tested with no
window manager in the room.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger("polyhost")

# What the firmware prints on the release edge of the AI key (poly_keymap.c).
AI_OPEN_LINE = "ai: open"

# A press repeated faster than this is the same press as far as anyone is concerned:
# the firmware acts on the release, so a bounce cannot produce two, but a re-emitted
# console fragment could. Seconds.
PRESS_DEBOUNCE_S = 0.75


class AiScanner:
    """Reassemble console fragments into lines and report each AI key press once.

    ⚠️ A console read is a report-sized FRAGMENT, not a line — the same trap
    :class:`~polyhost.services.crash_report.CrashScanner` documents — so ``feed``
    buffers across calls and only ever classifies ``\\n``-terminated lines. Matching
    the raw chunk instead drops every continuation.

    Unlike the crash scanner this does NOT dedupe by line content: every press prints
    the same text, and the second press is a real second press. It debounces on time
    instead, which is what a duplicated fragment would trip.
    """

    MAX_PENDING = 4096   # a fragment that never terminates must not grow forever

    def __init__(self, now=None):
        self._pending = ""
        self._last = None
        self._now = now   # injectable clock; None = time.monotonic

    def _clock(self) -> float:
        if self._now is not None:
            return self._now()
        import time
        return time.monotonic()

    def feed(self, chunk: str) -> int:
        """Return how many AI key presses this chunk completed (0 or 1 in practice)."""
        if not chunk:
            return 0
        buf = self._pending + chunk
        parts = buf.split("\n")
        self._pending = parts.pop()
        if len(self._pending) > self.MAX_PENDING:
            self._pending = self._pending[-self.MAX_PENDING:]
        presses = 0
        for line in parts:
            if AI_OPEN_LINE not in line:
                continue
            now = self._clock()
            if self._last is not None and (now - self._last) < PRESS_DEBOUNCE_S:
                continue
            self._last = now
            presses += 1
        return presses


# ---------------------------------------------------------------------------
# Raising the agent's window
# ---------------------------------------------------------------------------

@dataclass
class WindowMatch:
    """One window the target pattern matched. ``handle`` is whatever the backend uses
    to identify it, kept only so the cycle can tell two identical titles apart."""

    title: str
    handle: object


def match_windows(titles, pattern: str) -> list[WindowMatch]:
    """Which of ``titles`` the pattern selects, in a STABLE order.

    The pattern is a case-insensitive substring, or a regular expression when it is
    written as ``/.../``. Substring is the default because a target is normally typed
    by a person in a hurry ("Claude"), and a regex that has to be escaped is a worse
    default than one that has to be asked for.

    Stable order matters more than it looks: it is what makes "press again for the
    next one" land on a different window rather than shuffling. The window backend
    already returns a consistent order, so this only has to preserve it.
    """
    if not pattern:
        return []
    if len(pattern) >= 2 and pattern.startswith("/") and pattern.endswith("/"):
        try:
            rx = re.compile(pattern[1:-1], re.IGNORECASE)
        except re.error as e:  # noqa: BLE001 — a bad pattern must not kill the press
            log.warning("AI target pattern %r is not a valid regex: %s", pattern, e)
            return []
        pred = lambda t: rx.search(t) is not None   # noqa: E731
    else:
        needle = pattern.casefold()
        pred = lambda t: needle in (t or "").casefold()   # noqa: E731
    out = []
    for entry in titles:
        title, handle = (entry if isinstance(entry, tuple) else (entry, entry))
        if title and pred(title):
            out.append(WindowMatch(title=title, handle=handle))
    return out


def next_index(matches: list, previous_handle) -> int:
    """Which match to raise, given the one raised last time.

    Cycling is what the user asked for with several agent sessions open, and the rule
    that makes it behave is: advance PAST the window we raised last, not "index + 1".
    Windows come and go between presses, so a stored index would point at a different
    window — or off the end — as soon as one closes. Falling back to 0 also gives the
    right answer for the first press and after every match disappeared.
    """
    if not matches:
        return -1
    if previous_handle is None:
        return 0
    for i, m in enumerate(matches):
        if m.handle == previous_handle:
            return (i + 1) % len(matches)
    return 0


class WindowRaiser:
    """Focus the agent's window, cycling through the matches on repeated presses.

    The enumerate/activate pair is injected rather than imported so this is testable
    with no window manager: :class:`PolyCore` passes the pywinctl-backed pair.

    ⚠️ Native Wayland cannot be driven this way — there is no client-callable
    activation API — which is the same limitation the window TRACKING has there. On
    such a session the press is reported and nothing is raised, and that is honest:
    silently doing nothing would read as the key being broken.
    """

    def __init__(self, enumerate_windows, activate_window):
        self._enumerate = enumerate_windows
        self._activate = activate_window
        self._last_handle = None

    def raise_next(self, pattern: str) -> tuple[bool, str]:
        """Raise the next window matching ``pattern``. Returns (ok, message)."""
        if not pattern:
            return False, ("No agent window target set. Use `polyctl ai target "
                           "\"<part of the window title>\"` first.")
        try:
            titles = list(self._enumerate())
        except Exception as e:  # noqa: BLE001 — a backend that cannot list must not raise
            return False, f"Could not list windows: {e}"
        matches = match_windows(titles, pattern)
        idx = next_index(matches, self._last_handle)
        if idx < 0:
            self._last_handle = None
            return False, f"No window matches {pattern!r} right now."
        target = matches[idx]
        try:
            ok = self._activate(target.handle)
        except Exception as e:  # noqa: BLE001
            return False, f"Could not raise {target.title!r}: {e}"
        self._last_handle = target.handle
        if not ok:
            return False, (f"The window manager refused to raise {target.title!r} "
                           f"(a native Wayland session cannot be driven this way).")
        which = f" ({idx + 1} of {len(matches)})" if len(matches) > 1 else ""
        return True, f"Raised {target.title!r}{which}."
