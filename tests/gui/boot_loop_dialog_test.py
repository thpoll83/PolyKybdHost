"""BootLoopDialog: starts and stops the core's loop and shows what it reports.

The loop itself is tested in tests/core/boot_loop_test.py against the emulated
keyboard; this pins the widget's wiring under the offscreen platform.
"""
import os
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.boot_loop_dialog import BootLoopDialog
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e


def setUpModule():
    """Pin the QApplication for the module -- see split_link_dialog_test."""
    if _IMPORT_ERR is None:
        assert _APP is not None


RECORD = {
    "side": "master", "kind": "watchdog", "core": 0, "pc": 0, "lr": 0, "sp": 0,
    "xpsr": 0, "icsr": 0, "phase": 1, "phase_arg": 0x16E1, "uptime_ms": 0,
    "consecutive": 1, "reset_reason": 0x11, "fw": "1.3.2", "line": "", "fresh": True,
}


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class BootLoopDialogTest(unittest.TestCase):
    def setUp(self):
        self.core = mock.MagicMock()
        self.core.start_boot_loop.return_value = (True, {"rounds": 50})
        self.core.cancel_boot_loop.return_value = (True, "cancelling")
        self.d = BootLoopDialog(self.core)
        self.addCleanup(self.d.deleteLater)

    def test_start_passes_the_round_count_and_locks_the_controls(self):
        self.d.rounds.setValue(7)
        self.d.start_btn.click()
        self.core.start_boot_loop.assert_called_once_with(7)
        self.assertFalse(self.d.start_btn.isEnabled())
        self.assertTrue(self.d.cancel_btn.isEnabled())

    def test_the_default_and_the_limit_are_50(self):
        self.assertEqual(self.d.rounds.value(), 50)
        self.assertEqual(self.d.rounds.maximum(), 50)

    def test_a_refused_start_says_why_and_stays_idle(self):
        self.core.start_boot_loop.return_value = (False, "need v22+")
        self.d.start_btn.click()
        self.assertIn("need v22+", self.d.verdict.text())
        self.assertTrue(self.d.start_btn.isEnabled())

    def test_a_raising_core_does_not_escape_the_slot(self):
        self.core.start_boot_loop.side_effect = RuntimeError("rpc gone")
        self.d.start_btn.click()
        self.assertIn("rpc gone", self.d.verdict.text())

    def test_stop_cancels(self):
        self.d.start_btn.click()
        self.d.cancel_btn.click()
        self.core.cancel_boot_loop.assert_called_once()

    def test_progress_and_a_found_crash_are_shown(self):
        self.d.start_btn.click()
        self.d.feed_progress({"round": 3, "rounds": 50, "msg": "clean boot in 4.2 s"})
        self.d.feed_done({"ok": False, "result": "crash", "msg": "Round 4: a boot problem",
                          "rounds_done": 4, "boot_times": [], "record": RECORD})
        text = self.d.output.toPlainText()
        self.assertIn("[3/50] clean boot in 4.2 s", text)
        self.assertIn("phase=1:0x16e1", text)
        self.assertIn("A boot problem was recorded", self.d.verdict.text())
        self.assertTrue(self.d.start_btn.isEnabled())

    def test_copy_takes_the_log_and_the_verdict(self):
        self.d.feed_done({"ok": True, "result": "clean", "msg": "2 reboot(s), no boot problem.",
                          "rounds_done": 2, "boot_times": [3.0, 3.1], "record": None})
        self.d.copy_btn.click()
        text = QApplication.clipboard().text()
        self.assertIn("no boot problem", text)
        self.assertIn("No boot problem found", text)


if __name__ == "__main__":
    unittest.main()
