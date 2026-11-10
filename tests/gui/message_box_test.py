"""gui/message_box.py: QMessageBox's answers, with the app's icons.

Each test answers the box the way a user would, by clicking one of its
buttons or pressing Escape, and checks the code the caller gets back.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox  # noqa: E402

from polyhost.gui import message_box  # noqa: E402
from polyhost.gui.message_box import MessageBox  # noqa: E402

_APP = QApplication.instance() or QApplication([])


def _answer(click):
    """Patch exec_ so the box is answered by ``click(box)`` instead of a user."""
    def exec_(box):
        box.show()
        _APP.processEvents()
        click(box)
        box.close()
        return box.result()
    return mock.patch.object(QDialog, "exec_", exec_)


def _std(code):
    return lambda box: box.button_box.button(QDialogButtonBox.StandardButton(code)).click()


class AnswerTest(unittest.TestCase):

    def test_question_returns_the_clicked_button(self):
        for code in (QMessageBox.Yes, QMessageBox.No):
            with _answer(_std(code)):
                self.assertEqual(message_box.question(None, "t", "Sure?"), code)

    def test_escape_answers_cancel_then_no(self):
        with _answer(lambda box: box.reject()):
            self.assertEqual(message_box.question(None, "t", "Sure?"), QMessageBox.No)
            self.assertEqual(message_box.question(
                None, "t", "Sure?", QMessageBox.Yes | QMessageBox.Cancel), QMessageBox.Cancel)
            self.assertEqual(message_box.information(None, "t", "Done."), QMessageBox.Ok)

    def test_default_button_follows_the_argument(self):
        box = MessageBox(QMessageBox.Question, "t", "Sure?",
                         QMessageBox.Yes | QMessageBox.No, default=QMessageBox.No)
        self.addCleanup(box.deleteLater)
        self.assertTrue(box.button_box.button(QDialogButtonBox.No).isDefault())
        self.assertFalse(box.button_box.button(QDialogButtonBox.Yes).isDefault())

    def test_custom_buttons_report_which_was_clicked(self):
        box = MessageBox(QMessageBox.Question, "t", "Which side?", QMessageBox.NoButton)
        self.addCleanup(box.deleteLater)
        left = box.add_button("Left", QMessageBox.AcceptRole, "left")
        box.add_button("Cancel", QMessageBox.RejectRole, "cancel")
        left.click()
        self.assertIs(box.clicked_button(), left)
        self.assertEqual(box.result(), QDialog.Accepted)

    def test_every_button_has_an_icon(self):
        box = MessageBox(QMessageBox.Warning, "t", "Text", QMessageBox.Yes | QMessageBox.No
                         | QMessageBox.Cancel | QMessageBox.Ok)
        self.addCleanup(box.deleteLater)
        for btn in box.button_box.buttons():
            self.assertFalse(btn.icon().isNull(), btn.text())
        self.assertFalse(box.icon.pixmap().isNull())

    def test_informative_text_is_shown_under_a_bold_headline(self):
        box = MessageBox(QMessageBox.Warning, "t", "Empty every log file?",
                         informative="It cannot be undone.")
        self.addCleanup(box.deleteLater)
        box.show()
        _APP.processEvents()
        self.assertTrue(box.text.font().bold())
        self.assertTrue(box.informative.isVisible())
        self.assertGreaterEqual(box.informative.height(),
                                box.informative.heightForWidth(box.informative.width()))


if __name__ == "__main__":
    unittest.main()
