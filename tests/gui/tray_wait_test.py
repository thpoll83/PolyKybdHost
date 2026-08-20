"""Tests for the tray-availability wait (polyhost/gui/tray_wait.py).

The bug it fixes only reproduces during a real Windows logon, so the retry loop
is driven here with injected Qt seams instead — no display, no PyQt5.
"""
import logging
import unittest

from polyhost.gui.tray_wait import (
    TRAY_RETRY_MAX_MS, TrayVisibilityWaiter, plan_tray_retry)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class Harness:
    """Collects the waiter's Qt-side effects and lets the test run the timers."""

    def __init__(self, available_after=0):
        self.available_after = available_after   # probes to fail before answering
        self.probes = 0
        self.shows = 0
        self.scheduled = []                      # [(delay_ms, callback), ...]

    def is_available(self):
        self.probes += 1
        return self.probes > self.available_after

    def show(self):
        self.shows += 1

    def schedule(self, delay_ms, callback):
        self.scheduled.append((delay_ms, callback))

    def run_pending(self):
        """Fire every scheduled callback once (a Qt event-loop turn)."""
        pending, self.scheduled = self.scheduled, []
        for _delay, callback in pending:
            callback()


def make_waiter(harness, clock=None, timeout_s=300.0):
    return TrayVisibilityWaiter(
        show=harness.show, is_available=harness.is_available,
        log=logging.getLogger("test-tray"), schedule=harness.schedule,
        clock=clock or FakeClock(), timeout_s=timeout_s)


class PlanTrayRetryTest(unittest.TestCase):
    def test_backs_off_exponentially_then_caps(self):
        delays = [plan_tray_retry(n, 0.0)[1] for n in range(8)]
        self.assertEqual(delays[:4], [1000, 2000, 4000, 8000])
        self.assertTrue(all(d <= TRAY_RETRY_MAX_MS for d in delays))
        self.assertEqual(delays[-1], TRAY_RETRY_MAX_MS)

    def test_gives_up_once_the_timeout_is_reached(self):
        self.assertEqual(plan_tray_retry(3, 299.0, timeout_s=300.0)[0], True)
        self.assertEqual(plan_tray_retry(3, 300.0, timeout_s=300.0)[0], False)


class TrayVisibilityWaiterTest(unittest.TestCase):
    def test_shows_immediately_when_the_tray_is_up(self):
        h = Harness(available_after=0)
        w = make_waiter(h)
        w.start()
        self.assertTrue(w.shown)
        self.assertEqual(h.shows, 1)
        self.assertEqual(h.scheduled, [])       # no timer armed in the normal case

    def test_waits_then_shows_when_the_tray_arrives_late(self):
        """The logon race: Explorer's notification area shows up a few probes in."""
        h = Harness(available_after=2)
        w = make_waiter(h)
        w.start()
        self.assertFalse(w.shown)
        self.assertEqual(h.shows, 0)
        self.assertEqual([d for d, _ in h.scheduled], [1000])

        h.run_pending()                          # probe 2 — still nothing
        self.assertEqual([d for d, _ in h.scheduled], [2000])

        h.run_pending()                          # probe 3 — the tray answers
        self.assertTrue(w.shown)
        self.assertEqual(h.shows, 1)
        self.assertEqual(h.scheduled, [])

    def test_gives_up_after_the_timeout_without_showing(self):
        clock = FakeClock()
        h = Harness(available_after=10_000)       # never becomes available
        w = make_waiter(h, clock=clock, timeout_s=10.0)
        w.start()
        clock.now = 11.0
        h.run_pending()
        self.assertTrue(w.gave_up)
        self.assertFalse(w.shown)
        self.assertEqual(h.shows, 0)
        self.assertEqual(h.scheduled, [])         # stops rather than spinning

    def test_second_start_while_waiting_does_not_fork_a_second_chain(self):
        """host.py calls start() again once the context menu is attached."""
        h = Harness(available_after=1)
        w = make_waiter(h)
        w.start()
        probes_after_first = h.probes
        w.start()
        w.start()
        self.assertEqual(h.probes, probes_after_first)   # no extra probing
        self.assertEqual(len(h.scheduled), 1)            # exactly one timer armed

    def test_start_after_success_reasserts_the_icon(self):
        h = Harness(available_after=0)
        w = make_waiter(h)
        w.start()
        w.start()
        self.assertEqual(h.shows, 2)


if __name__ == "__main__":
    unittest.main()
