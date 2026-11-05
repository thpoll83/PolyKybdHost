"""The terminal and editor setup dialog (gui/shell_title_dialog.py): rows from
the two services' status, Install/Remove on the ticked shells and editors,
results shown."""
import os
import time
import unittest
import unittest.mock as mock
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui import shell_title_dialog as std
    from polyhost.services import editor_plugins as ep
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


def _editor_statuses():
    return [
        ep.EditorStatus(ep.VIM, ep.STATE_NOT_INSTALLED, Path("/h/.vim/pack/polykybd/start/polykybd"), ""),
        ep.EditorStatus(ep.NEOVIM, ep.STATE_NOT_PRESENT, Path("/h/nvim"), ""),
        ep.EditorStatus(ep.EMACS, ep.STATE_INSTALLED, Path("/h/.emacs.d/init.el"), ""),
    ]


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class ShellTitleDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make(self, statuses=None, results=None, editor_statuses=None, editor_results=None,
             editor_status_fn=None, report_settings=None):
        self.calls = []
        statuses = _statuses() if statuses is None else statuses
        editor_statuses = [] if editor_statuses is None else editor_statuses

        def status_fn():
            return statuses

        def install_fn(shells, statuses=None):
            self.calls.append(("install", shells, statuses))
            return results or []

        def remove_fn(shells, statuses=None):
            self.calls.append(("remove", shells, statuses))
            return results or []

        def editor_install_fn(editors, statuses=None):
            self.calls.append(("editor-install", editors, statuses))
            return editor_results or []

        def editor_remove_fn(editors, statuses=None):
            self.calls.append(("editor-remove", editors, statuses))
            return editor_results or []

        dlg = std.ShellTitleDialog(
            status_fn=status_fn, install_fn=install_fn, remove_fn=remove_fn,
            editor_status_fn=editor_status_fn or (lambda: editor_statuses),
            editor_install_fn=editor_install_fn, editor_remove_fn=editor_remove_fn,
            report_settings=report_settings)
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


    def test_editor_rows_and_default_ticks(self):
        dlg = self.make(editor_statuses=_editor_statuses())
        self.assertEqual(list(dlg._editor_boxes), [ep.VIM, ep.EMACS])
        self.assertTrue(dlg._editor_boxes[ep.VIM].isChecked())
        self.assertFalse(dlg._editor_boxes[ep.EMACS].isChecked())

    def test_an_editor_without_plugin_files_cannot_be_ticked(self):
        dlg = self.make(editor_statuses=[
            ep.EditorStatus(ep.VIM, ep.STATE_NO_SOURCE, Path("/h/.vim"), "/x/vim-plugin")])
        self.assertFalse(dlg._editor_boxes[ep.VIM].isEnabled())
        self.assertEqual(dlg.selected_editors(), [])

    def test_install_with_only_an_editor_ticked(self):
        results = [ep.Result(ep.VIM, True, True, ep.MSG_INSTALLED.format(path="/h/.vim/x"), None)]
        dlg = self.make(editor_statuses=_editor_statuses(), editor_results=results)
        for box in dlg._boxes.values():
            box.setChecked(False)
        self.assertTrue(dlg.install_button.isEnabled())
        dlg.install_button.click()
        self.settle(dlg)
        [(what, editors, statuses)] = self.calls
        self.assertEqual((what, editors), ("editor-install", [ep.VIM]))
        self.assertEqual(statuses, _editor_statuses())
        self.assertIn("/h/.vim/x", dlg._results.text())
        self.assertIn("Restart the editor", dlg._results.text())

    def test_remove_acts_on_both_lists(self):
        dlg = self.make(editor_statuses=_editor_statuses())
        for box in dlg._boxes.values():
            box.setChecked(False)
        dlg._boxes[st.ZSH].setChecked(True)
        dlg._editor_boxes[ep.VIM].setChecked(False)
        dlg._editor_boxes[ep.EMACS].setChecked(True)
        dlg.remove_button.click()
        self.assertEqual([c[:2] for c in self.calls],
                         [("remove", [st.ZSH]), ("editor-remove", [ep.EMACS])])

    def test_a_failed_editor_check_keeps_the_shell_rows(self):
        def boom():
            raise OSError("home gone")
        dlg = self.make(editor_status_fn=boom)
        self.assertEqual(list(dlg._boxes), [st.BASH, st.ZSH, st.PWSH])
        self.assertEqual(dlg._editor_boxes, {})
        self.assertTrue(dlg.install_button.isEnabled())

    def test_a_changed_report_port_shows_the_settings_note(self):
        dlg = self.make(editor_statuses=_editor_statuses(), report_settings=(50164, ""))
        self.assertTrue(dlg._settings_note.isHidden())
        dlg = self.make(editor_statuses=_editor_statuses(), report_settings=(50200, "t"))
        self.assertFalse(dlg._settings_note.isHidden())
        self.assertIn("50200", dlg._settings_note.text())

    def test_every_editor_state_has_a_text(self):
        for state in (ep.STATE_INSTALLED, ep.STATE_NOT_INSTALLED, ep.STATE_OUTDATED,
                      ep.STATE_MODIFIED, ep.STATE_STALE, ep.STATE_MANUAL,
                      ep.STATE_NOT_PRESENT, ep.STATE_NO_SOURCE):
            self.assertTrue(std.editor_state_text(ep.EditorStatus(ep.VIM, state, None, "x")))


if __name__ == "__main__":
    unittest.main()
