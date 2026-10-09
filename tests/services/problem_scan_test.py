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
SLAVE = "RPC FAILED id=3 after 10 tries: slave unresponsive"
RETRY_OK = ("oled_i2c: cmd write failed #1 (nack, flags=0x00, sda=1 scl=1, len=7, "
            "66 ms after the last good write) - retry ok")
RETRY_FAIL = ("oled_i2c: cmd write failed #2 (timeout, flags=0x00, sda=0 scl=1, len=7, "
              "12 ms after the last good write) - retry failed (timeout)")
STUCK = "oled_i2c: status display not responding: 3 writes in a row failed after a retry"
SPLIT_OK = "Split link: 1200 tx crc_err=0 nack=0 transport_fail=0 giveup=0 err=0.0%"
SPLIT_LOST = "Split link: 1200 tx crc_err=1 nack=0 transport_fail=2 giveup=3 err=0.4%"
EDEN = "Eden idle: core1 job for key 7 timed out - rendering on core0"


def core1_stall(n=1, at_ms=734512, report=1, relaunched=True):
    """One copy of multicore_exec.c's core1_stall_report() line."""
    outcome = "core1 relaunched" if relaunched else "core1 relaunch FAILED, overlays degraded until reboot"
    return ("WARNING core1 stalled: no answer for 512 ms (last cmd 0xcafe0004 arg 0x00410012, "
            f"counts 17/16, entered 1) - {outcome} (recovery {n} since boot at {at_ms} ms, "
            f"report {report}/3)")


CORE1_STALL_OK = core1_stall()
CORE1_STALL_FAILED = core1_stall(n=2, relaunched=False)


class ConsoleScannerTest(unittest.TestCase):
    def test_the_erase_wait_status_snapshot_is_not_a_problem(self):
        # Printed while the slave erases staging flash at the start of a
        # firmware update; the update went on to complete (2026-10-05).
        s = ps.ConsoleProblemScanner()
        found = s.feed("slave status (begin-pending): RPC FAILED \u2014 slave unresponsive\n")
        self.assertEqual(found, [])

    def test_a_status_snapshot_failing_at_another_point_still_counts(self):
        s = ps.ConsoleProblemScanner()
        found = s.feed("slave status (begin-ready): RPC FAILED \u2014 slave unresponsive\n")
        self.assertEqual([p.key for p in found], ["slave_unresponsive"])

    def test_an_error_line_is_reported_once(self):
        s = ps.ConsoleProblemScanner()
        found = s.feed(f"boot\n{SLAVE}\n")
        self.assertEqual([p.key for p in found], ["slave_unresponsive"])
        self.assertEqual(found[0].severity, ps.SEVERITY_ERROR)
        self.assertEqual(found[0].source, ps.SOURCE_KEYBOARD)
        self.assertEqual(found[0].line, SLAVE)
        self.assertEqual(s.feed(f"{SLAVE}\n{SLAVE}\n"), [])     # repeats only count
        self.assertEqual(s.problems()[0].count, 3)

    def test_a_line_split_across_reads_matches_after_the_second(self):
        s = ps.ConsoleProblemScanner()
        self.assertEqual(s.feed(SLAVE[:10]), [])
        self.assertEqual([p.key for p in s.feed(SLAVE[10:] + "\n")], ["slave_unresponsive"])

    # -- core1 stall recovery (multicore_exec.c, core1_stall_report) -----------
    def test_a_core1_stall_that_was_recovered_is_an_error(self):
        s = ps.ConsoleProblemScanner()
        found = s.feed(f"{CORE1_STALL_OK}\n")
        self.assertEqual([(p.key, p.severity) for p in found],
                         [("core1_stall", ps.SEVERITY_ERROR)])
        self.assertIn("restarted", found[0].summary)

    def test_a_core1_stall_whose_relaunch_failed_is_its_own_error(self):
        s = ps.ConsoleProblemScanner()
        found = s.feed(f"{CORE1_STALL_FAILED}\n")
        self.assertEqual([p.key for p in found], ["core1_stall_failed"])
        self.assertIn("did not restart", found[0].summary)

    def test_the_repeated_copies_of_one_recovery_count_once(self):
        now = [0.0]
        s = ps.ConsoleProblemScanner(clock=lambda: now[0])
        self.assertEqual(len(s.feed(f"{core1_stall(report=1)}\n")), 1)
        now[0] = 100.0   # past the update interval: a count change would publish
        self.assertEqual(s.feed(f"{core1_stall(report=2)}\n{core1_stall(report=3)}\n"), [])
        self.assertEqual(s.problems()[0].count, 1)

    def test_two_recoveries_count_twice(self):
        now = [0.0]
        s = ps.ConsoleProblemScanner(clock=lambda: now[0])
        s.feed(f"{core1_stall(n=1, at_ms=1000)}\n")
        now[0] = 100.0
        found = s.feed(f"{core1_stall(n=2, at_ms=90000)}\n")
        self.assertEqual([(p.key, p.count) for p in found], [("core1_stall", 2)])

    def test_the_same_number_after_a_reboot_is_a_new_recovery(self):
        # <n> restarts at 1 when the keyboard reboots; the uptime tells them apart.
        s = ps.ConsoleProblemScanner()
        s.feed(f"{core1_stall(n=1, at_ms=734512)}\n{core1_stall(n=1, at_ms=61200)}\n")
        self.assertEqual(s.problems()[0].count, 2)

    def test_the_fw_staging_relaunch_line_is_not_a_core1_stall(self):
        s = ps.ConsoleProblemScanner()
        found = s.feed("fw_staging: core1 relaunch timed out — RLE service down until reboot\n")
        self.assertEqual([p.key for p in found], ["core1_relaunch"])

    # -- the status OLED: one failure is a glitch, a burst is a fault ------------
    def test_one_oled_failure_is_a_warning_that_the_default_level_does_not_raise(self):
        s = ps.ConsoleProblemScanner()
        self.assertEqual(s.feed(f"{OLED}\n"), [])
        found = ps.ConsoleProblemScanner().feed(f"{OLED}\n", ps.LEVEL_ERRORS_AND_WARNINGS)
        self.assertEqual([(p.key, p.severity) for p in found],
                         [("oled_i2c", ps.SEVERITY_WARNING)])

    def test_three_oled_failures_within_a_minute_escalate_to_an_error(self):
        now = [0.0]
        s = ps.ConsoleProblemScanner(clock=lambda: now[0])
        self.assertEqual(s.feed(f"{OLED}\n"), [])
        now[0] = 30.0
        self.assertEqual(s.feed(f"{OLED}\n"), [])
        now[0] = 59.0
        found = s.feed(f"{OLED}\n")
        self.assertEqual([(p.key, p.severity, p.count) for p in found],
                         [("oled_i2c", ps.SEVERITY_ERROR, 3)])
        self.assertIn("keeps rejecting", found[0].summary)

    def test_oled_failures_spread_out_never_escalate(self):
        now = [0.0]
        s = ps.ConsoleProblemScanner(clock=lambda: now[0])
        for _ in range(5):
            self.assertEqual(s.feed(f"{OLED}\n"), [])
            now[0] += 61.0

    def test_an_oled_warning_already_shown_is_resent_as_an_error_when_it_escalates(self):
        now = [0.0]
        wide = ps.LEVEL_ERRORS_AND_WARNINGS
        s = ps.ConsoleProblemScanner(update_interval=600, clock=lambda: now[0])
        self.assertEqual([p.severity for p in s.feed(f"{OLED}\n", wide)], [ps.SEVERITY_WARNING])
        now[0] = 1.0
        self.assertEqual(s.feed(f"{OLED}\n", wide), [])          # inside the interval
        now[0] = 2.0
        found = s.feed(f"{OLED}\n", wide)                          # escalation skips it
        self.assertEqual([(p.severity, p.count) for p in found], [(ps.SEVERITY_ERROR, 3)])

    def test_the_stock_qmk_render_variants_all_match(self):
        for line in ("oled_render offset command failed", "oled_render data failed",
                     "oled_render90 data failed"):
            found = ps.ConsoleProblemScanner().feed(line + "\n", ps.LEVEL_ERRORS_AND_WARNINGS)
            self.assertEqual([p.key for p in found], ["oled_i2c"], line)

    def test_a_retried_oled_write_is_a_warning_until_it_keeps_happening(self):
        s = ps.ConsoleProblemScanner(clock=lambda: 0.0)
        found = ps.ConsoleProblemScanner().feed(RETRY_OK + "\n", ps.LEVEL_ERRORS_AND_WARNINGS)
        self.assertEqual([(p.key, p.severity) for p in found],
                         [("oled_i2c_retried", ps.SEVERITY_WARNING)])
        self.assertEqual(s.feed((RETRY_OK + "\n") * 9), [])
        found = s.feed(RETRY_OK + "\n")
        self.assertEqual([(p.key, p.severity, p.count) for p in found],
                         [("oled_i2c_retried", ps.SEVERITY_ERROR, 10)])

    def test_a_failed_retry_detail_line_is_not_a_retry_ok(self):
        s = ps.ConsoleProblemScanner()
        self.assertEqual(s.feed(RETRY_FAIL + "\n", ps.LEVEL_ERRORS_AND_WARNINGS), [])

    def test_a_stuck_status_display_is_an_error_at_once(self):
        found = ps.ConsoleProblemScanner().feed(STUCK + "\n")
        self.assertEqual([(p.key, p.severity) for p in found],
                         [("oled_i2c_stuck", ps.SEVERITY_ERROR)])

    def test_the_recovery_and_summary_lines_are_not_problems(self):
        s = ps.ConsoleProblemScanner()
        lines = ("oled_i2c: status display responding again after 4 failed write(s)\n"
                 "oled_i2c: 7 more failed write(s) not printed in the last 10 s (10 since boot)\n")
        self.assertEqual(s.feed(lines, ps.LEVEL_ERRORS_AND_WARNINGS), [])

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
            if p.escalate_after:
                # Escalation turns a warning into an error; an error has nowhere to go.
                self.assertEqual(p.severity, ps.SEVERITY_WARNING, p.id)
                self.assertGreater(p.escalate_window_s, 0, p.id)
                self.assertTrue(p.escalated_summary.endswith("."), p.id)

    def test_a_raised_count_is_resent_once_the_interval_has_passed(self):
        now = [100.0]
        s = ps.ConsoleProblemScanner(update_interval=10, clock=lambda: now[0])
        self.assertEqual([p.count for p in s.feed(f"{SLAVE}\n")], [1])
        now[0] = 105.0
        self.assertEqual(s.feed(f"{SLAVE}\n{SLAVE}\n"), [])       # inside the interval
        now[0] = 111.0
        found = s.feed(f"{SLAVE}\n")
        self.assertEqual([(p.key, p.count) for p in found], [("slave_unresponsive", 4)])
        self.assertEqual(s.feed(f"{SLAVE}\n"), [])                # interval restarts
        now[0] = 200.0
        self.assertEqual(s.feed("healthy\n"), [])                # no repeat, no update

    def test_a_narrowed_level_stops_warning_updates(self):
        now = [0.0]
        s = ps.ConsoleProblemScanner(update_interval=10, clock=lambda: now[0])
        wide = ps.LEVEL_ERRORS_AND_WARNINGS
        self.assertEqual([p.key for p in s.feed(EDEN + "\n", wide)], ["eden_core1_timeout"])
        now[0] = 20.0
        self.assertEqual(s.feed(EDEN + "\n", ps.LEVEL_ERRORS), [])
        self.assertEqual(s.problems()[0].count, 2)          # still counted
        now[0] = 40.0
        self.assertEqual([p.count for p in s.feed(EDEN + "\n", wide)], [3])

    def test_one_chunk_publishes_a_problem_once_with_its_total(self):
        s = ps.ConsoleProblemScanner(update_interval=0)
        found = s.feed(f"{SLAVE}\n{SLAVE}\n{SLAVE}\n")
        self.assertEqual([(p.key, p.count) for p in found], [("slave_unresponsive", 3)])

    def test_a_long_line_is_clipped(self):
        s = ps.ConsoleProblemScanner()
        found = s.feed(SLAVE + " " + "x" * 1000 + "\n")
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
