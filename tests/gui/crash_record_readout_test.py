"""Help & About > "Read keyboard crash record" (PolyHost.read_crash_records).

The crash alert fires only for a FRESH record that reaches the host. This entry
reads both halves over cmd 39 on demand, shows them in the shared crash dialog
and copies the report text, so a record the alert missed can still be handed on.
Driven against a stub host: the method only needs `core` and `_crash_dialog`.
"""
import os
import types
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost import host
    from polyhost.gui.crash_alert_dialog import CrashAlertDialog
    from polyhost.services import crash_report
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e


def setUpModule():
    """Pin the QApplication for the module -- see split_link_dialog_test."""
    if _IMPORT_ERR is None:
        assert _APP is not None


LINE = ("crash: side=master kind=watchdog core=0 pc=0x00000000 lr=0x00000000 "
        "sp=0x00000000 psr=0x00000000 icsr=0x00000000 phase=1:0x16e1 up=0ms "
        "n=1 reason=0x11 fw=1.3.2")


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class ReadCrashRecordsTest(unittest.TestCase):
    def setUp(self):
        self.replies = {0: (True, None), 1: (True, None)}
        core = mock.MagicMock()
        core.get_crash_record.side_effect = lambda w: self.replies[w]
        self.dialog = CrashAlertDialog(host_version="0.0.0")
        self.addCleanup(self.dialog.deleteLater)
        self.stub = types.SimpleNamespace(core=core, _crash_dialog=lambda: self.dialog)
        QApplication.clipboard().setText("")
        self.info = mock.patch.object(host.QMessageBox, "information").start()
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(host, "bring_to_front").start()

    def _run(self):
        host.PolyHost.read_crash_records(self.stub)

    def _record(self, side="master", fresh=False):
        rec = crash_report.parse_crash_line(LINE)
        return dict(rec.to_dict(), side=side, line="", fresh=fresh)

    def test_an_older_record_is_shown_and_copied(self):
        self.replies[0] = (True, self._record())
        self._run()
        self.assertEqual(len(self.dialog.records), 1)
        self.assertTrue(self.dialog.isVisible())
        text = QApplication.clipboard().text()
        self.assertIn("phase=1:0x16e1", text)
        self.assertIn("archived (older)", text)
        self.info.assert_not_called()

    def test_both_halves_are_read(self):
        self.replies[0] = (True, self._record())
        self.replies[1] = (True, self._record(side="slave"))
        self._run()
        self.assertEqual({r.side for r in self.dialog.records}, {"master", "slave"})

    def test_no_record_says_so_and_copies_nothing(self):
        self._run()
        self.info.assert_called_once()
        self.assertIn("Neither keyboard half", self.info.call_args[0][2])
        self.assertEqual(QApplication.clipboard().text(), "")
        self.assertFalse(self.dialog.isVisible())

    def test_a_failed_read_is_reported_not_raised(self):
        self.replies[0] = (False, "Firmware protocol too old")
        self.stub.core.get_crash_record.side_effect = [
            (False, "Firmware protocol too old"), RuntimeError("rpc gone")]
        self._run()
        msg = self.info.call_args[0][2]
        self.assertIn("master: Firmware protocol too old", msg)
        self.assertIn("slave: RuntimeError: rpc gone", msg)

    def test_one_half_failing_still_shows_the_other(self):
        self.replies[0] = (True, self._record())
        self.replies[1] = (False, "timed out")
        self._run()
        self.assertEqual(len(self.dialog.records), 1)
        self.assertIn("Not read: slave: timed out", self.dialog.status.text())


if __name__ == "__main__":
    unittest.main()
