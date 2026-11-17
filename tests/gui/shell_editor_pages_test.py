"""Integrations > Terminals and > Editors (gui/shell_editor_pages.py): rows from
the two services' status, Install/Remove on the ticked rows, results shown."""
import os
import tempfile
import time
import unittest
import unittest.mock as mock
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    _IMPORT_ERR = None
except ImportError as e:  # pragma: no cover - no PyQt5
    _IMPORT_ERR = e
if _IMPORT_ERR is None:
    # Outside the guard: a broken module must fail the run, not skip its tests.
    from polyhost.gui import integrations_dialog as idlg
    from polyhost.gui import shell_editor_pages as sep
from polyhost.services import editor_plugins as ep
from polyhost.services import shell_title as st


def _statuses():
    return [
        st.ShellStatus(st.BASH, st.STATE_NOT_INSTALLED, Path("/h/.bashrc"), ""),
        st.ShellStatus(st.ZSH, st.STATE_INSTALLED, Path("/h/.zshrc"), ""),
        st.ShellStatus(st.PWSH, st.STATE_STALE, Path("/h/profile.ps1"), "/old/polykybd-title.ps1"),
        st.ShellStatus(st.POWERSHELL, st.STATE_NOT_PRESENT, None, ""),
        st.ShellStatus(st.NUSHELL, st.STATE_NO_SETUP, None, ""),
    ]


def _editor_statuses():
    return [
        ep.EditorStatus(ep.VIM, ep.STATE_NOT_INSTALLED, Path("/h/.vim/pack/polykybd/start/polykybd"), ""),
        ep.EditorStatus(ep.NEOVIM, ep.STATE_NOT_PRESENT, Path("/h/nvim"), ""),
        ep.EditorStatus(ep.EMACS, ep.STATE_INSTALLED, Path("/h/.emacs.d/init.el"), ""),
    ]


class _PageTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def settle(self, page):
        end = time.monotonic() + 5
        while time.monotonic() < end:
            self.app.processEvents()
            if page._thread is not None and page._thread.isFinished() \
                    and page._checking.isHidden():
                break
            time.sleep(0.01)
        self.app.processEvents()


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TerminalsPageTest(_PageTestBase):
    def make(self, statuses=None, results=None):
        self.calls = []
        self.codex_calls = []
        statuses = _statuses() if statuses is None else statuses

        def install_fn(shells, statuses=None, codex=None):
            self.calls.append(("install", shells, statuses))
            self.codex_calls.append(codex)
            return results or []

        def remove_fn(shells, statuses=None):
            self.calls.append(("remove", shells, statuses))
            return results or []

        page = sep.TerminalsPage(status_fn=lambda: statuses, install_fn=install_fn,
                                 remove_fn=remove_fn)
        self.addCleanup(page.deleteLater)
        self.settle(page)
        return page

    def test_rows_and_default_ticks(self):
        page = self.make()
        boxes = page.boxes()
        self.assertEqual(list(boxes), [st.BASH, st.ZSH, st.PWSH])
        # Not installed with no existing file and no $SHELL match is not ticked
        # by default_selection; the stale one is.
        self.assertTrue(boxes[st.PWSH].isChecked())
        self.assertFalse(boxes[st.ZSH].isChecked())
        self.assertIn("Nushell", page.info.text())
        self.assertTrue(page.install_button.isEnabled())

    def test_install_passes_the_ticked_shells_and_the_shown_statuses(self):
        backup = Path("/h/.bashrc.polykybd-20261103-120000.bak")
        results = [st.Result(st.BASH, True, True, st.MSG_INSTALLED.format(path="/h/.bashrc"), backup)]
        page = self.make(results=results)
        page.boxes()[st.BASH].setChecked(True)
        page.boxes()[st.PWSH].setChecked(False)
        page.install_button.click()
        self.settle(page)
        [(what, shells, statuses)] = self.calls
        self.assertEqual((what, shells), ("install", [st.BASH]))
        self.assertEqual(statuses, _statuses())
        text = page.results.text()
        self.assertIn("/h/.bashrc", text)
        self.assertIn(str(backup), text)
        self.assertIn("Open a new terminal window", text)
        self.assertFalse(page.results.isHidden())

    def test_codex_box_shows_the_installed_option_and_is_passed(self):
        page = self.make()
        self.assertFalse(page.codex_box.isChecked())
        page.codex_box.click()
        page.boxes()[st.BASH].setChecked(True)
        page.install_button.click()
        self.settle(page)
        self.assertEqual(self.codex_calls, [True])
        # The refresh after the change does not undo the user's choice.
        self.assertTrue(page.codex_box.isChecked())

        statuses = _statuses()
        statuses[1] = statuses[1]._replace(codex=True)
        page = self.make(statuses=statuses)
        self.assertTrue(page.codex_box.isChecked())

    def test_remove_and_nothing_ticked(self):
        page = self.make()
        for box in page.boxes().values():
            box.setChecked(False)
        self.assertFalse(page.remove_button.isEnabled())
        page.boxes()[st.ZSH].setChecked(True)
        page.remove_button.click()
        self.settle(page)
        self.assertEqual(self.calls[0][:2], ("remove", [st.ZSH]))

    def test_the_ticks_survive_the_refresh_after_a_change(self):
        page = self.make()
        page.boxes()[st.BASH].setChecked(True)
        page.remove_button.click()
        self.settle(page)
        self.assertTrue(page.boxes()[st.BASH].isChecked())

    def test_no_shell_found(self):
        page = self.make(statuses=[st.ShellStatus(st.BASH, st.STATE_NOT_PRESENT, None, "")])
        self.assertEqual(page.boxes(), {})
        self.assertFalse(page.info.isHidden())
        self.assertFalse(page.install_button.isEnabled())

    def test_status_failure_is_shown(self):
        def boom():
            raise OSError("disk gone")
        page = sep.TerminalsPage(status_fn=boom)
        self.addCleanup(page.deleteLater)
        self.settle(page)
        self.assertIn("disk gone", page.info.text())

    def test_a_failing_install_is_shown_not_raised(self):
        def boom(*_a, **_k):
            raise OSError("read-only")
        page = sep.TerminalsPage(status_fn=_statuses, install_fn=boom)
        self.addCleanup(page.deleteLater)
        self.settle(page)
        page.boxes()[st.BASH].setChecked(True)
        page.install_button.click()
        self.settle(page)
        self.assertIn("read-only", page.results.text())

    def test_buttons_come_on_when_the_status_arrives_before_the_thread_ends(self):
        """`done` is emitted inside run(); handled while the thread still runs,
        it left both buttons off for good."""
        def slow_run(thread):
            thread.done.emit(thread._status_fn())
            time.sleep(0.4)     # the page handles `done` in this window

        with mock.patch.object(idlg._StatusThread, "run", slow_run):
            page = self.make()
            end = time.monotonic() + 5
            while not page._thread.isFinished() and time.monotonic() < end:
                self.app.processEvents()
                time.sleep(0.01)
            for _ in range(20):
                self.app.processEvents()
                time.sleep(0.01)
        self.assertTrue(page._checking.isHidden())
        self.assertTrue(page.install_button.isEnabled())

    def test_a_slow_install_runs_off_the_gui_thread(self):
        """Install may start PowerShell or GDB. The click returns at once,
        the buttons stay off while it runs, and the result arrives after."""
        def slow_install(shells, statuses=None, codex=None):
            time.sleep(0.4)
            return [st.Result(st.BASH, True, True, st.MSG_INSTALLED.format(path="/h/.bashrc"), None)]
        page = sep.TerminalsPage(status_fn=_statuses, install_fn=slow_install)
        self.addCleanup(page.deleteLater)
        self.settle(page)
        page.boxes()[st.BASH].setChecked(True)
        start = time.monotonic()
        page.install_button.click()
        self.assertLess(time.monotonic() - start, 0.2)
        self.assertFalse(page.install_button.isEnabled())
        self.assertFalse(page.remove_button.isEnabled())
        end = time.monotonic() + 5
        while page.results.isHidden() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)
        self.settle(page)
        self.assertIn("/h/.bashrc", page.results.text())
        self.assertTrue(page.install_button.isEnabled())

    def test_fish_says_it_needs_setup_only_for_codex(self):
        text = sep.state_text(st.ShellStatus(st.FISH, st.STATE_NOT_INSTALLED, None, ""))
        self.assertIn("Codex", text)
        self.assertNotEqual(text, sep.state_text(
            st.ShellStatus(st.BASH, st.STATE_NOT_INSTALLED, None, "")))

    def test_every_state_has_a_text(self):
        for state in (st.STATE_INSTALLED, st.STATE_NOT_INSTALLED, st.STATE_STALE,
                      st.STATE_NOT_PRESENT, st.STATE_UNKNOWN, st.STATE_BLOCKED,
                      st.STATE_NO_SETUP):
            self.assertTrue(sep.state_text(st.ShellStatus(st.PWSH, state, None, "x")))


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class EditorsPageTest(_PageTestBase):
    def make(self, statuses=None, results=None, status_fn=None, report_settings=(50164, "")):
        self.calls = []
        statuses = _editor_statuses() if statuses is None else statuses

        def install_fn(editors, statuses=None):
            self.calls.append(("install", editors, statuses))
            return results or []

        def remove_fn(editors, statuses=None):
            self.calls.append(("remove", editors, statuses))
            return results or []

        page = sep.EditorsPage(status_fn=status_fn or (lambda: statuses),
                               install_fn=install_fn, remove_fn=remove_fn,
                               report_settings=report_settings)
        self.addCleanup(page.deleteLater)
        self.settle(page)
        return page

    def test_rows_and_default_ticks(self):
        page = self.make()
        boxes = page.boxes()
        self.assertEqual(list(boxes), [ep.VIM, ep.EMACS])
        self.assertTrue(boxes[ep.VIM].isChecked())
        self.assertFalse(boxes[ep.EMACS].isChecked())

    def test_an_editor_without_plugin_files_cannot_be_ticked(self):
        page = self.make(statuses=[
            ep.EditorStatus(ep.VIM, ep.STATE_NO_SOURCE, Path("/h/.vim"), "/x/vim-plugin")])
        self.assertFalse(page.boxes()[ep.VIM].isEnabled())
        self.assertEqual(page.selected(), [])
        self.assertFalse(page.install_button.isEnabled())

    def test_install(self):
        results = [ep.Result(ep.VIM, True, True, ep.MSG_INSTALLED.format(path="/h/.vim/x"), None)]
        page = self.make(results=results)
        page.install_button.click()
        self.settle(page)
        [(what, editors, statuses)] = self.calls
        self.assertEqual((what, editors), ("install", [ep.VIM]))
        # The service reads the files again rather than trusting the rows.
        self.assertIsNone(statuses)
        self.assertIn("/h/.vim/x", page.results.text())
        self.assertIn("Restart the editor", page.results.text())

    def test_remove(self):
        page = self.make()
        page.boxes()[ep.VIM].setChecked(False)
        page.boxes()[ep.EMACS].setChecked(True)
        page.remove_button.click()
        self.settle(page)
        self.assertEqual([c[:3] for c in self.calls], [("remove", [ep.EMACS], None)])

    def test_remove_keeps_a_plugin_changed_after_the_page_was_shown(self):
        """The real service on a temporary home: a file edited after the
        rows were read is found as changed by hand, not deleted."""
        home = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, home, True)
        kw = dict(home=home, env={}, which=lambda _n: "/usr/bin/vim")
        ep.install([ep.VIM], **kw)
        page = sep.EditorsPage(status_fn=lambda: ep.status([ep.VIM], **kw),
                               install_fn=lambda e, statuses=None: ep.install(e, statuses, **kw),
                               remove_fn=lambda e, statuses=None: ep.remove(e, statuses, **kw),
                               report_settings=(50164, ""))
        self.addCleanup(page.deleteLater)
        self.settle(page)
        target = Path(ep.status([ep.VIM], **kw)[0].target)
        some_file = next(p for p in target.rglob("*") if p.is_file() and p.suffix == ".vim")
        some_file.write_text(some_file.read_text() + "\n\" my own line\n")
        page.boxes()[ep.VIM].setChecked(True)
        page.remove_button.click()
        self.settle(page)
        self.assertTrue(some_file.exists())
        self.assertIn("my own line", some_file.read_text())

    def test_no_editor_found(self):
        page = self.make(statuses=[ep.EditorStatus(ep.VIM, ep.STATE_NOT_PRESENT, None, "")])
        self.assertEqual(page.boxes(), {})
        self.assertFalse(page.install_button.isEnabled())

    def test_a_failed_check_is_shown(self):
        def boom():
            raise OSError("home gone")
        page = self.make(status_fn=boom)
        self.assertEqual(page.boxes(), {})
        self.assertIn("home gone", page.info.text())

    def test_a_changed_report_port_shows_the_settings_note(self):
        page = self.make(report_settings=(50164, ""))
        self.assertTrue(page.settings_note.isHidden())
        page = self.make(report_settings=(50200, "t"))
        self.assertFalse(page.settings_note.isHidden())
        self.assertIn("50200", page.settings_note.text())

    def test_the_jetbrains_row_has_its_label_and_restart_hint(self):
        from PyQt5.QtWidgets import QLabel
        page = self.make(statuses=[
            ep.EditorStatus(ep.JETBRAINS, ep.STATE_NOT_INSTALLED, Path("/h/.local/share/JetBrains"),
                            "PyCharm2025.2")])
        self.assertEqual(list(page.boxes()), [ep.JETBRAINS])
        self.assertTrue(page.boxes()[ep.JETBRAINS].isChecked())
        texts = [w.text() for w in page.findChildren(QLabel)]
        self.assertEqual(sep.editor_label(ep.JETBRAINS), "JetBrains IDEs")
        self.assertTrue(any("JetBrains IDEs" in t for t in texts)
                        or "JetBrains IDEs" in page.boxes()[ep.JETBRAINS].text(), texts)
        self.assertIn("Restart the IDE after Install.", texts)

    def test_every_editor_state_has_a_text(self):
        for state in (ep.STATE_INSTALLED, ep.STATE_NOT_INSTALLED, ep.STATE_OUTDATED,
                      ep.STATE_MODIFIED, ep.STATE_STALE, ep.STATE_MANUAL,
                      ep.STATE_NOT_PRESENT, ep.STATE_NO_SOURCE, ep.STATE_NO_PROJECT,
                      ep.STATE_COMMAND):
            self.assertTrue(sep.editor_state_text(ep.EditorStatus(ep.VIM, state, None, "x")))
        texts = {sep.editor_state_text(ep.EditorStatus(ep.VIM, s, None, "x"))
                 for s in (ep.STATE_NO_PROJECT, ep.STATE_COMMAND, ep.STATE_NOT_PRESENT)}
        self.assertEqual(len(texts), 3)

    def make_new(self, statuses):
        """A page whose install_fn and remove_fn also take ``projects``."""
        calls = []

        def install_fn(editors, statuses=None, projects=None):
            calls.append(("install", editors, projects))
            return []

        def remove_fn(editors, statuses=None, projects=None):
            calls.append(("remove", editors, projects))
            return []

        page = sep.EditorsPage(status_fn=lambda: statuses, install_fn=install_fn,
                               remove_fn=remove_fn, report_settings=(50164, ""))
        self.addCleanup(page.deleteLater)
        self.settle(page)
        return page, calls

    def tmp_project(self, marker):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        (Path(tmp.name) / marker).write_text("")
        return Path(tmp.name)

    def test_every_new_editor_has_a_label_and_a_hint(self):
        for editor in ep.NEW_EDITORS:
            self.assertNotEqual(sep.editor_label(editor), editor)
            self.assertTrue(sep.editor_hint(ep.EditorStatus(editor, ep.STATE_NOT_INSTALLED, None, "")),
                            editor)

    def test_jupyterlab_shows_the_command_with_a_copy_button_and_cannot_be_ticked(self):
        cmd = 'python -m pip install "/x/jupyterlab-extension"'
        page, _calls = self.make_new([ep.EditorStatus(ep.JUPYTERLAB, ep.STATE_COMMAND, None, cmd)])
        box = page.boxes()[ep.JUPYTERLAB]
        self.assertFalse(box.isEnabled() or box.isChecked())
        self.assertNotIn(ep.JUPYTERLAB, page._removable)
        from PyQt5.QtWidgets import QLabel
        self.assertIn(cmd, [w.text() for w in page.findChildren(QLabel)])
        page.copy_buttons[ep.JUPYTERLAB].click()
        self.assertEqual(QApplication.clipboard().text(), cmd)

    def test_add_a_project_folder_installs_into_it(self):
        game = self.tmp_project("project.godot")
        page, calls = self.make_new([ep.EditorStatus(ep.GODOT, ep.STATE_NO_PROJECT, None, "")])
        self.assertFalse(page.boxes()[ep.GODOT].isChecked())
        page.choose_folder = lambda editor: str(game)
        page.project_buttons[ep.GODOT].click()
        self.settle(page)
        self.assertEqual(calls, [("install", [ep.GODOT], {ep.GODOT: [str(game)]})])

    def test_install_asks_for_a_project_and_refuses_a_wrong_folder(self):
        wrong = self.tmp_project("README.md")
        page, calls = self.make_new([ep.EditorStatus(ep.UNITY, ep.STATE_NO_PROJECT, None, ""),
                                 ep.EditorStatus(ep.VIM, ep.STATE_NOT_INSTALLED, Path("/v"), "")])
        asked, warned = [], []
        page.choose_folder = lambda editor: asked.append(editor) or str(wrong)
        page.warn = warned.append
        page.boxes()[ep.UNITY].setChecked(True)
        page.install_button.click()
        self.settle(page)
        self.assertEqual(asked, [ep.UNITY])
        self.assertIn("Packages/manifest.json", warned[0])
        self.assertEqual(calls, [("install", [ep.UNITY, ep.VIM], None)])

    def test_a_vault_row_shows_its_folders(self):
        page, _calls = self.make_new([ep.EditorStatus(ep.OBSIDIAN, ep.STATE_INSTALLED, None,
                                                  "/n/Notes, /n/Work")])
        from PyQt5.QtWidgets import QLabel
        self.assertIn("/n/Notes, /n/Work", [w.text() for w in page.findChildren(QLabel)])
        self.assertEqual(page.project_buttons[ep.OBSIDIAN].text(), sep.project_button_text(ep.OBSIDIAN))


if __name__ == "__main__":
    unittest.main()
