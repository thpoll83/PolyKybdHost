"""Integrations (gui/integrations_dialog.py): the category list and pages, and
the AI agents page on a temporary home folder."""
import os
import tempfile
import time
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QLabel, QWidget
    _IMPORT_ERR = None
except ImportError as e:  # pragma: no cover - no PyQt5
    _IMPORT_ERR = e
if _IMPORT_ERR is None:
    # Outside the guard: a broken module must fail the run, not skip its tests.
    from polyhost.gui import integrations_dialog as idlg
    from polyhost.services.agents import hook_install as hi

ARGV = ["/opt/poly/polyctl"]


def _settle(app, page):
    end = time.monotonic() + 5
    while time.monotonic() < end:
        app.processEvents()
        if page._thread is not None and page._thread.isFinished() \
                and page._checking.isHidden():
            break
        time.sleep(0.01)
    app.processEvents()


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class IntegrationsDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _fake_pages(self):
        made = []

        def factory(name):
            def make():
                page = QWidget()
                page.reopen = mock.MagicMock()
                page.name = name
                made.append(page)
                return page
            return make
        return {c: factory(c) for c in idlg.CATEGORIES}, made

    def test_categories_in_sidebar_order(self):
        factories, made = self._fake_pages()
        dlg = idlg.IntegrationsDialog(mock.MagicMock(), page_factories=factories)
        self.addCleanup(dlg.deleteLater)
        self.assertEqual([dlg.nav.item(i).text() for i in range(dlg.nav.count())],
                         ["AI agents", "Terminals", "Editors", "Browser"])
        self.assertEqual(dlg.current_category(), idlg.AGENTS)
        self.assertEqual(dlg.windowTitle(), "Integrations")

    def test_show_category_switches_the_page(self):
        factories, _made = self._fake_pages()
        dlg = idlg.IntegrationsDialog(mock.MagicMock(), page_factories=factories)
        self.addCleanup(dlg.deleteLater)
        dlg.show_category(idlg.EDITORS)
        self.assertEqual(dlg.current_category(), idlg.EDITORS)
        self.assertEqual(dlg.stack.currentIndex(), 2)
        dlg.show_category(idlg.BROWSER)
        self.assertEqual(dlg.stack.currentIndex(), 3)

    def test_only_the_listed_categories_are_shown(self):
        factories, made = self._fake_pages()
        dlg = idlg.IntegrationsDialog(mock.MagicMock(), page_factories=factories,
                                      categories=(idlg.AGENTS, idlg.TERMINALS, idlg.EDITORS))
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.nav.count(), 3)
        self.assertNotIn(idlg.BROWSER, dlg.pages)
        dlg.show_category(idlg.BROWSER)              # ignored, not an error
        self.assertEqual(dlg.current_category(), idlg.AGENTS)

    def test_reopen_reads_every_page_again(self):
        factories, made = self._fake_pages()
        dlg = idlg.IntegrationsDialog(mock.MagicMock(), page_factories=factories)
        self.addCleanup(dlg.deleteLater)
        dlg.reopen()
        for page in made:
            page.reopen.assert_called_once_with()

    def test_open_integrations_keeps_one_window(self):
        factories, made = self._fake_pages()
        owner = mock.MagicMock(integrations_dialog=None)
        first = idlg.open_integrations(owner, category=idlg.TERMINALS,
                                       page_factories=factories)
        self.addCleanup(first.deleteLater)
        self.assertEqual(first.current_category(), idlg.TERMINALS)
        second = idlg.open_integrations(owner, category=idlg.AGENTS)
        self.assertIs(first, second)
        self.assertEqual(second.current_category(), idlg.AGENTS)
        first.close()
        idlg.open_integrations(owner)                # hidden: read the files again
        for page in made:
            page.reopen.assert_called_once_with()


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class AgentsPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        self.asked = []

    def make(self, answer=True, note=None):
        home = self.home

        def confirm(text, details):
            self.asked.append((text, details))
            return answer

        page = idlg.AgentsPage(
            mock.MagicMock(), note=note,
            status_fn=lambda: [hi.status(v, home, ARGV) for v in hi.VENDORS],
            plan_fn=lambda vendor, install: hi.plan(vendor, home, install, ARGV),
            confirm=confirm)
        self.addCleanup(page.deleteLater)
        _settle(self.app, page)
        return page

    def _state_texts(self, page):
        return [w.text() for w in page.findChildren(QLabel)]

    def test_one_row_per_agent_nothing_ticked_on_a_clean_home(self):
        page = self.make()
        boxes = page.boxes()
        self.assertEqual([b.text() for b in boxes.values()],
                         ["Claude Code", "Codex", "Copilot CLI", "Gemini CLI", "Qwen Code",
                          "OpenCode"])
        self.assertFalse(any(b.isChecked() for b in boxes.values()))
        self.assertFalse(page.install_button.isEnabled())
        self.assertIn(hi.config_path("codex", self.home), self._state_texts(page))

    def test_install_asks_with_the_diff_then_writes(self):
        page = self.make(note=lambda: "on the keyboard computer, turn on X")
        page.boxes()["claude-code"].setChecked(True)
        page.boxes()["opencode"].setChecked(True)
        # Nothing of ours yet: Remove has nothing to do.
        self.assertFalse(page.remove_button.isEnabled())
        page.install_button.click()
        _settle(self.app, page)
        [(text, details)] = self.asked
        self.assertIn(hi.config_path("claude-code", self.home), text)
        self.assertIn("agents hook claude-code", details)
        self.assertEqual(hi.status("claude-code", self.home, ARGV).state, hi.STATE_INSTALLED)
        self.assertEqual(hi.status("opencode", self.home, ARGV).state, hi.STATE_INSTALLED)
        self.assertIn("turn on X", page.results.text())
        # The rows were read again: Remove now has hooks to take out.
        self.assertTrue(page.remove_button.isEnabled())

    def test_no_on_the_question_writes_nothing(self):
        page = self.make(answer=False)
        page.boxes()["gemini"].setChecked(True)
        page.install_button.click()
        _settle(self.app, page)
        self.assertEqual(len(self.asked), 1)
        self.assertFalse(os.path.exists(hi.config_path("gemini", self.home)))
        self.assertTrue(page.results.isHidden())

    def test_remove_takes_out_only_the_ticked_agents_hooks(self):
        for vendor in ("claude-code", "copilot"):
            hi.apply(hi.plan(vendor, self.home, argv=ARGV))
        page = self.make()
        for box in page.boxes().values():
            box.setChecked(False)
        page.boxes()["copilot"].setChecked(True)
        page.remove_button.click()
        _settle(self.app, page)
        self.assertIn("Remove the PolyKybd hooks", self.asked[0][0])
        self.assertEqual(hi.status("copilot", self.home, ARGV).state, hi.STATE_NOT_INSTALLED)
        self.assertEqual(hi.status("claude-code", self.home, ARGV).state, hi.STATE_INSTALLED)

    def test_hooks_of_another_copy_are_ticked_for_update(self):
        hi.apply(hi.plan("qwen", self.home, argv=["/old/polyctl"]))
        page = self.make()
        self.assertTrue(page.boxes()["qwen"].isChecked())
        self.assertTrue(page.remove_button.isEnabled())

    def test_a_codex_conflict_row_cannot_be_ticked(self):
        path = hi.config_path("codex", self.home)
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('notify = ["my-notifier"]\n')
        page = self.make()
        self.assertFalse(page.boxes()["codex"].isEnabled())
        self.assertTrue(any("notify" in t for t in self._state_texts(page)))

    def test_every_state_has_a_text(self):
        for state in (hi.STATE_INSTALLED, hi.STATE_NOT_INSTALLED, hi.STATE_OUTDATED,
                      hi.STATE_CONFLICT, hi.STATE_ERROR):
            self.assertTrue(idlg.agent_state_text(hi.HookStatus("codex", "/p", state, "x")))


if __name__ == "__main__":
    unittest.main()
