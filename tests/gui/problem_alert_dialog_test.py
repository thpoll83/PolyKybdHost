"""ProblemAlertDialog: repeats update the count, Report hands over the text.

Runs under the offscreen Qt platform against the real widget.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.problem_alert_dialog import ProblemAlertDialog
    from polyhost.services import problem_scan as ps
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e


def setUpModule():
    """Pin the QApplication for the life of the module -- see macro_tab_test."""
    if _IMPORT_ERR is None:
        assert _APP is not None


def _oled(count=1):
    return ps.Problem(ps.SOURCE_KEYBOARD, "oled_i2c", ps.SEVERITY_ERROR,
                      "The status display did not accept an update.",
                      "oled_render offset command failed", count)


@unittest.skipIf(_IMPORT_ERR is not None, f"PyQt5 unavailable: {_IMPORT_ERR}")
class ProblemAlertDialogTest(unittest.TestCase):
    def test_a_repeat_raises_the_count_instead_of_adding_a_row(self):
        d = ProblemAlertDialog()
        d.add_problem(_oled())
        d.add_problem(_oled(4))
        self.assertEqual(len(d.problems), 1)
        self.assertEqual(d.problems[0].count, 4)
        self.assertIn("seen 4×", d.detail.toPlainText())
        self.assertIn("1 problem", d.headline.text())

    def test_an_escalated_warning_takes_the_error_severity_and_sentence(self):
        d = ProblemAlertDialog()
        d.add_problem(ps.Problem(ps.SOURCE_KEYBOARD, "oled_i2c", ps.SEVERITY_WARNING,
                                 "Missed one update.", "oled_render offset command failed", 1))
        d.add_problem(ps.Problem(ps.SOURCE_KEYBOARD, "oled_i2c", ps.SEVERITY_ERROR,
                                 "Keeps rejecting updates.", "oled_render data failed", 3))
        self.assertEqual(len(d.problems), 1)
        self.assertEqual(d.problems[0].severity, ps.SEVERITY_ERROR)
        self.assertIn("[Keyboard, error] Keeps rejecting updates. (seen 3×)", d.detail.toPlainText())
        self.assertIn("oled_render data failed", d.detail.toPlainText())

    def test_report_passes_the_composed_description_and_title(self):
        got = []
        d = ProblemAlertDialog(report_cb=lambda desc, title: got.append((desc, title)))
        d.add_problem(_oled())
        d.add_problem(ps.Problem(ps.SOURCE_HOST, "x", ps.SEVERITY_ERROR, "H.", "boom"))
        d._report()
        self.assertEqual(len(got), 1)
        desc, title = got[0]
        self.assertIn("oled_render offset command failed", desc)
        self.assertIn("boom", desc)
        self.assertTrue(title.endswith("(+1 more)"))
        self.assertIn("2 problems", d.headline.text())

    def test_a_failing_report_falls_back_to_the_clipboard(self):
        def broken(desc, title):
            raise RuntimeError("no dialog")
        d = ProblemAlertDialog(report_cb=broken)
        d.add_problem(_oled())
        d._report()   # must not raise out of the slot
        self.assertIn("oled_render", QApplication.clipboard().text())
        self.assertIn("Copied", d.status.text())


if __name__ == "__main__":
    unittest.main()
