"""The problem scan: which console lines and log records count, and how often.

The scanner exists for lines like ``oled_render offset command failed`` that a
user never sees. The failure that would make it useless is the opposite one, a
pattern that fires on a healthy board, so the healthy split-link stats line is
pinned here as a non-match.
"""
import logging
import unittest

from polyhost.services import problem_scan as ps

OLED = "oled_render offset command failed"
SPLIT_OK = "Split link: 1200 tx crc_err=0 nack=0 transport_fail=0 giveup=0 err=0.0%"
SPLIT_LOST = "Split link: 1200 tx crc_err=1 nack=0 transport_fail=2 giveup=3 err=0.4%"
EDEN = "Eden idle: core1 job for key 7 timed out - rendering on core0"


class ConsoleScannerTest(unittest.TestCase):
    def test_the_oled_i2c_line_is_an_error_reported_once(self):
        s = ps.ConsoleProblemScanner()
        found = s.feed(f"boot\n{OLED}\n")
        self.assertEqual([p.key for p in found], ["oled_i2c"])
        self.assertEqual(found[0].severity, ps.SEVERITY_ERROR)
        self.assertEqual(found[0].source, ps.SOURCE_KEYBOARD)
        self.assertEqual(found[0].line, OLED)
        self.assertEqual(s.feed(f"{OLED}\n{OLED}\n"), [])     # repeats only count
        self.assertEqual(s.problems()[0].count, 3)

    def test_a_line_split_across_reads_matches_after_the_second(self):
        s = ps.ConsoleProblemScanner()
        self.assertEqual(s.feed(OLED[:10]), [])
        self.assertEqual([p.key for p in s.feed(OLED[10:] + "\n")], ["oled_i2c"])

    def test_healthy_split_link_stats_are_not_a_problem(self):
        s = ps.ConsoleProblemScanner()
        self.assertEqual(s.feed(SPLIT_OK + "\n", ps.LEVEL_ERRORS_AND_WARNINGS), [])

    def test_warnings_need_the_wider_level(self):
        s = ps.ConsoleProblemScanner()
        self.assertEqual(s.feed(f"{SPLIT_LOST}\n{EDEN}\n"), [])
        found = s.feed(f"{SPLIT_LOST}\n{EDEN}\n", ps.LEVEL_ERRORS_AND_WARNINGS)
        self.assertEqual(sorted(p.key for p in found),
                         ["eden_core1_timeout", "split_link_giveup"])
        self.assertTrue(all(p.severity == ps.SEVERITY_WARNING for p in found))

    def test_a_crash_line_is_left_to_the_crash_scanner(self):
        s = ps.ConsoleProblemScanner()
        line = ("crash: side=master kind=hardfault core=0 pc=0x1 lr=0x1 sp=0x1 psr=0x1 "
                "icsr=0x1 phase=2:0x0 up=1ms n=1 reason=0x1 fw=1.4.1")
        self.assertEqual(s.feed(line + "\n", ps.LEVEL_ERRORS_AND_WARNINGS), [])

    def test_every_pattern_has_a_known_severity_and_a_sentence(self):
        ids = [p.id for p in ps.CONSOLE_PATTERNS]
        self.assertEqual(len(ids), len(set(ids)))
        for p in ps.CONSOLE_PATTERNS:
            self.assertIn(p.severity, (ps.SEVERITY_ERROR, ps.SEVERITY_WARNING), p.id)
            self.assertTrue(p.summary.endswith("."), p.id)

    def test_a_raised_count_is_resent_once_the_interval_has_passed(self):
        now = [100.0]
        s = ps.ConsoleProblemScanner(update_interval=10, clock=lambda: now[0])
        self.assertEqual([p.count for p in s.feed(f"{OLED}\n")], [1])
        now[0] = 105.0
        self.assertEqual(s.feed(f"{OLED}\n{OLED}\n"), [])       # inside the interval
        now[0] = 111.0
        found = s.feed(f"{OLED}\n")
        self.assertEqual([(p.key, p.count) for p in found], [("oled_i2c", 4)])
        self.assertEqual(s.feed(f"{OLED}\n"), [])                # interval restarts
        now[0] = 200.0
        self.assertEqual(s.feed("healthy\n"), [])                # no repeat, no update

    def test_one_chunk_publishes_a_problem_once_with_its_total(self):
        s = ps.ConsoleProblemScanner(update_interval=0)
        found = s.feed(f"{OLED}\n{OLED}\n{OLED}\n")
        self.assertEqual([(p.key, p.count) for p in found], [("oled_i2c", 3)])

    def test_a_long_line_is_clipped(self):
        s = ps.ConsoleProblemScanner()
        found = s.feed(OLED + " " + "x" * 1000 + "\n")
        self.assertLessEqual(len(found[0].line), ps.MAX_LINE)


class HostLogHandlerTest(unittest.TestCase):
    def setUp(self):
        self.got = []
        self.level = ps.LEVEL_ERRORS
        self.enabled = True
        self.handler = ps.HostLogProblemHandler(
            self.got.append, level_cb=lambda: self.level,
            enabled_cb=lambda: self.enabled, origin="tray")
        self.log = logging.getLogger("problem_scan_test")
        self.log.propagate = False
        self.log.setLevel(logging.DEBUG)
        self.log.addHandler(self.handler)

    def tearDown(self):
        self.log.removeHandler(self.handler)

    def test_an_error_is_reported_once_per_call_site(self):
        self.log.error("could not open %s", "a")
        self.log.error("could not open %s", "b")
        self.assertEqual(len(self.got), 1)
        self.assertEqual(self.got[0].severity, ps.SEVERITY_ERROR)
        self.assertEqual(self.got[0].line, "could not open a")
        self.assertEqual(self.got[0].count, 2)
        self.assertIn("tray", self.got[0].summary)

    def test_a_repeat_is_resent_with_its_count_after_the_interval(self):
        now = [0.0]
        self.handler._clock = lambda: now[0]
        self.handler._update_interval = 10
        self.log.error("could not open %s", "a")
        now[0] = 5.0
        self.log.error("could not open %s", "b")
        self.assertEqual(len(self.got), 1)
        now[0] = 10.0
        self.log.error("could not open %s", "c")
        self.assertEqual(len(self.got), 2)
        self.assertIs(self.got[1], self.got[0])     # an update of the same problem
        self.assertEqual(self.got[1].count, 3)
        self.assertEqual(self.got[1].line, "could not open a")

    def test_warnings_only_at_the_wider_level(self):
        self.log.warning("slow")
        self.assertEqual(self.got, [])
        self.level = ps.LEVEL_ERRORS_AND_WARNINGS
        self.log.warning("slow")
        self.assertEqual([p.severity for p in self.got], [ps.SEVERITY_WARNING])

    def test_the_switch_turns_it_off(self):
        self.enabled = False
        self.log.error("boom")
        self.assertEqual(self.got, [])

    def test_info_never_counts(self):
        self.level = ps.LEVEL_ERRORS_AND_WARNINGS
        self.log.info("fine")
        self.assertEqual(self.got, [])

    def test_the_relayed_console_logger_is_ignored(self):
        console = logging.getLogger("PolyKybdConsole")
        console.addHandler(self.handler)
        try:
            console.error("relayed text")
        finally:
            console.removeHandler(self.handler)
        self.assertEqual(self.got, [])

    def test_a_record_logged_by_the_callback_cannot_feed_itself(self):
        def noisy(prob):
            self.got.append(prob)
            self.log.error("observer failed")   # what Observable.emit does on a failure
        self.handler._on_problem = noisy
        self.log.error("first")
        self.assertEqual([p.line for p in self.got], ["first"])

    def test_a_raising_callback_never_raises_into_the_logger(self):
        def broken(prob):
            raise RuntimeError("nope")
        self.handler._on_problem = broken
        self.log.error("still fine")   # must not raise


class PayloadAndReportTest(unittest.TestCase):
    def test_round_trip_keeps_extra_fields(self):
        p = ps.Problem(ps.SOURCE_HOST, "k", ps.SEVERITY_ERROR, "s.", "line", 2,
                       extra={"logger": "PolyHost"})
        back = ps.Problem.from_dict(p.to_dict())
        self.assertEqual(back.to_dict(), p.to_dict())

    def test_report_text_lists_every_problem_and_titles_the_first(self):
        a = ps.Problem(ps.SOURCE_KEYBOARD, "oled_i2c", ps.SEVERITY_ERROR,
                       "The status display did not accept an update.", OLED, 3)
        b = ps.Problem(ps.SOURCE_HOST, "x", ps.SEVERITY_WARNING, "W.", "slow")
        description, title = ps.compose_report_text([a, b])
        self.assertIn(OLED, description)
        self.assertIn("seen 3×", description)
        self.assertIn("[Host, warning]", description)
        self.assertEqual(title, "The status display did not accept an update. (+1 more)")


if __name__ == "__main__":
    unittest.main()
