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
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QKeyEvent
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.layout_dialog.macro_steps_dialog import (
        COL_KIND, COL_VALUE, MIN_RECORDED_GAP_MS, VIEW_SCRIPT, VIEW_TABLE,
        MacroStepsDialog,
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

TEXT = [mb.Step("char", code=ord(c)) for c in "ok"]


def _kind_index(box, kind):
    """The combo index whose data is `kind` -- the rows offer labels, not kinds."""
    return [box.itemData(i) for i in range(box.count())].index(kind)


def _set_kind(dlg, row, kind):
    box = dlg.table.cellWidget(row, COL_KIND)
    box.setCurrentIndex(_kind_index(box, kind))


def _descends_from(widget, ancestor):
    """True when `widget` sits anywhere under `ancestor` in the widget tree."""
    node = widget
    while node is not None:
        if node is ancestor:
            return True
        node = node.parentWidget()
    return False


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class LayoutTest(unittest.TestCase):
    """Where the controls LIVE, which is the thing the tabs changed."""

    def test_two_tabs_named_for_what_they_hold(self):
        dlg = MacroStepsDialog()
        self.assertEqual([dlg.tabs.tabText(i) for i in range(dlg.tabs.count())],
                         ["Table", "Script"])

    def test_the_table_tab_comes_first(self):
        """It is the one that needs no syntax, so it is what opens."""
        self.assertEqual(MacroStepsDialog().tabs.currentIndex(), VIEW_TABLE)

    def test_the_row_buttons_live_INSIDE_the_table_tab(self):
        """They act on rows, so they belong with the rows -- in the script view they
        would be five permanently-greyed buttons taking up a footer.

        Asserted on the widget tree rather than on enabled-ness: a button can be
        disabled and still occupy the layout, which is exactly the arrangement this
        replaced.
        """
        dlg = MacroStepsDialog()
        page = dlg.tabs.widget(VIEW_TABLE)
        for btn in (dlg.add_btn, dlg.text_btn, dlg.remove_btn, dlg.up_btn, dlg.down_btn):
            self.assertTrue(_descends_from(btn, page), btn.text())

    def test_record_is_SHARED_not_on_either_tab(self):
        """It is the one control that means something in both views, so it sits outside
        them -- moving it onto the Table tab would make it unreachable while writing a
        script, which is a place people will want to capture a chord."""
        dlg = MacroStepsDialog()
        for btn in (dlg.record_btn, dlg.timing_box):
            self.assertFalse(_descends_from(btn, dlg.tabs.widget(VIEW_TABLE)), btn)
            self.assertFalse(_descends_from(btn, dlg.tabs.widget(VIEW_SCRIPT)), btn)

    def test_the_script_box_advertises_its_syntax(self):
        """Nothing else on screen says what to type, and an empty text box with no
        placeholder is indistinguishable from a broken tab."""
        dlg = MacroStepsDialog()
        self.assertIn("{", dlg.script.placeholderText())
        self.assertIn("tap", dlg.script.toolTip())

    def test_the_table_is_TWO_columns_an_action_and_its_value(self):
        """One value column, not Key plus ms.

        With two, every row showed the editor its kind cannot use -- and both accepted
        an entry that was dropped on save, which is exactly the edit that gets reported
        as "it did not keep what I typed". A third column would have to mean a third
        thing a step can carry, and there isn't one.
        """
        dlg = MacroStepsDialog()
        head = dlg.table.horizontalHeader()
        titles = [dlg.table.horizontalHeaderItem(i).text()
                  for i in range(dlg.table.columnCount())]
        self.assertEqual(titles, ["Action", "Value"])
        self.assertGreater(dlg.table.columnWidth(COL_KIND), 0)
        self.assertIsNotNone(head)


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class RowEditingTest(unittest.TestCase):
    """Adding, editing and reordering rows -- the gestures the Table tab exists for."""

    def test_add_with_nothing_selected_appends(self):
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        dlg.table.clearSelection()
        dlg._on_add()
        self.assertEqual(dlg.table.rowCount(), 2)
        self.assertEqual(dlg._selected(), 1)

    def test_add_inserts_AFTER_the_selected_row(self):
        """Appending to the end would be wrong for the common case: you notice a missing
        Hold in the middle of a chord, select the row it belongs after, and add."""
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04), mb.Step("tap", code=0x05)])
        dlg.table.selectRow(0)
        dlg._on_add()
        self.assertEqual(dlg.table.rowCount(), 3)
        self.assertEqual(dlg._selected(), 1)
        self.assertEqual([s.code for s in dlg.steps()],
                         [0x04, mk.value_for("KC_A"), 0x05])

    def test_a_new_row_is_a_tap_of_a_real_key(self):
        """An empty Key cell would read back as keycode 0, which is not a key -- so a
        fresh row has to start from something the keyboard can actually send."""
        dlg = MacroStepsDialog()
        dlg._on_add()
        self.assertEqual(dlg.steps(), [mb.Step("tap", code=mk.value_for("KC_A"))])

    def test_typing_a_keycode_name_into_the_key_cell_changes_the_step(self):
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        dlg.table.item(0, COL_VALUE).setText("KC_ENTER")
        self.assertEqual(dlg.steps(), [mb.Step("tap", code=mk.value_for("KC_ENTER"))])

    def test_a_short_alias_is_accepted_in_the_key_cell(self):
        """`KC_LSFT` is what a VIA user types and what the script view accepts; the
        table must not be the one place that rejects it."""
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        dlg.table.item(0, COL_VALUE).setText("KC_LSFT")
        self.assertEqual(dlg.steps(), [mb.Step("tap", code=mk.value_for("KC_LEFT_SHIFT"))])

    def test_a_raw_hex_keycode_is_accepted_in_the_value_cell(self):
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        dlg.table.item(0, COL_VALUE).setText("0xFD")
        self.assertEqual(dlg.steps(), [mb.Step("tap", code=0xFD)])

    def test_changing_the_action_KEEPS_the_key(self):
        """Turning a Tap into a Hold is the commonest edit there is, and re-typing the
        keycode afterwards would make it the most annoying."""
        dlg = MacroStepsDialog([mb.Step("tap", code=mk.value_for("KC_LEFT_CTRL"))])
        _set_kind(dlg, 0, "down")
        self.assertEqual(dlg.steps(),
                         [mb.Step("down", code=mk.value_for("KC_LEFT_CTRL"))])

    def test_a_wait_rows_value_cell_is_not_editable(self):
        """A Wait has no key, so an entry there is one save discards silently."""
        dlg = MacroStepsDialog([mb.Step("delay", ms=10)])
        self.assertFalse(dlg.table.item(0, COL_VALUE).flags() & Qt.ItemIsEditable)

    def test_a_keycode_rows_value_cell_IS_editable(self):
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        self.assertTrue(dlg.table.item(0, COL_VALUE).flags() & Qt.ItemIsEditable)

    def test_a_wait_row_offers_NO_PLACE_to_type_a_keycode(self):
        """The point of one value column: the editor a Wait cannot use is not merely
        greyed, it is not there.

        With Key and ms side by side a Wait row still showed an empty Key cell, and it
        took an entry that the save then dropped -- the reader's complaint that started
        this. Here the spin box IS the cell, and the item under it is blank.
        """
        dlg = MacroStepsDialog([mb.Step("delay", ms=10)])
        self.assertIsNotNone(dlg.table.cellWidget(0, COL_VALUE))     # the spin box
        self.assertEqual(dlg.table.item(0, COL_VALUE).text(), "")
        self.assertFalse(dlg.table.item(0, COL_VALUE).flags() & Qt.ItemIsEditable)

    def test_a_keycode_row_offers_NO_PLACE_to_type_a_duration(self):
        """The same rule the other way round.

        A Tap's spare ms cell used to hold no widget and no item -- and was still
        editable, because an empty QTableWidget cell opens an editor on a double-click.
        `steps()` never read it, so the number went nowhere. There is no tap-with-a-
        duration in the format for it to have gone to.
        """
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        self.assertIsNone(dlg.table.cellWidget(0, COL_VALUE))
        self.assertTrue(dlg.table.item(0, COL_VALUE).flags() & Qt.ItemIsEditable)

    def test_both_editors_live_in_the_SAME_column(self):
        """A duration and a keycode are the same thing -- what this action acts on --
        so they share one column, and that is what lets the header name it."""
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04), mb.Step("delay", ms=10)])
        self.assertEqual(dlg.table.columnCount(), 2)
        self.assertIsNotNone(dlg.table.item(0, COL_VALUE).text())
        self.assertIsNotNone(dlg.table.cellWidget(1, COL_VALUE))

    def test_a_row_that_was_a_WAIT_can_be_typed_into_again(self):
        """The re-editable flag only matters on the way BACK.

        A fresh `QTableWidgetItem` is editable already, so the `|= ItemIsEditable` in
        `_sync_row` does nothing on a new row and everything on a row the Wait branch
        has cleared. Found by mutation: deleting that line left the whole suite green
        while a row that had once been a Wait could never be given a keycode again.
        """
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        _set_kind(dlg, 0, "delay")
        _set_kind(dlg, 0, "tap")
        self.assertTrue(dlg.table.item(0, COL_VALUE).flags() & Qt.ItemIsEditable)
        dlg.table.item(0, COL_VALUE).setText("KC_ENTER")
        self.assertEqual(dlg.steps(), [mb.Step("tap", code=mk.value_for("KC_ENTER"))])

    def test_a_keycode_is_NOT_remembered_across_a_trip_through_wait(self):
        """Deliberate, and the alternative would be HALF a feature.

        Hiding the keycode under the spin box so the switch back restores it works only
        until the row is moved: `_move` and the tab switch rebuild from `steps()`, where
        a Wait carries a duration and nothing else. Remembering it in one path and not
        the other is worse than never remembering.
        """
        dlg = MacroStepsDialog([mb.Step("tap", code=mk.value_for("KC_ENTER"))])
        _set_kind(dlg, 0, "delay")
        _set_kind(dlg, 0, "tap")
        self.assertEqual(dlg.steps(), [mb.Step("tap", code=mk.value_for("KC_A"))])

    def test_changing_the_ms_box_changes_the_step(self):
        dlg = MacroStepsDialog([mb.Step("delay", ms=10)])
        dlg.table.cellWidget(0, COL_VALUE).setValue(400)
        self.assertEqual(dlg.steps(), [mb.Step("delay", ms=400)])

    def test_the_ms_box_is_bounded_to_what_the_format_holds(self):
        """The wire format stores the delay as ASCII digits the firmware caps at 65535,
        so a spin box that went higher would offer a value that silently truncates."""
        dlg = MacroStepsDialog([mb.Step("delay", ms=10)])
        spin = dlg.table.cellWidget(0, COL_VALUE)
        self.assertEqual((spin.minimum(), spin.maximum()), (0, 0xFFFF))

    def test_remove_with_nothing_selected_is_a_no_op(self):
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        dlg.table.clearSelection()
        dlg._on_remove()
        self.assertEqual(dlg.table.rowCount(), 1)

    def test_the_row_buttons_are_dead_with_no_selection(self):
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        dlg.table.clearSelection()
        dlg._refresh_buttons()
        for b in (dlg.remove_btn, dlg.up_btn, dlg.down_btn):
            self.assertFalse(b.isEnabled(), b.text())
        for b in (dlg.add_btn, dlg.text_btn):
            self.assertTrue(b.isEnabled(), b.text())

    def test_reordering_across_kinds_keeps_each_rows_own_editor(self):
        """A move rebuilds the table from the steps, so the ms box has to follow the
        Wait row rather than the position it used to be in."""
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04), mb.Step("delay", ms=99)])
        dlg.table.selectRow(1)
        dlg._move(-1)
        self.assertIsNotNone(dlg.table.cellWidget(0, COL_VALUE))
        self.assertIsNone(dlg.table.cellWidget(1, COL_VALUE))
        self.assertEqual(dlg.steps(), [mb.Step("delay", ms=99), mb.Step("tap", code=0x04)])


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class AddTextTest(unittest.TestCase):
    """`Add text…` turns a typed run into one Type row per character."""

    @staticmethod
    def _answer(dlg, text, accepted=True):
        with patch("polyhost.gui.layout_dialog.macro_steps_dialog.QInputDialog.getText",
                   return_value=(text, accepted)):
            dlg._on_add_text()

    def test_each_character_becomes_its_own_row(self):
        dlg = MacroStepsDialog()
        self._answer(dlg, "hi")
        self.assertEqual(dlg.steps(), [mb.Step("char", code=ord("h")),
                                       mb.Step("char", code=ord("i"))])

    def test_the_run_is_inserted_in_ORDER_after_the_selection(self):
        """Inserting each character at the same index would reverse the word -- the
        classic off-by-loop, and one a single-character fixture cannot catch."""
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04), mb.Step("tap", code=0x05)])
        dlg.table.selectRow(0)
        self._answer(dlg, "abc")
        self.assertEqual([s.code for s in dlg.steps()],
                         [0x04, ord("a"), ord("b"), ord("c"), 0x05])

    def test_cancelling_adds_nothing(self):
        dlg = MacroStepsDialog()
        self._answer(dlg, "hi", accepted=False)
        self.assertEqual(dlg.table.rowCount(), 0)

    def test_an_empty_answer_adds_nothing(self):
        dlg = MacroStepsDialog()
        self._answer(dlg, "")
        self.assertEqual(dlg.table.rowCount(), 0)

    def test_text_the_keyboard_cannot_type_is_REFUSED_not_partly_added(self):
        """The refusal has to happen before any row lands, or a rejected word leaves
        half of itself behind -- which is the silent-truncation failure `encode_text`
        exists to prevent, reintroduced one layer up.
        """
        dlg = MacroStepsDialog()
        self._answer(dlg, "café")
        self.assertEqual(dlg.table.rowCount(), 0)
        self.assertIn("macro", dlg.summary.text().lower())


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
        self.assertIsNone(dlg.table.cellWidget(0, COL_VALUE))
        self.assertIsNotNone(dlg.table.cellWidget(1, COL_VALUE))

    def test_switching_a_row_to_wait_gives_it_the_ms_box(self):
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        box = dlg.table.cellWidget(0, COL_KIND)
        box.setCurrentIndex([box.itemData(i) for i in range(box.count())].index("delay"))
        self.assertIsNotNone(dlg.table.cellWidget(0, COL_VALUE))
        self.assertEqual(dlg.steps(), [mb.Step("delay", ms=0)])

    def test_switching_a_wait_row_back_to_tap_takes_the_ms_box_away(self):
        """The other direction of the same rule, and the one a fresh row can never
        reach -- so without it the removal was untested and a mutation that never
        removed the box passed the whole suite.
        """
        dlg = MacroStepsDialog([mb.Step("delay", ms=10)])
        box = dlg.table.cellWidget(0, COL_KIND)
        box.setCurrentIndex([box.itemData(i) for i in range(box.count())].index("tap"))
        self.assertIsNone(dlg.table.cellWidget(0, COL_VALUE))
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
        self.assertEqual(dlg.table.item(0, COL_VALUE).text(), "0xFD")
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
        dlg.table.cellWidget(0, COL_VALUE).setValue(0xFFFF)
        dlg._on_accept()
        self.assertEqual(dlg.result_steps, [mb.Step("delay", ms=0xFFFF)])
        self.assertEqual(mb.decode(mb.encode_steps(dlg.result_steps)),
                         [mb.Step("delay", ms=0xFFFF)])


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class ScriptViewTest(unittest.TestCase):
    """Two views over one macro. What matters is that switching cannot lose or change
    it -- the toggle converts through `macro_script` on every flip."""

    def test_the_table_converts_to_a_script(self):
        dlg = MacroStepsDialog(CHORD)
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        self.assertEqual(dlg.script.toPlainText(),
                         "{+KC_LEFT_CTRL}{+KC_LEFT_SHIFT}{KC_P}"
                         "{-KC_LEFT_SHIFT}{-KC_LEFT_CTRL}")

    def test_steps_answers_for_whichever_view_is_live(self):
        """Both views are readable through the same method, so nothing downstream --
        save, the summary, the accept check -- has to know which one is showing."""
        dlg = MacroStepsDialog(CHORD)
        self.assertEqual(dlg.steps(), CHORD)
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        self.assertEqual(dlg.steps(), CHORD)

    def test_a_script_typed_by_hand_becomes_rows(self):
        dlg = MacroStepsDialog()
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        dlg.script.setPlainText("{+KC_LCTL}{KC_A}{-KC_LCTL}{50}hi")
        dlg.tabs.setCurrentIndex(VIEW_TABLE)
        self.assertEqual(dlg.table.rowCount(), 6)
        self.assertEqual(mk.describe(dlg.steps()), 'Ctrl+A  ·  50 ms  ·  "hi"')

    def test_a_broken_script_KEEPS_THE_TEXT_and_stays_put(self):
        """The moment the user most wants to see what they typed is the moment it does
        not parse. Converting "as far as it got" would discard the rest and clearing it
        would discard all of it, so the switch is refused and the box is put back.
        """
        dlg = MacroStepsDialog()
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        dlg.script.setPlainText("{KC_WAT}")
        dlg.tabs.setCurrentIndex(VIEW_TABLE)
        self.assertEqual(dlg.tabs.currentIndex(), VIEW_SCRIPT)
        self.assertEqual(dlg.tabs.currentIndex(), VIEW_SCRIPT)
        self.assertEqual(dlg.script.toPlainText(), "{KC_WAT}")
        self.assertIn("KC_WAT", dlg.summary.text())

    def test_accepting_a_broken_script_refuses_rather_than_saving_nothing(self):
        dlg = MacroStepsDialog()
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        dlg.script.setPlainText("{KC_WAT}")
        dlg._on_accept()
        self.assertEqual(dlg.result_steps, [])
        self.assertIn("KC_WAT", dlg.summary.text())

    def test_the_row_buttons_are_dead_in_the_script_view(self):
        """They act on the table; in the script view the equivalent gesture is typing."""
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        dlg.table.selectRow(0)
        self.assertTrue(dlg.add_btn.isEnabled())
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        for b in (dlg.add_btn, dlg.text_btn, dlg.remove_btn, dlg.up_btn, dlg.down_btn):
            self.assertFalse(b.isEnabled(), b)

    def test_a_round_trip_through_both_views_changes_nothing(self):
        steps = CHORD + [mb.Step("delay", ms=120)] + \
            [mb.Step("char", code=ord(c)) for c in "a{b"]
        dlg = MacroStepsDialog(steps)
        for _ in range(3):
            dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
            dlg.tabs.setCurrentIndex(VIEW_TABLE)
        self.assertEqual(dlg.steps(), steps)


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

    def test_recording_appends_to_the_SCRIPT_view_when_that_is_showing(self):
        """Capturing a chord and then hand-editing it as text is a normal thing to
        want, so Record works in both views -- and routing it through one append is
        what stops the two views disagreeing about what was just captured.
        """
        dlg = MacroStepsDialog()
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        self._record(dlg, [(Qt.Key_Control, "", True), (Qt.Key_X, "x", True),
                           (Qt.Key_X, "x", False), (Qt.Key_Control, "", False)])
        self.assertEqual(dlg.script.toPlainText(),
                         "{+KC_LEFT_CTRL}{+KC_X}{-KC_X}{-KC_LEFT_CTRL}")
        self.assertEqual(dlg.table.rowCount(), 0, "it also wrote into the hidden table")

    def test_the_view_cannot_be_switched_mid_recording(self):
        dlg = MacroStepsDialog()
        dlg.record_btn.setChecked(True)
        self.assertFalse(dlg.tabs.tabBar().isEnabled())
        dlg.record_btn.setChecked(False)
        self.assertTrue(dlg.tabs.tabBar().isEnabled())

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


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class ScriptEditingTest(unittest.TestCase):
    """The Script tab as a live editor, not just a conversion target."""

    @staticmethod
    def _script(text=""):
        dlg = MacroStepsDialog()
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        dlg.script.setPlainText(text)
        return dlg

    def test_the_summary_follows_the_script_as_it_is_typed(self):
        """It follows the table already; the script view was the one place where the
        summary described something other than what was on screen."""
        dlg = self._script("{+KC_LCTL}{KC_A}{-KC_LCTL}")
        self.assertEqual(dlg.summary.text(), "Ctrl+A")

    def test_a_broken_script_reports_ITSELF_in_the_summary_line(self):
        """One line, doing both jobs: describing a good script and naming a bad one.
        A separate error label would be blank almost always."""
        dlg = self._script("{KC_WAT}")
        self.assertIn("KC_WAT", dlg.summary.text())

    def test_the_summary_recovers_when_the_script_is_fixed(self):
        """An error that sticks after the text is corrected trains people to ignore
        the line entirely."""
        dlg = self._script("{KC_WAT}")
        dlg.script.setPlainText("{KC_A}")
        self.assertEqual(dlg.summary.text(), "A")

    def test_an_empty_script_reads_as_empty_not_as_an_error(self):
        dlg = self._script("")
        self.assertEqual(dlg.summary.text(), "No steps yet.")

    def test_a_script_of_plain_text_needs_no_syntax_at_all(self):
        dlg = self._script("hello")
        self.assertEqual(dlg.steps(), [mb.Step("char", code=ord(c)) for c in "hello"])

    def test_a_pasted_VIA_script_with_short_names_converts_to_rows(self):
        """The point of borrowing VIA's syntax: text from the other app lands here."""
        dlg = self._script("{+KC_LSFT}{KC_1}{-KC_LSFT}")
        dlg.tabs.setCurrentIndex(VIEW_TABLE)
        self.assertEqual(dlg.steps(),
                         [mb.Step("down", code=mk.value_for("KC_LEFT_SHIFT")),
                          mb.Step("tap", code=mk.value_for("KC_1")),
                          mb.Step("up", code=mk.value_for("KC_LEFT_SHIFT"))])

    def test_switching_to_script_from_an_EMPTY_table_gives_empty_text(self):
        """Not the placeholder, and not a stale value from a previous macro."""
        dlg = MacroStepsDialog()
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        self.assertEqual(dlg.script.toPlainText(), "")

    def test_a_table_edit_reaches_the_script_on_the_next_switch(self):
        """The conversion runs on every flip, so the script cannot be a stale snapshot
        of the table as it was the first time it was shown."""
        dlg = MacroStepsDialog([mb.Step("tap", code=0x04)])
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        dlg.tabs.setCurrentIndex(VIEW_TABLE)
        dlg.table.item(0, COL_VALUE).setText("KC_ENTER")
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        self.assertEqual(dlg.script.toPlainText(), "{KC_ENTER}")


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class RecorderTimingTest(unittest.TestCase):
    """The `with timing` option, driven through a scripted clock.

    `QElapsedTimer.restart()` is what `_capture` measures gaps with, so replacing it is
    the only way to test the threshold without sleeping -- and a test that sleeps for
    real is a test that is flaky on a loaded machine.
    """

    class FakeClock:
        def __init__(self, gaps):
            self._gaps = list(gaps)

        def restart(self):
            return self._gaps.pop(0) if self._gaps else 0

    def _record(self, dlg, gaps, keys):
        dlg.record_btn.setChecked(True)
        # AFTER the toggle: arming calls `restart()` on whatever clock is installed, so
        # a fake set beforehand would lose its first gap to that call.
        dlg._clock = self.FakeClock(gaps)
        for key, text, press in keys:
            QApplication.sendEvent(dlg, QKeyEvent(
                QEvent.KeyPress if press else QEvent.KeyRelease,
                key, Qt.NoModifier, text, False))
        dlg.record_btn.setChecked(False)

    def test_a_long_gap_becomes_a_wait_step(self):
        dlg = MacroStepsDialog()
        dlg.timing_box.setCurrentIndex(1)                 # with timing
        self._record(dlg, [0, 500, 0], [
            (Qt.Key_A, "a", True), (Qt.Key_A, "a", False),
            (Qt.Key_B, "b", True)])
        kinds = [s.kind for s in dlg.steps()]
        self.assertIn("delay", kinds)
        delay = next(s for s in dlg.steps() if s.kind == "delay")
        self.assertEqual(delay.ms, 500)

    def test_a_short_gap_does_NOT(self):
        """Below the threshold the gap is the user typing, not a pause they meant -- and
        a Wait per keystroke is both noise in the list and bytes out of a shared store.
        """
        dlg = MacroStepsDialog()
        dlg.timing_box.setCurrentIndex(1)
        self._record(dlg, [0, MIN_RECORDED_GAP_MS - 1, 0], [
            (Qt.Key_A, "a", True), (Qt.Key_A, "a", False),
            (Qt.Key_B, "b", True)])
        self.assertFalse(any(s.kind == "delay" for s in dlg.steps()))

    def test_the_FIRST_key_never_gets_a_leading_wait(self):
        """The clock has been running since Record was pressed, so the first gap is how
        long the user took to start -- which is not part of the macro."""
        dlg = MacroStepsDialog()
        dlg.timing_box.setCurrentIndex(1)
        self._record(dlg, [9999], [(Qt.Key_A, "a", True)])
        self.assertEqual([s.kind for s in dlg.steps()], ["down"])

    def test_a_long_gap_is_ignored_with_timing_OFF(self):
        dlg = MacroStepsDialog()
        self.assertIs(dlg.timing_box.currentData(), False)
        self._record(dlg, [0, 5000, 0], [
            (Qt.Key_A, "a", True), (Qt.Key_A, "a", False),
            (Qt.Key_B, "b", True)])
        self.assertFalse(any(s.kind == "delay" for s in dlg.steps()))

    def test_a_gap_longer_than_the_format_holds_is_clamped(self):
        """65535 ms is the ceiling; a longer pause has to become the longest expressible
        wait rather than an encode failure at save time."""
        dlg = MacroStepsDialog()
        dlg.timing_box.setCurrentIndex(1)
        self._record(dlg, [0, 200000, 0], [
            (Qt.Key_A, "a", True), (Qt.Key_A, "a", False),
            (Qt.Key_B, "b", True)])
        delay = next(s for s in dlg.steps() if s.kind == "delay")
        self.assertEqual(delay.ms, 0xFFFF)

    def test_the_clamp_is_what_keeps_a_long_pause_out_of_the_SCRIPT_view(self):
        """⚠️ The table cannot show this: its spin box is bounded 0..0xFFFF, so it
        clamps an over-long gap whether or not `_capture` does — and a test that only
        records into the table passes with the clamp deleted.

        In the script view the step is formatted straight to text, so an unclamped gap
        writes `{200000}` — which the parser then refuses, turning a recording into a
        script the dialog will not accept.
        """
        dlg = MacroStepsDialog()
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        dlg.timing_box.setCurrentIndex(1)
        self._record(dlg, [0, 200000, 0], [
            (Qt.Key_A, "a", True), (Qt.Key_A, "a", False),
            (Qt.Key_B, "b", True)])
        self.assertIn("{65535}", dlg.script.toPlainText())
        dlg._on_accept()                       # the script must still be acceptable
        self.assertTrue(any(s.kind == "delay" for s in dlg.result_steps))


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class RecorderStateTest(unittest.TestCase):
    def test_the_button_says_what_it_will_do(self):
        dlg = MacroStepsDialog()
        self.assertEqual(dlg.record_btn.text(), "Record")
        dlg.record_btn.setChecked(True)
        self.assertEqual(dlg.record_btn.text(), "Stop")
        dlg.record_btn.setChecked(False)
        self.assertEqual(dlg.record_btn.text(), "Record")

    def test_the_step_count_restarts_with_each_session(self):
        """It counts THIS capture, not the macro -- a running total would read as "you
        recorded 40 steps" for a two-key chord appended to an existing macro."""
        dlg = MacroStepsDialog()
        for _ in range(2):
            dlg.record_btn.setChecked(True)
            QApplication.sendEvent(dlg, QKeyEvent(
                QEvent.KeyPress, Qt.Key_A, Qt.NoModifier, "a", False))
            self.assertIn("1 step", dlg.summary.text())
            dlg.record_btn.setChecked(False)

    def test_stopping_restores_the_ordinary_summary(self):
        """The recording line is progress, not a result -- leaving it up would describe
        the macro as "Recording…" for as long as the dialog is open."""
        dlg = MacroStepsDialog()
        dlg.record_btn.setChecked(True)
        QApplication.sendEvent(dlg, QKeyEvent(
            QEvent.KeyPress, Qt.Key_A, Qt.NoModifier, "a", False))
        dlg.record_btn.setChecked(False)
        self.assertNotIn("Recording", dlg.summary.text())
        self.assertEqual(dlg.summary.text(), "hold A")


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class ResultTest(unittest.TestCase):
    """What leaves the dialog. `result_steps` is the entire output contract."""

    def test_cancelling_publishes_nothing(self):
        dlg = MacroStepsDialog(CHORD)
        dlg.reject()
        self.assertEqual(dlg.result_steps, [])

    def test_accepting_from_the_script_tab_publishes_the_parsed_steps(self):
        dlg = MacroStepsDialog()
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        dlg.script.setPlainText("{+KC_LCTL}{KC_A}{-KC_LCTL}")
        dlg._on_accept()
        self.assertEqual(dlg.result_steps,
                         [mb.Step("down", code=mk.value_for("KC_LEFT_CTRL")),
                          mb.Step("tap", code=mk.value_for("KC_A")),
                          mb.Step("up", code=mk.value_for("KC_LEFT_CTRL"))])

    def test_an_empty_macro_is_a_valid_result(self):
        """Clearing every step is how a macro is emptied from here; refusing it would
        leave no way to do that but Cancel, which keeps the old body."""
        dlg = MacroStepsDialog()
        dlg._on_accept()
        self.assertEqual(dlg.result_steps, [])

    def test_every_step_kind_survives_the_whole_dialog(self):
        """Open, flip both ways, accept -- then encode as the keyboard would. A view
        that round-trips through itself but loses a kind on the wire still loses it."""
        steps = (CHORD + [mb.Step("delay", ms=250)] + TEXT +
                 [mb.Step("char", code=ord("{")), mb.Step("tap", code=0xFD)])
        dlg = MacroStepsDialog(steps)
        dlg.tabs.setCurrentIndex(VIEW_SCRIPT)
        dlg.tabs.setCurrentIndex(VIEW_TABLE)
        dlg._on_accept()
        self.assertEqual(dlg.result_steps, steps)
        self.assertEqual(mb.decode(mb.encode_steps(dlg.result_steps)), steps)


if __name__ == "__main__":
    unittest.main()
