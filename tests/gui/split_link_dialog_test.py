"""The .uf2 recovery hand-off from a failed firmware update (gui/split_link_dialog.py)."""
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.device.split_link import split_link_timeout_message
    from polyhost.gui import split_link_dialog
    from polyhost.gui.hid_fw_up_dialog import HidFwUpDialog
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class SplitLinkHandOffTest(unittest.TestCase):

    def setUp(self):
        split_link_dialog._instance = None
        self.addCleanup(setattr, split_link_dialog, "_instance", None)

    def _dlg(self):
        dlg = HidFwUpDialog(None, "fw.bin", external=True, apply_after=True)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_a_split_link_failure_hands_over_to_the_help(self):
        msg = split_link_timeout_message("FW_UP_BEGIN timed out", "staging area")
        dlg = self._dlg()
        with mock.patch("PyQt5.QtCore.QTimer.singleShot") as later:
            dlg.feed_finished(False, msg)
        self.assertTrue(dlg._done)
        self.assertEqual(dlg.result(), dlg.Rejected)
        # Deferred, not opened inline: this runs from a bridge event.
        (delay, fn), _ = later.call_args
        self.assertEqual(delay, 0)
        help_dlg = fn()
        self.addCleanup(help_dlg.close)
        self.assertIs(help_dlg, split_link_dialog._instance)
        self.assertEqual(help_dlg._detail.text(), msg)

    def test_any_other_failure_keeps_the_close_button(self):
        dlg = self._dlg()
        with mock.patch("PyQt5.QtCore.QTimer.singleShot"):
            dlg.feed_finished(False, "FW_UP_BEGIN timed out — keyboard did not finish erasing")
        self.assertEqual(dlg._cancel_btn.text(), "Close")
        self.assertIsNone(split_link_dialog._instance)

    def test_a_second_failure_reuses_the_open_help(self):
        a = split_link_dialog.show_split_link_help("first")
        self.addCleanup(a.close)
        b = split_link_dialog.show_split_link_help("second")
        self.assertIs(a, b)
        self.assertEqual(b._detail.text(), "second")

    def test_download_result_lands_in_the_dialog(self):
        d = split_link_dialog.show_split_link_help("x")
        self.addCleanup(d.close)
        d._on_downloaded(True, "", "/tmp/p.uf2", "https://example.com/r")
        self.assertIn("/tmp/p.uf2", d._status.text())
        self.assertFalse(d._reveal_btn.isHidden())
        d._on_downloaded(False, "boom", "", "https://example.com/r")
        self.assertIn("https://example.com/r", d._status.text())


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class FontPackHookTest(unittest.TestCase):
    """PolyHost._maybe_show_split_link_help: auto-open once per session."""

    def _call(self, host, result):
        from polyhost.host import PolyHost
        with mock.patch("polyhost.host.QTimer.singleShot") as later:
            PolyHost._maybe_show_split_link_help(host, result)
        return later

    def _host(self):
        return mock.Mock(_split_link_help_shown=False)

    def test_opens_once_for_a_dead_link(self):
        host = self._host()
        result = {"ok": False, "msg": "Failed: symbol.", "split_link_down": True}
        self.assertEqual(self._call(host, result).call_count, 1)
        self.assertTrue(host._split_link_help_shown)
        self.assertEqual(self._call(host, result).call_count, 0)

    def test_a_single_flash_is_recognised_by_its_message(self):
        msg = split_link_timeout_message("BEGIN timed out", "font pack region")
        self.assertEqual(self._call(self._host(), {"ok": False, "msg": msg}).call_count, 1)

    def test_other_failures_do_not_open_it(self):
        host = self._host()
        self.assertEqual(self._call(host, {"ok": False, "msg": "Failed: symbol.",
                                           "split_link_down": False}).call_count, 0)
        self.assertFalse(host._split_link_help_shown)


if __name__ == "__main__":
    unittest.main()
