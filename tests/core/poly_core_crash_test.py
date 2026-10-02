"""PolyCore surfaces a firmware crash line from the console read as ONE event."""
import unittest
from unittest.mock import MagicMock, patch

from polyhost.services.crash_report import CrashScanner, parse_crash_line
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

    def test_a_refused_clear_does_not_forget(self):
        core, events = _core_with_console(LINE + "\n", LINE + "\n")
        core.worker.run_sync.return_value = (False, "refused")
        core._console_periodic(MagicMock())
        ok, _ = core.clear_crash_record()
        self.assertFalse(ok)
        core._console_periodic(MagicMock())
        self.assertEqual([n for n, _ in events].count("crash_detected"), 1)

    def test_get_crash_record_validates_the_half(self):
        core, _ = _core_with_console("")
        ok, msg = core.get_crash_record(2)
        self.assertFalse(ok)
        self.assertIn("Invalid half", msg)
        core.worker.run_sync.return_value = (True, None)
        self.assertEqual(core.get_crash_record(1), (True, None))



def _hid(fresh=True, side="master", line=""):
    d = dict(parse_crash_line(LINE).to_dict(), line=line, fresh=fresh, side=side)
    return d


class ConnectTimeCrashReadTest(unittest.TestCase):
    """The console line is lossy; a fresh connect asks the keyboard over cmd 39."""

    def setUp(self):
        self.core, self.events = _core_with_console("")
        self.replies = {0: (True, None), 1: (True, None)}
        self.reads = []

        def get(which):
            self.reads.append(which)
            return self.replies[which]
        self.core.keeb.get_crash_record.side_effect = get
        self.clock = [1000.0]
        patcher = patch("polyhost.core.poly_core.time.monotonic",
                        side_effect=lambda: self.clock[0])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _tick(self, at=None):
        if at is not None:
            self.clock[0] = 1000.0 + at
        self.core._crash_autocheck_periodic(MagicMock(is_set=lambda: False))

    def _crashes(self):
        return [p for n, p in self.events if n == "crash_detected"]

    def test_nothing_is_read_until_armed(self):
        self._tick()
        self.assertEqual(self.reads, [])

    def test_a_fresh_master_record_alerts_once(self):
        self.replies[0] = (True, _hid())
        self.core._arm_crash_autocheck()
        self._tick()
        self.assertEqual(self.reads, [0, 1])
        self.assertEqual(len(self._crashes()), 1)
        self.assertEqual(self._crashes()[0]["side"], "master")

    def test_an_archived_record_does_not_alert(self):
        self.replies[0] = (True, _hid(fresh=False))
        self.core._arm_crash_autocheck()
        self._tick()
        self.assertEqual(self._crashes(), [])

    def test_the_slave_is_asked_again_until_its_record_arrives(self):
        self.core._arm_crash_autocheck()
        self._tick(0)
        self._tick(5)
        self.assertEqual(self.reads, [0, 1])
        self.replies[1] = (True, _hid(side="slave"))
        self._tick(8)
        self.assertEqual(self.reads, [0, 1, 1])
        self.assertEqual([p["side"] for p in self._crashes()], ["slave"])
        self._tick(25)              # found: the 20 s re-check is dropped
        self.assertEqual(self.reads, [0, 1, 1])

    def test_the_banner_line_after_a_hid_read_does_not_alert_again(self):
        self.replies[0] = (True, _hid())
        self.core._arm_crash_autocheck()
        self._tick()
        self.core.keeb.get_console_output.side_effect = ["   " + LINE + "\n"]
        self.core._console_periodic(MagicMock())
        self.assertEqual(len(self._crashes()), 1)

    def test_a_record_the_console_already_reported_does_not_alert_again(self):
        self.core.keeb.get_console_output.side_effect = [LINE + "\n"]
        self.core._console_periodic(MagicMock())
        self.replies[0] = (True, _hid())
        self.core._arm_crash_autocheck()
        self._tick()
        self.assertEqual(len(self._crashes()), 1)

    def test_a_disconnect_defers_the_reads_instead_of_dropping_them(self):
        # No new boot marker will re-arm them, so a flap must not throw them away.
        self.replies[0] = (True, _hid())
        self.core._arm_crash_autocheck()
        self.core.connected = False
        self._tick()
        self.assertEqual(self.reads, [])
        self.core.connected = True
        self._tick(1)
        self.assertEqual(self.reads, [0, 1])
        self.assertEqual(len(self._crashes()), 1)

    def test_a_failed_master_read_is_retried(self):
        # Right after a boot the keyboard can be deaf after a large overlay
        # transfer; one timeout used to lose the crash for good.
        self.replies[0] = (False, "timed out")
        self.core._arm_crash_autocheck()
        self._tick(0)
        self.replies[0] = (True, _hid())
        self._tick(4)
        self.assertEqual([w for w in self.reads if w == 0], [0, 0])
        self.assertEqual([p["side"] for p in self._crashes()], ["master"])
        self._tick(10)              # answered: the 10 s re-check is dropped
        self.assertEqual([w for w in self.reads if w == 0], [0, 0])

    def test_an_empty_master_answer_ends_its_checks(self):
        self.core._arm_crash_autocheck()
        self._tick(0)
        self._tick(30)
        self.assertEqual([w for w in self.reads if w == 0], [0])

    def test_a_cancel_mid_tick_keeps_the_unread_half(self):
        self.core._arm_crash_autocheck()
        calls = iter([False, True, True, True])
        self.core._crash_autocheck_periodic(MagicMock(is_set=lambda: next(calls)))
        self.assertEqual(self.reads, [0])
        self._tick()
        self.assertEqual(self.reads, [0, 1])

    def test_a_failed_or_raising_read_is_quiet(self):
        self.replies[0] = (False, "refused")
        self.core.keeb.get_crash_record.side_effect = [
            (False, "refused"), RuntimeError("hid gone")]
        self.core._arm_crash_autocheck()
        self._tick()
        self.assertEqual(self._crashes(), [])


if __name__ == "__main__":
    unittest.main()
