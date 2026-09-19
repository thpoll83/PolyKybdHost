"""The relay's up/down state machine — the part of the forwarder that CAN be tested.

⚠️ `polyhost/forwarder.py` imports pywinctl at module load, so a test of it is
permanently skipped in the documented environment, which reads as coverage. This
suite exists because the backoff and the log-once rules are exactly the logic
worth pinning, and they were extracted so they could be.
"""
import unittest

from polyhost.services.relay_health import RelayHealth, duration


class BackoffTest(unittest.TestCase):

    def test_the_FIRST_attempt_is_always_allowed(self):
        self.assertTrue(RelayHealth().should_attempt(0.0))

    def test_a_failure_STOPS_the_next_attempt_until_the_backoff_expires(self):
        # ⚠️ The point is not the log. Each attempt blocks the window poll for
        # the socket timeout, so a dead daemon used to stall the tick by ~3 s on
        # every focus change.
        health = RelayHealth(min_backoff=2.0)
        health.note(False, 0.0, "timed out")
        self.assertFalse(health.should_attempt(1.9))
        self.assertTrue(health.should_attempt(2.1))

    def test_the_FIRST_retry_waits_the_MINIMUM_not_double_it(self):
        # Doubling from the start means the shortest outage anyone notices
        # already costs 4 s before the first re-try.
        health = RelayHealth(min_backoff=2.0)
        health.note(False, 0.0, "timed out")
        self.assertTrue(health.should_attempt(2.0))

    def test_it_doubles_and_then_CAPS(self):
        health = RelayHealth(min_backoff=2.0, max_backoff=30.0)
        waits, now = [], 0.0
        for _ in range(8):
            health.note(False, now, "timed out")
            wait = next(w for w in (0.1 * i for i in range(1, 6000))
                        if health.should_attempt(now + w))
            waits.append(round(wait, 1))
            now += wait
        self.assertEqual(waits[:5], [2.0, 4.0, 8.0, 16.0, 30.0])
        self.assertLessEqual(max(waits), 30.0)

    def test_a_SUCCESS_clears_the_backoff_completely(self):
        health = RelayHealth()
        for t in (0.0, 5.0, 40.0):
            health.note(False, t, "timed out")
        health.note(True, 100.0)
        self.assertTrue(health.should_attempt(100.0))
        health.note(False, 100.0, "timed out")
        self.assertFalse(health.should_attempt(101.9))
        self.assertTrue(health.should_attempt(102.1))


class ResetTest(unittest.TestCase):

    def test_reset_makes_the_next_attempt_IMMEDIATE(self):
        # ⚠️ For a deliberate user action (un-pausing, a changed host). Making
        # someone who just pressed Resume wait out a 30 s timer is the wrong
        # answer to a question they already answered.
        health = RelayHealth()
        for t in (0.0, 5.0, 40.0, 100.0):
            health.note(False, t, "timed out")
        self.assertFalse(health.should_attempt(101.0))
        health.reset()
        self.assertTrue(health.should_attempt(101.0))

    def test_reset_forgets_the_OUTAGE_so_the_next_one_is_announced_afresh(self):
        # Without this the second failure reads as "still down" and says nothing,
        # so a user who paused, resumed and hit the same dead daemon would get
        # no line at all.
        health = RelayHealth()
        health.note(False, 0.0, "timed out")
        health.reset()
        self.assertEqual(health.note(False, 1.0, "timed out")[0], "error")
        self.assertEqual(health.note(True, 2.0)[0], "info")

    def test_reset_keeps_the_TUNING_it_was_built_with(self):
        health = RelayHealth(min_backoff=7.0, max_backoff=9.0, still_down_every=11.0)
        health.note(False, 0.0, "timed out")
        health.reset()
        self.assertEqual((health.min_backoff, health.max_backoff,
                          health.still_down_every), (7.0, 9.0, 11.0))


class WhatItSaysTest(unittest.TestCase):
    """216 identical ERROR lines in one field log is what this replaced."""

    def test_the_FIRST_failure_is_an_ERROR_and_the_rest_are_SILENT(self):
        health = RelayHealth()
        first = health.note(False, 0.0, "timed out")
        self.assertEqual(first[0], "error")
        self.assertIn("timed out", first[1])
        for t in (2.1, 6.2, 14.3, 30.4, 62.5):
            self.assertIsNone(health.note(False, t, "timed out"))

    def test_a_FIRST_success_is_not_announced_as_a_recovery(self):
        # Nothing has failed, so there is nothing to have recovered from.
        health = RelayHealth()
        self.assertIsNone(health.note(True, 0.0))

    def test_coming_back_says_so_ONCE_with_the_cost(self):
        health = RelayHealth()
        health.note(False, 0.0, "timed out")
        for t in (2.1, 6.2, 14.3):
            health.note(False, t, "timed out")
        verdict = health.note(True, 100.0)
        self.assertEqual(verdict[0], "info")
        self.assertIn("4 failed", verdict[1])
        self.assertIn("1m40s", verdict[1])
        self.assertIsNone(health.note(True, 200.0))

    def test_a_LONG_outage_still_gets_a_periodic_reminder(self):
        # One line at the start and silence for four hours reads as the
        # forwarder having stopped.
        health = RelayHealth(still_down_every=300.0)
        health.note(False, 0.0, "timed out")
        self.assertIsNone(health.tick(299.0))
        reminder = health.tick(301.0)
        self.assertEqual(reminder[0], "warning")
        self.assertIn("5m01s", reminder[1])
        self.assertIsNone(health.tick(302.0))
        self.assertEqual(health.tick(602.0)[0], "warning")

    def test_the_reminder_fires_on_SKIPPED_attempts_too(self):
        # ⚠️ Once the backoff is at its 30 s cap the caller mostly SKIPS, so a
        # reminder that only ran on real attempts would still fire — but at the
        # cap it is the skip path that is hit first, and this is what pins that
        # `tick()` is reachable from there.
        health = RelayHealth(still_down_every=300.0)
        health.note(False, 0.0, "timed out")
        self.assertFalse(health.should_attempt(1.0))
        self.assertIsNone(health.tick(1.0))
        self.assertIsNotNone(health.tick(400.0))

    def test_a_healthy_relay_is_SILENT_on_the_reminder_path(self):
        health = RelayHealth(still_down_every=1.0)
        health.note(True, 0.0)
        self.assertIsNone(health.tick(1000.0))

    def test_the_REASON_reaches_BOTH_lines_that_report_it(self):
        # A failure nobody can name is a failure nobody can fix. ⚠️ The reminder
        # is the half that needs the STORED reason — the first line builds its
        # text from the argument, so a mutation dropping `self.reason` escaped
        # until this covered `tick()` as well.
        health = RelayHealth(still_down_every=300.0)
        first = health.note(False, 0.0, "connection refused: nope")
        self.assertIn("connection refused: nope", first[1])
        self.assertIn("connection refused: nope", health.tick(301.0)[1])


class DurationTest(unittest.TestCase):

    def test_it_reads_as_a_duration_at_every_scale(self):
        self.assertEqual(duration(0), "0s")
        self.assertEqual(duration(42), "42s")
        self.assertEqual(duration(90), "1m30s")
        self.assertEqual(duration(3900), "1h05m")

    def test_a_negative_clock_step_does_not_print_nonsense(self):
        # `time.monotonic()` cannot go backwards, but the value is a subtraction
        # of two of them and this is a log line, not a calculation.
        self.assertEqual(duration(-5), "0s")


if __name__ == "__main__":
    unittest.main()
