"""The shell title integration dialog (gui/shell_title_dialog.py): rows from
the service's status, Install/Remove on the ticked shells, results shown."""
import os
import time
import unittest
import unittest.mock as mock
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui import shell_title_dialog as std
    from polyhost.services import shell_title as st
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e


def _statuses():
    return [
        st.ShellStatus(st.BASH, st.STATE_NOT_INSTALLED, Path("/h/.bashrc"), ""),
        st.ShellStatus(st.ZSH, st.STATE_INSTALLED, Path("/h/.zshrc"), ""),
        st.ShellStatus(st.PWSH, st.STATE_STALE, Path("/h/profile.ps1"), "/old/polykybd-title.ps1"),
        st.ShellStatus(st.POWERSHELL, st.STATE_NOT_PRESENT, None, ""),
        st.ShellStatus(st.FISH, st.STATE_NO_SETUP, None, ""),
    ]


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class ShellTitleDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make(self, statuses=None, results=None):
        self.calls = []
        statuses = _statuses() if statuses is None else statuses

        def status_fn():
            return statuses

        def install_fn(shells, statuses=None):
            self.calls.append(("install", shells, statuses))
            return results or []

        def remove_fn(shells, statuses=None):
            self.calls.append(("remove", shells, statuses))
            return results or []

        dlg = std.ShellTitleDialog(status_fn=status_fn, install_fn=install_fn, remove_fn=remove_fn)
        self.addCleanup(dlg.deleteLater)
        self.settle(dlg)
        return dlg

    def settle(self, dlg):
        end = time.monotonic() + 5
        while time.monotonic() < end:
            self.app.processEvents()
            if dlg._thread is not None and dlg._thread.isFinished() and dlg._checking.isHidden():
                break
            time.sleep(0.01)
        self.app.processEvents()

    def test_rows_and_default_ticks(self):
        dlg = self.make()
        self.assertEqual(list(dlg._boxes), [st.BASH, st.ZSH, st.PWSH])
        # Not installed with no existing file and no $SHELL match is not ticked
        # by default_selection; the stale one is.
        self.assertTrue(dlg._boxes[st.PWSH].isChecked())
        self.assertFalse(dlg._boxes[st.ZSH].isChecked())
        self.assertIn("fish", dlg._info.text())
        self.assertTrue(dlg.install_button.isEnabled())

    def test_install_passes_the_ticked_shells_and_the_shown_statuses(self):
        backup = Path("/h/.bashrc.polykybd-20261103-120000.bak")
        results = [st.Result(st.BASH, True, True, st.MSG_INSTALLED.format(path="/h/.bashrc"), backup)]
        dlg = self.make(results=results)
        dlg._boxes[st.BASH].setChecked(True)
        dlg._boxes[st.PWSH].setChecked(False)
        dlg.install_button.click()
        self.settle(dlg)
        [(what, shells, statuses)] = self.calls
        self.assertEqual((what, shells), ("install", [st.BASH]))
        self.assertEqual(statuses, _statuses())
        text = dlg._results.text()
        self.assertIn("/h/.bashrc", text)
        self.assertIn(str(backup), text)
        self.assertFalse(dlg._results.isHidden())

    def test_remove_and_nothing_ticked(self):
        dlg = self.make()
        for box in dlg._boxes.values():
            box.setChecked(False)
        self.assertFalse(dlg.remove_button.isEnabled())
        dlg._boxes[st.ZSH].setChecked(True)
        dlg.remove_button.click()
        self.assertEqual(self.calls[0][:2], ("remove", [st.ZSH]))

    def test_no_shell_found(self):
        dlg = self.make(statuses=[st.ShellStatus(st.BASH, st.STATE_NOT_PRESENT, None, "")])
        self.assertEqual(dlg._boxes, {})
        self.assertFalse(dlg._info.isHidden())
        self.assertFalse(dlg.install_button.isEnabled())

    def test_status_failure_is_shown(self):
        def boom():
            raise OSError("disk gone")
        dlg = std.ShellTitleDialog(status_fn=boom, install_fn=None, remove_fn=None)
        self.addCleanup(dlg.deleteLater)
        self.settle(dlg)
        self.assertIn("disk gone", dlg._info.text())

    def test_buttons_come_on_when_the_status_arrives_before_the_thread_ends(self):
        """`done` is emitted inside run(); handled while the thread still runs,
        it left both buttons off for good."""
        def slow_run(thread):
            thread.done.emit(thread._status_fn())
            time.sleep(0.4)     # the dialog handles `done` in this window

        with mock.patch.object(std._StatusThread, "run", slow_run):
            dlg = self.make()
            end = time.monotonic() + 5
            while not dlg._thread.isFinished() and time.monotonic() < end:
                self.app.processEvents()
                time.sleep(0.01)
            for _ in range(20):
                self.app.processEvents()
                time.sleep(0.01)
        self.assertTrue(dlg._checking.isHidden())
        self.assertTrue(dlg.install_button.isEnabled())

    def test_every_state_has_a_text(self):
        for state in (st.STATE_INSTALLED, st.STATE_NOT_INSTALLED, st.STATE_STALE,
                      st.STATE_NOT_PRESENT, st.STATE_UNKNOWN, st.STATE_BLOCKED,
                      st.STATE_NO_SETUP):
            self.assertTrue(std.state_text(st.ShellStatus(st.PWSH, state, None, "x")))


if __name__ == "__main__":
    unittest.main()
