"""gui/browser_extension_page.py: Integrations > Browser."""
import json
import os
import shutil
import tempfile
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    _QT = True
except ImportError:  # no Qt: skip
    _QT = False
if _QT:
    # Outside the guard: a broken module must fail the run, not skip its tests.
    from polyhost.gui import browser_extension_page as bep
    from polyhost.services import browser_extension as be


@unittest.skipUnless(_QT, "needs PyQt5 and a display (xvfb-run)")
class BrowserPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state = os.path.join(self.tmp, "state.json")
        patch = mock.patch.object(be, "_state_path", lambda: self.state)
        patch.start()
        self.addCleanup(patch.stop)

    def _dialog(self):
        dlg = bep.BrowserPage(mock.MagicMock(), receiver_port=50164)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_copy_writes_the_folder_and_remembers_it(self):
        dlg = self._dialog()
        self.assertEqual(dlg.folder.text(), "")
        dlg.copy_button.click()
        self.assertIn("Choose a folder first", dlg.status.text())
        folder = os.path.join(self.tmp, "ext")
        dlg.folder.setText(folder)
        dlg.copy_button.click()
        self.assertIn(be.source_version(), dlg.status.text())
        self.assertEqual(be.installed_version(folder), be.source_version())
        with open(self.state, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["folder"], folder)
        self.assertEqual(self._dialog().folder.text(), folder)     # pre-filled next time

    def test_a_folder_with_other_files_is_reported_not_overwritten(self):
        folder = os.path.join(self.tmp, "mine")
        os.makedirs(folder)
        with open(os.path.join(folder, "notes.txt"), "w", encoding="utf-8") as fh:
            fh.write("x")
        dlg = self._dialog()
        dlg.folder.setText(folder)
        dlg.copy_button.click()
        self.assertIn("Not copied", dlg.status.text())
        self.assertEqual(os.listdir(folder), ["notes.txt"])
        self.assertFalse(os.path.exists(self.state))

    def test_steps_name_the_port_and_the_page_button_copies(self):
        from PyQt5.QtWidgets import QLabel, QPushButton
        dlg = self._dialog()
        texts = " ".join(label.text() for label in dlg.findChildren(QLabel))
        self.assertIn("50164", texts)
        self.assertIn("Load unpacked", texts)
        button = next(b for b in dlg.findChildren(QPushButton) if "chrome://" in b.text())
        button.click()
        self.assertEqual(QApplication.clipboard().text(), "chrome://extensions")


    def test_reopen_shows_the_receiver_port_as_it_is_now(self):
        with mock.patch("polyhost.settings.read_setting", return_value=50164):
            page = bep.BrowserPage(mock.MagicMock())
        self.addCleanup(page.deleteLater)
        self.assertIn("50164", page.steps.text())
        with mock.patch("polyhost.settings.read_setting", return_value=50200):
            page.reopen()
        self.assertIn("50200", page.steps.text())
        self.assertNotIn("50164", page.steps.text())

    def test_the_long_step_text_does_not_overlap_its_button(self):
        # German is the longest; the window opened at a height computed before
        # the labels wrapped, and the step text ran under the button.
        import time
        from PyQt5.QtWidgets import QPushButton
        from polyhost.gui.i18n_qt import prepare
        from polyhost.gui.ui_kit import WrapLabel
        from polyhost.gui.integrations_dialog import BROWSER, IntegrationsDialog
        self.addCleanup(prepare, "en")
        prepare("de")
        # The page as the tray shows it: in the Integrations dialog's scroll area.
        dlg = IntegrationsDialog(mock.MagicMock(), categories=(BROWSER,), page_factories={
            BROWSER: lambda: bep.BrowserPage(mock.MagicMock(), receiver_port=50164)})
        self.addCleanup(dlg.deleteLater)
        dlg.show()
        for _ in range(5):
            QApplication.processEvents()
            time.sleep(0.02)
        page = dlg.pages[BROWSER]
        steps = next(w for w in page.findChildren(WrapLabel) if "chrome://" in w.text())
        button = next(b for b in page.findChildren(QPushButton) if "chrome://" in b.text())
        bottom = steps.mapTo(page, steps.rect().bottomLeft()).y()
        self.assertLess(bottom, button.mapTo(page, button.rect().topLeft()).y())
        dlg.close()

if __name__ == "__main__":
    unittest.main()
