"""PolyCore turns a known-bad console line into ONE problem_detected event."""
import unittest
from unittest.mock import MagicMock

from polyhost.services import problem_scan
from tests.core.poly_core_apply_test import make_core

OLED = "oled_render offset command failed"
# An error at once; the stock OLED line above is a warning until it repeats.
STUCK = "oled_i2c: status display not responding: 3 writes in a row failed after a retry"


def _core_with_console(*chunks, settings=None):
    core = make_core(connected=True)
    core._crash_scanner = MagicMock()
    core._crash_scanner.feed.return_value = []
    core._problem_scanner = problem_scan.ConsoleProblemScanner()
    values = {"problem_scan_keyboard_console": True, "problem_scan_host_logs": True,
              "problem_scan_level": "errors", **(settings or {})}
    core.poly_settings = MagicMock()
    core.poly_settings.get.side_effect = values.__getitem__
    core.keeb.read_serial.return_value = ""
    core.keeb.get_console_output.side_effect = list(chunks)
    events = []
    core.subscribe(lambda name, payload: events.append((name, payload)))
    return core, events


class ConsoleProblemScanTest(unittest.TestCase):
    def test_an_error_line_becomes_one_event(self):
        core, events = _core_with_console(f"x\n{STUCK}\n", f"{STUCK}\n")
        core._console_periodic(MagicMock())
        core._console_periodic(MagicMock())
        problems = [p for n, p in events if n == "problem_detected"]
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["key"], "oled_i2c_stuck")
        self.assertEqual(problems[0]["source"], "keyboard")

    def test_one_oled_failure_raises_nothing_and_a_burst_raises_an_error(self):
        core, events = _core_with_console(f"{OLED}\n", f"{OLED}\n{OLED}\n")
        core._console_periodic(MagicMock())
        self.assertNotIn("problem_detected", [n for n, _ in events])
        core._console_periodic(MagicMock())
        problems = [p for n, p in events if n == "problem_detected"]
        self.assertEqual([(p["key"], p["severity"], p["count"]) for p in problems],
                         [("oled_i2c", "error", 3)])

    def test_the_switch_turns_the_console_source_off(self):
        core, events = _core_with_console(
            f"{STUCK}\n", settings={"problem_scan_keyboard_console": False})
        core._console_periodic(MagicMock())
        self.assertNotIn("problem_detected", [n for n, _ in events])

    def test_warnings_follow_the_level_setting(self):
        line = "Split link: 9 tx crc_err=0 nack=0 transport_fail=1 giveup=2 err=0.1%\n"
        core, events = _core_with_console(line)
        core._console_periodic(MagicMock())
        self.assertNotIn("problem_detected", [n for n, _ in events])
        core, events = _core_with_console(
            line, settings={"problem_scan_level": "errors_and_warnings"})
        core._console_periodic(MagicMock())
        self.assertIn("problem_detected", [n for n, _ in events])

    def test_a_core_built_without_the_scanner_still_reads_the_console(self):
        core, events = _core_with_console(f"{OLED}\n")
        del core._problem_scanner
        core._console_periodic(MagicMock())
        self.assertEqual([n for n, _ in events], ["console"])


if __name__ == "__main__":
    unittest.main()
