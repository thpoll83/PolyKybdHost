"""Integrations -> GNOME (gui/gnome_extension_page.py) with fake service functions."""
import os
import time
import unittest
import unittest.mock as mock
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QWidget
    _IMPORT_ERR = None
except ImportError as e:  # pragma: no cover - no PyQt5
    _IMPORT_ERR = e
if _IMPORT_ERR is None:
    # Outside the guard: a broken module must fail the run, not skip its tests.
    from polyhost.gui import gnome_extension_page as gp
    from polyhost.gui import integrations_dialog as idlg
    from polyhost.services import gnome_extension as ge

FOLDER = Path("/home/u/.local/share/gnome-shell/extensions/window-reporter@polykybd.org")


def _status(**kw):
    values = dict(folder=FOLDER, files="missing", enabled=False, user_off=False,
                  user_off_writable=True, active=False, wayland=True, error="")
    values.update(kw)
    return ge.Status(**values)


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
class GnomePageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _page(self, st, install=None, remove=None):
        page = gp.GnomePage(status_fn=lambda: st, install_fn=install or mock.MagicMock(),
                            remove_fn=remove or mock.MagicMock())
        self.addCleanup(page.deleteLater)
        _settle(self.app, page)
        return page

    def test_missing_extension_with_user_extensions_off(self):
        # The 2026-11-25 machine.
        page = self._page(_status(user_off=True))
        boxes = page.boxes()
        self.assertEqual(list(boxes), [gp.EXTENSION, gp.USER_EXTENSIONS])
        self.assertTrue(boxes[gp.EXTENSION].isChecked())
        # Opt-in: it affects every user extension.
        self.assertFalse(boxes[gp.USER_EXTENSIONS].isChecked())
        self.assertTrue(boxes[gp.USER_EXTENSIONS].isEnabled())

    def test_locked_user_extensions_cannot_be_ticked(self):
        page = self._page(_status(user_off=True, user_off_writable=False))
        self.assertFalse(page.boxes()[gp.USER_EXTENSIONS].isEnabled())

    def test_installed_and_active(self):
        page = self._page(_status(files="current", enabled=True, active=True))
        self.assertEqual(list(page.boxes()), [gp.EXTENSION])
        self.assertFalse(page.boxes()[gp.EXTENSION].isChecked())
        self.assertEqual(gp.extension_state_text(page._status), "Installed and active")
        self.assertTrue(page.info.isHidden())

    def test_installed_but_not_yet_started(self):
        page = self._page(_status(files="current", enabled=True, active=False))
        self.assertIn("next login", gp.extension_state_text(page._status))
        self.assertIn("Log out", page.info.text())

    def test_x11_session_says_it_is_not_needed(self):
        page = self._page(_status(wayland=False))
        self.assertIn("X11", page.info.text())

    def test_install_passes_the_ticked_rows(self):
        install = mock.MagicMock(return_value=[
            ge.Result(ge.MSG_INSTALLED, str(FOLDER), changed=True),
            ge.Result(ge.MSG_USER_ON, changed=True)])
        page = self._page(_status(user_off=True), install=install)
        page.boxes()[gp.USER_EXTENSIONS].setChecked(True)
        page._apply(True)
        _settle(self.app, page)
        install.assert_called_once_with(extension=True, user_extensions=True)
        text = page.results.text()
        self.assertIn("installed in", text)
        self.assertIn("User extensions: switched on", text)
        self.assertIn("Log out and back in", text)

    def test_install_without_the_user_extensions_row(self):
        install = mock.MagicMock(return_value=[ge.Result(ge.MSG_INSTALLED, str(FOLDER),
                                                         changed=True)])
        page = self._page(_status(user_off=True), install=install)
        page._apply(True)
        _settle(self.app, page)
        install.assert_called_once_with(extension=True, user_extensions=False)

    def test_remove_never_touches_user_extensions(self):
        remove = mock.MagicMock(return_value=[ge.Result(ge.MSG_REMOVED, str(FOLDER),
                                                        changed=True)])
        page = self._page(_status(files="current", enabled=True, user_off=True),
                          remove=remove)
        page.boxes()[gp.EXTENSION].setChecked(True)
        page.boxes()[gp.USER_EXTENSIONS].setChecked(True)
        page._apply(False)
        _settle(self.app, page)
        remove.assert_called_once_with()
        self.assertIn("removed", page.results.text())

    def test_failed_result_is_shown(self):
        install = mock.MagicMock(return_value=[ge.Result(ge.MSG_FAILED, "no network")])
        page = self._page(_status(), install=install)
        page._apply(True)
        _settle(self.app, page)
        self.assertIn("no network", page.results.text())
        self.assertNotIn("Log out", page.results.text())


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class GnomeCategoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _nav(self):
        fakes = {c: QWidget for c in (idlg.AGENTS, idlg.TERMINALS, idlg.EDITORS, idlg.BROWSER)}
        dlg = idlg.IntegrationsDialog(mock.MagicMock(), page_factories=fakes)
        self.addCleanup(dlg.deleteLater)
        return [dlg.nav.item(i).text() for i in range(dlg.nav.count())]

    def test_gnome_shown_only_on_gnome(self):
        with mock.patch.object(idlg, "_on_gnome", return_value=False):
            self.assertNotIn("GNOME", self._nav())
        with mock.patch.object(idlg, "_on_gnome", return_value=True), \
                mock.patch.object(idlg, "_gnome_page",
                                  side_effect=lambda: gp.GnomePage(
                                      status_fn=lambda: _status())):
            self.assertEqual(self._nav()[-1], "GNOME")


if __name__ == "__main__":
    unittest.main()
