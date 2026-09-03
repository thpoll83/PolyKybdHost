"""PolyCore surfaces a firmware crash line from the console read as ONE event."""
import unittest
from unittest.mock import MagicMock

from polyhost.services.crash_report import CrashScanner
from tests.core.poly_core_apply_test import make_core
from tests.services.crash_report_test import LINE


def _core_with_console(*chunks):
    core = make_core(connected=True)
    core._crash_scanner = CrashScanner()
    core.keeb.read_serial.return_value = ""
    core.keeb.get_console_output.side_effect = list(chunks)
    events = []
    core.subscribe(lambda name, payload: events.append((name, payload)))
    return core, events


class ConsoleCrashScanTest(unittest.TestCase):
    def test_a_crash_line_becomes_a_crash_detected_event_with_the_record(self):
        core, events = _core_with_console("boot\n   " + LINE + "\n")
        core._console_periodic(MagicMock())
        names = [n for n, _ in events]
        self.assertIn("console", names)
        self.assertIn("crash_detected", names)
        payload = dict(events)["crash_detected"]
        self.assertEqual(payload["kind"], "hardfault")
        self.assertEqual(payload["line"], LINE)

    def test_a_line_split_across_two_reads_fires_once_after_the_second(self):
        cut = len(LINE) // 2
        core, events = _core_with_console(LINE[:cut], LINE[cut:] + "\n", LINE + "\n")
        core._console_periodic(MagicMock())
        self.assertNotIn("crash_detected", [n for n, _ in events])
        core._console_periodic(MagicMock())
        self.assertEqual([n for n, _ in events].count("crash_detected"), 1)
        core._console_periodic(MagicMock())      # the banner re-emit is not a new crash
        self.assertEqual([n for n, _ in events].count("crash_detected"), 1)

    def test_nothing_on_the_console_emits_nothing(self):
        core, events = _core_with_console("")
        core._console_periodic(MagicMock())
        self.assertEqual(events, [])

    def test_clear_forgets_so_the_next_boot_line_is_reported_again(self):
        core, events = _core_with_console(LINE + "\n", LINE + "\n")
        core.worker.run_sync.return_value = (True, "ok")
        core._console_periodic(MagicMock())
        ok, _ = core.clear_crash_record()
        self.assertTrue(ok)
        core._console_periodic(MagicMock())
        self.assertEqual([n for n, _ in events].count("crash_detected"), 2)

    def test_get_crash_record_validates_the_half(self):
        core, _ = _core_with_console("")
        ok, msg = core.get_crash_record(2)
        self.assertFalse(ok)
        self.assertIn("Invalid half", msg)
        core.worker.run_sync.return_value = (True, None)
        self.assertEqual(core.get_crash_record(1), (True, None))


if __name__ == "__main__":
    unittest.main()
