"""The update confirmation dialog (gui/update_dialog.py)."""
import os
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QDialog
    from polyhost.gui import update_dialog
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e

# Five lines at the dialog's minimum width, the third one wrapping: the shape
# of the firmware prompt when the keyboard did not report its version.
_MESSAGE = ("Firmware 1.9.4 is available.\nReleased: 2026-10-14\n"
            "Installed: unknown (the keyboard did not report its version and "
            "this line is long enough to wrap)\n\n"
            "Both halves update over HID and reboot automatically.")


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class UpdateDialogMessageTest(unittest.TestCase):
    """The lead message lost its last line whenever a line wrapped: a top-level
    layout does not ask a label for its height-for-width (field render,
    2026-10-14)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _message_label(self, width=None):
        seen = {}

        def fake_exec(dlg):
            if width:
                dlg.resize(width, dlg.height())
            dlg.show()
            self.app.processEvents()
            seen["label"] = next(lbl for lbl in dlg.findChildren(update_dialog.QLabel)
                                 if lbl.text() == _MESSAGE)
            seen["height"] = seen["label"].height()
            seen["needed"] = seen["label"].heightForWidth(seen["label"].width())
            dlg.close()
            return QDialog.Rejected

        with mock.patch.object(QDialog, "exec_", fake_exec):
            update_dialog.confirm_update("Update", _MESSAGE, notes="- n",
                                         html_url="https://example.invalid",
                                         question="Download and flash now?")
        return seen

    def test_a_wrapped_message_is_shown_whole(self):
        seen = self._message_label()
        self.assertGreater(seen["needed"], 0)
        self.assertGreaterEqual(seen["height"], seen["needed"])

    def test_the_height_follows_a_wider_dialog(self):
        seen = self._message_label(width=1200)
        self.assertGreaterEqual(seen["height"], seen["needed"])


if __name__ == "__main__":
    unittest.main()
