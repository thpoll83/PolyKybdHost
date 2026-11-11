"""ComboTab and TapDanceTab: loading, the slot list, saving, clearing and placing TD(n).

Runs the real widgets under the offscreen Qt platform against a stand-in core that
answers combos_get / combos_set the way PolyCore does.
"""
import os
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.layout_dialog.combo_tab import ComboTab, TapDanceTab, short_text
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e

KC_A, KC_J, KC_K, KC_ESC, KC_9 = 0x04, 0x0D, 0x0E, 0x29, 0x26
MO1 = 0x5221


def _data(available=True):
    combos = [{"slot": i, "keys": [], "result": 0} for i in range(16)]
    combos[0] = {"slot": 0, "keys": [KC_J, KC_K], "result": KC_ESC}
    tds = [{"slot": i, "on_tap": 0, "on_hold": 0, "on_double_tap": 0, "on_tap_hold": 0,
            "term_ms": 0} for i in range(16)]
    tds[2] = {"slot": 2, "on_tap": KC_A, "on_hold": MO1, "on_double_tap": 0,
              "on_tap_hold": 0, "term_ms": 250}
    return {"available": available, "combo_term_ms": 50, "combos": combos,
            "tap_dances": tds}


def _core(ok=True, data=None):
    core = mock.MagicMock()
    core.combos_get.return_value = (ok, data if data is not None else _data())
    core.combos_set.return_value = (True, {"other_half": True})
    return core


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class ComboTabTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_the_list_shows_every_slot_numbered_from_one(self):
        tab = ComboTab(_core())
        tab.reload()
        self.assertEqual(tab.list.count(), 16)
        self.assertEqual(tab.list.item(0).text(), "1: J + K → ESCAPE")
        self.assertEqual(tab.list.item(1).text(), "2: (empty)")

    def test_the_note_names_the_combo_term(self):
        tab = ComboTab(_core())
        tab.reload()
        self.assertIn("50 ms", tab.note.text())

    def test_selecting_a_slot_fills_the_fields(self):
        tab = ComboTab(_core())
        tab.reload()
        self.assertEqual(tab.key_fields[0].text(), "KC_J")
        self.assertEqual(tab.key_fields[2].text(), "")
        self.assertEqual(tab.result_field.keycode(), KC_ESC)

    def test_save_sends_only_the_edited_slot(self):
        core = _core()
        tab = ComboTab(core)
        tab.reload()
        tab.list.setCurrentRow(3)
        tab.key_fields[0].setText("KC_A")
        tab.key_fields[1].setText("s(kc_9)")
        tab.key_fields[2].setText("j")
        tab.result_field.setText("MO(1)")
        tab._on_save()
        core.combos_set.assert_called_once_with(
            combos=[{"slot": 3, "keys": [KC_A, 0x200 | KC_9, KC_J], "result": MO1}])
        self.assertTrue(tab.list.item(3).text().startswith("4: A + LSFT(9) + J"))

    @mock.patch("polyhost.gui.layout_dialog.combo_tab.message_box")
    def test_one_key_is_refused_before_anything_is_sent(self, box):
        core = _core()
        tab = ComboTab(core)
        tab.reload()
        tab.list.setCurrentRow(3)
        tab.key_fields[0].setText("KC_A")
        tab.result_field.setText("KC_ESC")
        tab._on_save()
        core.combos_set.assert_not_called()
        box.warning.assert_called_once()

    @mock.patch("polyhost.gui.layout_dialog.combo_tab.message_box")
    def test_an_unknown_name_is_refused(self, box):
        core = _core()
        tab = ComboTab(core)
        tab.reload()
        tab.key_fields[1].setText("KC_NOPE")
        tab._on_save()
        core.combos_set.assert_not_called()
        self.assertIn("KC_NOPE", box.warning.call_args[0][2])

    def test_clear_writes_an_empty_record(self):
        core = _core()
        tab = ComboTab(core)
        tab.reload()
        tab._on_clear()
        core.combos_set.assert_called_once_with(combos=[{"slot": 0, "keys": [], "result": 0}])
        self.assertEqual(tab.list.item(0).text(), "1: (empty)")
        self.assertEqual(tab.key_fields[0].text(), "")

    def test_a_build_without_the_feature_disables_the_editor(self):
        tab = ComboTab(_core(data=_data(available=False)))
        tab.reload()
        self.assertEqual(tab.list.count(), 0)
        self.assertFalse(tab.save_btn.isEnabled())
        self.assertIn("DOOM", tab.note.text())

    def test_a_refusal_from_the_core_is_shown(self):
        tab = ComboTab(_core(ok=False, data="Firmware protocol too old"))
        tab.reload()
        self.assertFalse(tab.key_fields[0].isEnabled())
        self.assertIn("too old", tab.note.text())

    def test_the_other_half_missing_is_reported(self):
        core = _core()
        core.combos_set.return_value = (True, {"other_half": False})
        tab = ComboTab(core)
        tab.reload()
        tab._on_save()
        self.assertIn("this half only", tab.note.text())


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class TapDanceTabTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_the_list_summarises_the_actions(self):
        tab = TapDanceTab(_core())
        tab.reload()
        self.assertEqual(tab.list.item(2).text(), "3: A, hold MO(1)")
        self.assertEqual(tab.list.item(0).text(), "1: (empty)")

    def test_the_term_shows_the_default_for_zero(self):
        tab = TapDanceTab(_core())
        tab.reload()
        self.assertEqual(tab.term.text(), "Tapping term")
        tab.list.setCurrentRow(2)
        self.assertEqual(tab.term.value(), 250)

    def test_save_sends_the_record(self):
        core = _core()
        tab = TapDanceTab(core)
        tab.reload()
        tab.action_fields["on_tap"].setText("KC_ESC")
        tab.action_fields["on_double_tap"].setText("LCTL(KC_A)")
        tab._on_save()
        core.combos_set.assert_called_once_with(tap_dances=[{
            "slot": 0, "on_tap": KC_ESC, "on_hold": 0, "on_double_tap": 0x100 | KC_A,
            "on_tap_hold": 0, "term_ms": 0}])

    @mock.patch("polyhost.gui.layout_dialog.combo_tab.message_box")
    def test_an_action_the_firmware_cannot_send_is_refused(self, box):
        core = _core()
        tab = TapDanceTab(core)
        tab.reload()
        tab.action_fields["on_tap"].setText("TD(1)")
        tab._on_save()
        core.combos_set.assert_not_called()
        box.warning.assert_called_once()

    @mock.patch("polyhost.gui.layout_dialog.combo_tab.message_box")
    def test_no_tap_action_is_refused(self, box):
        core = _core()
        tab = TapDanceTab(core)
        tab.reload()
        tab.action_fields["on_hold"].setText("KC_A")
        tab._on_save()
        core.combos_set.assert_not_called()

    def test_use_on_key_emits_td_of_the_slot(self):
        tab = TapDanceTab(_core())
        tab.reload()
        tab.list.setCurrentRow(2)
        got = []
        tab.keycodeSelected.connect(lambda *a: got.append(a))
        tab._on_assign()
        self.assertEqual(got, [("Tap dance 3", "TD(2)", 0x5702, 0)])


class ShortTextTest(unittest.TestCase):
    @unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
    def test_drops_the_prefix(self):
        self.assertEqual(short_text(KC_J), "J")
        self.assertEqual(short_text(0), "")
        self.assertEqual(short_text(MO1), "MO(1)")


if __name__ == "__main__":
    unittest.main()
