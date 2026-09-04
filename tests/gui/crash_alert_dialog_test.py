"""CrashAlertDialog — what Clear forgets, and what Dismiss does not.

The dialog is retained for the life of the tray and every record is appended to
it, so before Clear existed a crash from an hour ago rode along in the report
about the one that just happened (field, 2026-09-04: a test session left eight
records in every later report). Dismiss deliberately still only hides.

The interesting cases are the failure ones. Clearing has to reach BOTH the
host-side list and the keyboard's flash archive, and the two must not be able to
end up out of step -- so a device that refuses is still followed by dropping the
list here, and says so, rather than leaving records a keyboard no longer holds.

Runs under the offscreen Qt platform against the real widget: the thing worth
pinning is the wiring between the button, the confirmation and the callback, and
a mock of the dialog would agree with itself about all three.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from polyhost.gui import crash_alert_dialog as cad
    from polyhost.services import crash_report
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e


def setUpModule():
    """Pin the QApplication for the life of the module -- see macro_tab_test."""
    if _IMPORT_ERR is None:
        assert _APP is not None


MASTER = ("   crash: side=master kind=hardfault core=0 pc=0x10011104 lr=0x10023d87 "
          "sp=0x20040ac0 psr=0xa1000000 icsr=0x00400003 phase=2:0x0000 up=148556ms "
          "n=1 reason=0x21 fw=0.18.4")
SLAVE = ("   crash: side=slave kind=hardfault core=0 pc=0x10011190 lr=0x10011187 "
         "sp=0x2003d130 psr=0x01000000 icsr=0x00400003 phase=4:0x0077 up=18276ms "
         "n=1 reason=0x21 fw=0.18.4")


@unittest.skipIf(_IMPORT_ERR is not None, f"PyQt5/dialog unavailable: {_IMPORT_ERR}")
class CrashAlertClearTest(unittest.TestCase):
    def setUp(self):
        self._answer = QMessageBox.Yes
        self._orig_question = cad.QMessageBox.question
        cad.QMessageBox.question = staticmethod(lambda *a, **k: self._answer)
        self.addCleanup(self._restore)
        self.records = [crash_report.parse_crash_line(MASTER),
                        crash_report.parse_crash_line(SLAVE)]
        self.assertTrue(all(self.records), "fixture lines must parse")

    def _restore(self):
        cad.QMessageBox.question = self._orig_question

    def _dialog(self, clear_cb=None):
        d = cad.CrashAlertDialog(clear_cb=clear_cb, host_version="0.0.0")
        self.addCleanup(d.deleteLater)
        for r in self.records:
            d.add_record(r)
        return d

    def test_clear_forgets_here_and_on_the_keyboard(self):
        calls = []
        d = self._dialog(clear_cb=lambda: (calls.append(1), (True, "ok"))[1])
        self.assertEqual(len(d.records), 2)
        d.clear_btn.click()
        self.assertEqual(calls, [1], "the keyboard's archive must be erased too")
        self.assertEqual(d.records, [])
        self.assertFalse(d.isVisible())

    def test_a_device_that_refuses_still_drops_the_local_list_and_says_so(self):
        # Leaving the list because the keyboard was unreachable (paused, mid-flash)
        # is exactly the complaint: stale records in every later report.
        d = self._dialog(clear_cb=lambda: (False, "suspended"))
        d.clear_btn.click()
        self.assertEqual(d.records, [])
        self.assertIn("suspended", d.status.text())

    def test_a_raising_device_call_does_not_strand_the_dialog(self):
        def boom():
            raise RuntimeError("no device")
        d = self._dialog(clear_cb=boom)
        d.clear_btn.click()
        self.assertEqual(d.records, [])
        self.assertIn("no device", d.status.text())

    def test_declining_the_confirmation_changes_nothing(self):
        calls = []
        self._answer = QMessageBox.No
        d = self._dialog(clear_cb=lambda: (calls.append(1), (True, "ok"))[1])
        d.clear_btn.click()
        self.assertEqual(calls, [], "the archive must not be erased on a decline")
        self.assertEqual(len(d.records), 2)

    def test_no_button_without_a_device_to_clear(self):
        # Clearing the host's list while the keyboard still held the record would
        # put the two out of step, which is the state the button exists to prevent.
        d = self._dialog(clear_cb=None)
        self.assertFalse(hasattr(d, "clear_btn"))

    def test_dismiss_hides_but_keeps_the_records(self):
        # Pinned deliberately: Dismiss is "not now", Clear is "forget". The dialog
        # docstring used to claim dismissing kept nothing, which was never true.
        d = self._dialog(clear_cb=lambda: (True, "ok"))
        d.reject()
        self.assertEqual(len(d.records), 2)

    def test_a_repeated_record_is_not_appended_twice(self):
        d = self._dialog(clear_cb=lambda: (True, "ok"))
        d.add_record(crash_report.parse_crash_line(MASTER))
        self.assertEqual(len(d.records), 2)


if __name__ == "__main__":
    unittest.main()
