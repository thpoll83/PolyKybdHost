"""host._msgbox: a long message is shown whole, a short one keeps the old size.

The box had a fixed 400x160 size, which cut the "release has no firmware
file" warning to its first third (field report, 2026-10-14).

Importing polyhost.host needs an X server (pynput), hence the guard.
"""
import os
import unittest
import unittest.mock as mock

_LONG = ("Firmware v1.9.1 has been released, but it does not include a downloadable "
         "firmware file, so it cannot be installed yet.\n\nYour keyboard is on v1.8.4. "
         "This usually means the release build failed - the release page will get its "
         "firmware once that is fixed.\n\n"
         "https://github.com/thpoll83/qmk_firmware/releases/tag/PolyKybd-fw-v1.9.1")


@unittest.skipUnless(os.environ.get("DISPLAY"),
                     "polyhost.host imports pynput, which needs an X server")
class MsgboxHeightTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from polyhost import host
        cls.host = host

    def _show(self, text):
        from PyQt5.QtWidgets import QDialog, QLabel, QScrollArea
        seen = {}

        def fake_exec(dlg):
            dlg.show()
            self.app.processEvents()
            label = next(lbl for lbl in dlg.findChildren(QLabel) if lbl.text() == text)
            seen.update(dialog=dlg.height(), label=label.height(),
                        needed=label.heightForWidth(label.width()),
                        scrolls=bool(dlg.findChildren(QScrollArea)))
            dlg.close()
            return QDialog.Rejected

        with mock.patch.object(QDialog, "exec_", fake_exec):
            self.host._msgbox(self.host.QMessageBox.Warning, "PolyKybd Firmware", text)
        return seen

    def test_a_long_message_is_shown_whole(self):
        seen = self._show(_LONG)
        self.assertGreater(seen["needed"], 0)
        self.assertGreaterEqual(seen["label"], seen["needed"])

    def test_a_message_taller_than_the_screen_scrolls(self):
        # Capped at 80% of the available screen height, so the buttons stay
        # on screen; the text scrolls inside instead (Greptile, #387).
        avail = self.app.primaryScreen().availableGeometry().height()
        seen = self._show("\n".join(f"line {i}" for i in range(400)))
        self.assertLessEqual(seen["dialog"], int(avail * 0.8))
        self.assertTrue(seen["scrolls"])

    def test_a_short_message_keeps_the_minimum_size(self):
        seen = self._show("No firmware release could be found.")
        self.assertEqual(seen["dialog"], self.host._UPD_DLG_H)


if __name__ == "__main__":
    unittest.main()
