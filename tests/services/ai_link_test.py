"""Tests for the agent status link: the console scanner and the window raiser.

The interesting cases are the ones that only show up on real hardware — a console
line split across two 250 ms reads, and a window list that changes between presses —
so both are driven directly rather than mocked away.
"""
import unittest

from polyhost.services.ai_link import (AiScanner, WindowRaiser, match_windows,
                                       next_index, PRESS_DEBOUNCE_S)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class AiScannerTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.scanner = AiScanner(now=self.clock)

    def test_a_whole_line_is_one_press(self):
        self.assertEqual(self.scanner.feed("ai: open\n"), 1)

    def test_a_line_split_across_reads_is_still_one_press(self):
        # A console read returns whatever fitted in one HID report, so the line
        # genuinely arrives in pieces. Matching the raw chunk would find neither half.
        self.assertEqual(self.scanner.feed("Split link: 400 tx\nai: op"), 0)
        self.assertEqual(self.scanner.feed("en\n"), 1)

    def test_an_unterminated_line_is_not_a_press_yet(self):
        self.assertEqual(self.scanner.feed("ai: open"), 0)

    def test_other_console_traffic_is_ignored(self):
        self.assertEqual(self.scanner.feed("crash: side=master kind=hardfault\n"), 0)

    def test_two_presses_both_count(self):
        # Unlike the crash scanner this must NOT dedupe by content: every press
        # prints the same text, and the second press is a real second press.
        self.assertEqual(self.scanner.feed("ai: open\n"), 1)
        self.clock.t += PRESS_DEBOUNCE_S * 2
        self.assertEqual(self.scanner.feed("ai: open\n"), 1)

    def test_a_repeated_fragment_within_the_debounce_counts_once(self):
        self.assertEqual(self.scanner.feed("ai: open\nai: open\n"), 1)

    def test_a_runaway_fragment_does_not_grow_without_bound(self):
        self.scanner.feed("x" * (AiScanner.MAX_PENDING * 3))
        self.assertLessEqual(len(self.scanner._pending), AiScanner.MAX_PENDING)


class MatchWindowsTest(unittest.TestCase):
    def test_substring_is_case_insensitive(self):
        got = match_windows(["Claude Code — repo", "Firefox"], "claude")
        self.assertEqual([m.title for m in got], ["Claude Code — repo"])

    def test_a_slashed_pattern_is_a_regex(self):
        got = match_windows(["agent-1", "agent-2", "notes"], "/agent-\\d/")
        self.assertEqual(len(got), 2)

    def test_a_broken_regex_matches_nothing_instead_of_raising(self):
        # A bad pattern is a typo in a setting, not a reason to lose the keypress.
        self.assertEqual(match_windows(["a"], "/[unclosed/"), [])

    def test_an_empty_pattern_matches_nothing(self):
        self.assertEqual(match_windows(["anything"], ""), [])

    def test_order_is_preserved(self):
        # Stable order is what makes "press again for the next one" advance rather
        # than shuffle.
        titles = [f"agent {i}" for i in range(5)]
        self.assertEqual([m.title for m in match_windows(titles, "agent")], titles)


class NextIndexTest(unittest.TestCase):
    def _m(self, *handles):
        return match_windows([(f"w{h}", h) for h in handles], "w")

    def test_first_press_takes_the_first_match(self):
        self.assertEqual(next_index(self._m("a", "b"), None), 0)

    def test_a_press_advances_past_the_last_raised_window(self):
        self.assertEqual(next_index(self._m("a", "b", "c"), "b"), 2)

    def test_it_wraps(self):
        self.assertEqual(next_index(self._m("a", "b"), "b"), 0)

    def test_a_closed_window_falls_back_to_the_first(self):
        # The cycle stores a HANDLE rather than an index precisely for this: with an
        # index, closing a window silently moves every later one under the cursor.
        self.assertEqual(next_index(self._m("a", "b"), "gone"), 0)

    def test_no_matches_reports_nothing_to_raise(self):
        self.assertEqual(next_index([], "a"), -1)


class WindowRaiserTest(unittest.TestCase):
    def setUp(self):
        self.windows = [("Claude Code — one", "h1"), ("Claude Code — two", "h2"),
                        ("Firefox", "h3")]
        self.raised = []
        self.raiser = WindowRaiser(lambda: list(self.windows),
                                   lambda h: (self.raised.append(h), True)[1])

    def test_it_cycles_through_the_matches(self):
        for expected in ("h1", "h2", "h1"):
            ok, _ = self.raiser.raise_next("claude")
            self.assertTrue(ok)
            self.assertEqual(self.raised[-1], expected)

    def test_no_target_says_so_rather_than_raising_something(self):
        ok, msg = self.raiser.raise_next("")
        self.assertFalse(ok)
        self.assertIn("target", msg)
        self.assertEqual(self.raised, [])

    def test_no_match_is_reported(self):
        ok, msg = self.raiser.raise_next("nothing here")
        self.assertFalse(ok)
        self.assertIn("No window matches", msg)

    def test_a_refused_activation_is_reported_not_swallowed(self):
        # Native Wayland cannot be driven this way; saying nothing would read as the
        # key being broken.
        raiser = WindowRaiser(lambda: list(self.windows), lambda h: False)
        ok, msg = raiser.raise_next("claude")
        self.assertFalse(ok)
        self.assertIn("refused", msg)

    def test_a_backend_that_cannot_list_is_reported_not_raised(self):
        def boom():
            raise RuntimeError("no display")
        ok, msg = WindowRaiser(boom, lambda h: True).raise_next("claude")
        self.assertFalse(ok)
        self.assertIn("no display", msg)

    def test_a_closed_window_between_presses_does_not_skip_the_survivor(self):
        self.raiser.raise_next("claude")            # raises h1
        self.windows = [("Claude Code — two", "h2")]
        ok, _ = self.raiser.raise_next("claude")
        self.assertTrue(ok)
        self.assertEqual(self.raised[-1], "h2")


if __name__ == "__main__":
    unittest.main()
