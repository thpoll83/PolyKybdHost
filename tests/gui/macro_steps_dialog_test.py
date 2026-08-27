"""MacroStepsDialog — the step table and the keystroke recorder.

Runs under the offscreen Qt platform against the real widget. The recorder is driven
with synthesised `QKeyEvent`s rather than a robot: what it has to get right is the
translation and the down/up bookkeeping, both of which a real key press only reaches
through the same `keyPressEvent`.

⚠️ The offscreen platform prints "does not support grabbing the keyboard" and carries
on. That is fine here — the grab is what stops the keystrokes reaching another widget
on a real desktop, and there is no other widget in a unit test — but it does mean these
tests cannot prove the grab works, only that it is asked for and released.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QKeyEvent
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.layout_dialog.macro_steps_dialog import (
        COL_KEY, COL_KIND, COL_MS, MacroStepsDialog,
    )
    from polyhost.services import macro_body as mb
    from polyhost.services import macro_keys as mk
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e


def setUpModule():
    """Pin the QApplication for the life of the module -- see macro_tab_test."""
    if _IMPORT_ERR is None:
        assert _APP is not None


CHORD = [mb.Step("down", code=0xE0), mb.Step("down", code=0xE1),
         mb.Step("tap", code=0x13),
         mb.Step("up", code=0xE1), mb.Step("up", code=0xE0)]


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class StepTableTest(unittest.TestCase):
    def test_what_goes_in_comes_back_out(self):
        """The widgets ARE the model, so the round trip is the whole contract."""
        steps = CHORD + [mb.Step("delay", ms=250),
                         mb.Step("char", code=ord("o")), mb.Step("char", code=ord("k"))]
        dlg = MacroStepsDialog(steps)
        self.assertEqual(dlg.steps(), steps)

    def test_the_summary_describes_the_table(self):
        dlg = MacroStepsDialog(CHORD)
        self.assertEqual(dlg.summary.text(), "Ctrl+Shift+P")

    def test_an_empty_dialog_says_so_rather_than_showing_nothing(self):
        self.assertEqual(MacroStepsDialog().summary.text(), "No steps yet.")

    def test_only_a_wait_row_gets_a_ms_box(self):
        """⚠️ `setVisible(False)` does NOT stop a table drawing a cell widget, so the
        first cut left a live spin box on every Tap row -- an edit that save discards,
        which is the shape that gets reported as "it did not keep what I typed".
        """
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04), mb.Step("delay", ms=10)])
        self.assertIsNone(dlg.table.cellWidget(0, COL_MS))
        self.assertIsNotNone(dlg.table.cellWidget(1, COL_MS))

    def test_switching_a_row_to_wait_gives_it_the_ms_box(self):
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        box = dlg.table.cellWidget(0, COL_KIND)
        box.setCurrentIndex([box.itemData(i) for i in range(box.count())].index("delay"))
        self.assertIsNotNone(dlg.table.cellWidget(0, COL_MS))
        self.assertEqual(dlg.steps(), [mb.Step("delay", ms=0)])

    def test_switching_a_wait_row_back_to_tap_takes_the_ms_box_away(self):
        """The other direction of the same rule, and the one a fresh row can never
        reach -- so without it the removal was untested and a mutation that never
        removed the box passed the whole suite.
        """
        dlg = MacroStepsDialog([mb.Step("delay", ms=10)])
        box = dlg.table.cellWidget(0, COL_KIND)
        box.setCurrentIndex([box.itemData(i) for i in range(box.count())].index("tap"))
        self.assertIsNone(dlg.table.cellWidget(0, COL_MS))
        self.assertEqual(dlg.steps(), [mb.Step("tap", code=mk.value_for("KC_A"))])

    def test_a_character_row_cannot_be_turned_into_a_keycode(self):
        """Its Key cell holds a character, not a keycode name, so letting the Action
        change would reinterpret the same cell as something else entirely."""
        dlg = MacroStepsDialog([mb.Step("char", code=ord("a"))])
        self.assertFalse(dlg.table.cellWidget(0, COL_KIND).isEnabled())

    def test_an_unnamed_keycode_survives_the_round_trip(self):
        """The firmware plays whatever byte it is handed, so a body written elsewhere
        must not be silently rewritten by opening it here."""
        dlg = MacroStepsDialog([mb.Step("tap", code=0xFD)])
        self.assertEqual(dlg.table.item(0, COL_KEY).text(), "0xFD")
        self.assertEqual(dlg.steps(), [mb.Step("tap", code=0xFD)])

    def test_reordering_moves_the_row_and_the_selection_with_it(self):
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04), mb.Step("tap", code=0x05)])
        dlg.table.selectRow(1)
        dlg._move(-1)
        self.assertEqual(dlg.steps(), [mb.Step("tap", code=0x05), mb.Step("tap", code=0x04)])
        self.assertEqual(dlg._selected(), 0)

    def test_a_move_off_either_end_is_a_no_op(self):
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        dlg.table.selectRow(0)
        dlg._move(-1)
        dlg._move(1)
        self.assertEqual(dlg.steps(), [mb.Step("tap", code=0x04)])

    def test_removing_takes_the_selected_row(self):
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04), mb.Step("tap", code=0x05)])
        dlg.table.selectRow(0)
        dlg._on_remove()
        self.assertEqual(dlg.steps(), [mb.Step("tap", code=0x05)])

    def test_accepting_publishes_the_steps(self):
        dlg = MacroStepsDialog(CHORD)
        dlg._on_accept()
        self.assertEqual(dlg.result_steps, CHORD)

    def test_the_longest_expressible_delay_survives(self):
        """65535 ms is the top of the wire format's range, so it is the value most
        likely to be lost to an off-by-one somewhere between the spin box and the bytes.

        Note what this does NOT test: `_on_accept` also re-runs `encode_steps` and
        refuses on `MacroError`, but every widget here bounds its own range (the spin to
        0..0xFFFF, `value_for` to one byte), so the table cannot currently build a body
        that fails. That guard is deliberate belt-and-braces against a future editable
        field, not a reachable path -- claiming a test for it would be claiming coverage
        of a branch nothing can enter.
        """
        dlg = MacroStepsDialog([mb.Step("delay", ms=10)])
        dlg.table.cellWidget(0, COL_MS).setValue(0xFFFF)
        dlg._on_accept()
        self.assertEqual(dlg.result_steps, [mb.Step("delay", ms=0xFFFF)])
        self.assertEqual(mb.decode(mb.encode_steps(dlg.result_steps)),
                         [mb.Step("delay", ms=0xFFFF)])


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class RecorderTest(unittest.TestCase):
    @staticmethod
    def _send(dlg, key, text="", press=True, repeat=False):
        ev = QKeyEvent(QEvent.KeyPress if press else QEvent.KeyRelease,
                       key, Qt.NoModifier, text, repeat)
        QApplication.sendEvent(dlg, ev)

    def _record(self, dlg, keys):
        dlg.record_btn.setChecked(True)
        for key, text, press in keys:
            self._send(dlg, key, text, press)
        dlg.record_btn.setChecked(False)

    def test_a_recorded_chord_is_the_chord_that_was_pressed(self):
        dlg = MacroStepsDialog()
        self._record(dlg, [
            (Qt.Key_Control, "", True), (Qt.Key_Shift, "", True),
            (Qt.Key_P, "p", True),
            (Qt.Key_P, "p", False), (Qt.Key_Shift, "", False),
            (Qt.Key_Control, "", False),
        ])
        self.assertEqual(dlg.steps(), [
            mb.Step("down", code=mk.value_for("KC_LEFT_CTRL")),
            mb.Step("down", code=mk.value_for("KC_LEFT_SHIFT")),
            mb.Step("down", code=mk.value_for("KC_P")),
            mb.Step("up", code=mk.value_for("KC_P")),
            mb.Step("up", code=mk.value_for("KC_LEFT_SHIFT")),
            mb.Step("up", code=mk.value_for("KC_LEFT_CTRL")),
        ])
        self.assertEqual(mk.describe(dlg.steps()), "Ctrl+Shift+P")

    def test_auto_repeat_is_not_recorded(self):
        """Holding a key makes the OS report it over and over; recording that fills the
        list with hundreds of rows for one key the user simply held down."""
        dlg = MacroStepsDialog()
        dlg.record_btn.setChecked(True)
        self._send(dlg, Qt.Key_A, "a", True)
        for _ in range(20):
            self._send(dlg, Qt.Key_A, "a", True, repeat=True)
        self._send(dlg, Qt.Key_A, "a", False)
        dlg.record_btn.setChecked(False)
        self.assertEqual(dlg.steps(), [mb.Step("down", code=mk.value_for("KC_A")),
                                       mb.Step("up", code=mk.value_for("KC_A"))])

    def test_escape_stops_recording_and_is_not_itself_recorded(self):
        """Esc has to stop the recorder, and it must not close the dialog out from under
        it -- either would lose whatever had been captured."""
        dlg = MacroStepsDialog()
        dlg.record_btn.setChecked(True)
        self._send(dlg, Qt.Key_A, "a", True)
        self._send(dlg, Qt.Key_Escape, "", True)
        self.assertFalse(dlg._recording)
        self.assertFalse(dlg.record_btn.isChecked())
        self.assertEqual(dlg.steps(), [mb.Step("down", code=mk.value_for("KC_A"))])

    def test_a_key_with_no_keycode_is_skipped_and_said_so(self):
        """Silently recording nothing reads as the recorder dropping keys at random."""
        dlg = MacroStepsDialog()
        dlg.record_btn.setChecked(True)
        self._send(dlg, 0x0100002F, "", True)      # unassigned, just below F1
        self.assertEqual(dlg.table.rowCount(), 0)
        self.assertIn("No basic keycode", dlg.summary.text())
        dlg.record_btn.setChecked(False)

    def test_nothing_is_captured_while_not_recording(self):
        """The dialog is an ordinary editor the rest of the time -- typing in a Key cell
        must not append steps."""
        dlg = MacroStepsDialog()
        self._send(dlg, Qt.Key_A, "a", True)
        self._send(dlg, Qt.Key_A, "a", False)
        self.assertEqual(dlg.table.rowCount(), 0)

    def test_timing_is_off_by_default(self):
        """Most macros want to run as fast as the keyboard can, and a Wait per keystroke
        is bytes on a shared buffer as well as noise in the list."""
        dlg = MacroStepsDialog()
        self.assertIs(dlg.timing_box.currentData(), False)
        self._record(dlg, [(Qt.Key_A, "a", True), (Qt.Key_A, "a", False)])
        self.assertFalse(any(s.kind == "delay" for s in dlg.steps()))

    def test_the_editing_buttons_are_dead_while_recording(self):
        """Every keystroke belongs to the macro while it is armed, so a button that
        opens a text prompt would be taking the keyboard back."""
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        dlg.table.selectRow(0)
        dlg.record_btn.setChecked(True)
        for b in (dlg.add_btn, dlg.text_btn, dlg.remove_btn, dlg.timing_box):
            self.assertFalse(b.isEnabled(), b)
        dlg.record_btn.setChecked(False)
        self.assertTrue(dlg.add_btn.isEnabled())

    def test_accepting_while_armed_stops_the_recorder_first(self):
        """Accepting must not leave the keyboard grabbed -- on a real desktop that is the app
        appearing to stop responding to the keyboard entirely."""
        dlg = MacroStepsDialog()
        dlg.record_btn.setChecked(True)
        dlg._on_accept()
        self.assertFalse(dlg._recording)

    def test_stopping_releases_the_keyboard(self):
        """Asserted as the CALL, because the offscreen platform has no grab to observe.
        That is the most these tests can prove -- but it is the half that goes wrong:
        a grab that is taken and never released leaves the whole app looking like it
        has stopped responding to the keyboard.
        """
        dlg = MacroStepsDialog()
        released = []
        dlg.releaseKeyboard = lambda: released.append(True)
        dlg.record_btn.setChecked(True)
        dlg.record_btn.setChecked(False)
        self.assertEqual(len(released), 1)

    def test_closing_while_armed_releases_the_keyboard(self):
        dlg = MacroStepsDialog()
        released = []
        dlg.releaseKeyboard = lambda: released.append(True)
        dlg.record_btn.setChecked(True)
        dlg.close()
        self.assertFalse(dlg._recording)
        self.assertEqual(len(released), 1)


if __name__ == "__main__":
    unittest.main()
