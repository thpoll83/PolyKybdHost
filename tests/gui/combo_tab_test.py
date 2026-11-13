"""ComboTab and TapDanceTab: loading, the slot list, saving, clearing and placing TD(n).

Runs the real widgets under the offscreen Qt platform against a stand-in core that
answers combos_get / combos_set the way PolyCore does.
"""
import os
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Only a missing PyQt5 skips: an import error in the editor itself must fail the run.
try:
    from PyQt5.QtWidgets import QApplication
    _IMPORT_ERR = None
except ImportError as e:  # pragma: no cover
    _IMPORT_ERR = e
if _IMPORT_ERR is None:
    from polyhost.gui.layout_dialog.combo_tab import ComboTab, TapDanceTab, short_text

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
    core.get_status.return_value = {"connected": True, "safe_mode": False,
                                    "capabilities": {"combos": True}}
    return core


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class ComboTabTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_the_list_shows_every_slot_numbered_from_one(self):
        tab = ComboTab(_core())
        tab.reload()
        tab._fetcher.wait_idle()
        self.assertEqual(tab.list.count(), 16)
        self.assertEqual(tab.list.item(0).text(), "1: J + K → ESCAPE")
        self.assertEqual(tab.list.item(1).text(), "2: (empty)")

    def test_the_keyboard_is_read_off_the_gui_thread(self):
        """A read is up to 33 round trips, and an RPC in client mode has no timeout."""
        import threading
        core = _core()
        seen = []
        release = threading.Event()

        def slow_get():
            seen.append(threading.current_thread() is threading.main_thread())
            release.wait(5)
            return (True, _data())
        core.combos_get.side_effect = slow_get
        tab = ComboTab(core)
        tab.reload()
        self.assertFalse(tab.save_btn.isEnabled())
        self.assertIn("Reading", tab.note.text())
        release.set()
        tab._fetcher.wait_idle()
        self.assertEqual(seen, [False])
        self.assertTrue(tab.save_btn.isEnabled())
        self.assertEqual(tab.list.count(), 16)

    def test_an_exception_from_the_core_is_shown(self):
        core = _core()
        core.combos_get.side_effect = ConnectionError("daemon gone")
        tab = ComboTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        self.assertIn("daemon gone", tab.note.text())
        self.assertFalse(tab.save_btn.isEnabled())

    def test_older_firmware_is_explained_without_a_device_call(self):
        core = _core()
        core.get_status.return_value = {"connected": True, "safe_mode": False,
                                        "capabilities": {"combos": False}}
        tab = ComboTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        core.combos_get.assert_not_called()
        self.assertIn("protocol 33", tab.note.text())
        self.assertFalse(tab.save_btn.isEnabled())

    def test_a_refusal_after_a_stale_status_still_gets_the_translated_text(self):
        core = _core(ok=False, data="Firmware protocol too old for combos")
        core.get_status.side_effect = [
            {"connected": True, "safe_mode": False, "capabilities": {"combos": True}},
            {"connected": True, "safe_mode": False, "capabilities": {"combos": False}},
        ]
        tab = ComboTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        self.assertIn("protocol 33", tab.note.text())

    def test_restricted_mode_is_explained(self):
        core = _core()
        core.get_status.return_value = {"connected": True, "safe_mode": True,
                                        "capabilities": {"combos": False}}
        tab = ComboTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        core.combos_get.assert_not_called()
        self.assertIn("restricted mode", tab.note.text())

    def test_no_keyboard_is_explained(self):
        core = _core()
        core.get_status.return_value = {"connected": False}
        tab = ComboTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        self.assertIn("not connected", tab.note.text())

    def test_the_note_names_the_combo_term(self):
        tab = ComboTab(_core())
        tab.reload()
        tab._fetcher.wait_idle()
        self.assertIn("50 ms", tab.note.text())

    def test_selecting_a_slot_fills_the_fields(self):
        tab = ComboTab(_core())
        tab.reload()
        tab._fetcher.wait_idle()
        self.assertEqual(tab.key_fields[0].text(), "KC_J")
        self.assertEqual(tab.key_fields[2].text(), "")
        self.assertEqual(tab.result_field.keycode(), KC_ESC)

    def test_save_sends_only_the_edited_slot(self):
        core = _core()
        tab = ComboTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        tab.list.setCurrentRow(3)
        tab.key_fields[0].setText("KC_A")
        tab.key_fields[1].setText("s(kc_9)")
        tab.key_fields[2].setText("j")
        tab.result_field.setText("MO(1)")
        tab._on_save()
        tab._fetcher.wait_idle()
        core.combos_set.assert_called_once_with(
            combos=[{"slot": 3, "keys": [KC_A, 0x200 | KC_9, KC_J], "result": MO1}])
        self.assertTrue(tab.list.item(3).text().startswith("4: A + LSFT(9) + J"))

    @mock.patch("polyhost.gui.layout_dialog.combo_tab.message_box")
    def test_one_key_is_refused_before_anything_is_sent(self, box):
        core = _core()
        tab = ComboTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        tab.list.setCurrentRow(3)
        tab.key_fields[0].setText("KC_A")
        tab.result_field.setText("KC_ESC")
        tab._on_save()
        tab._fetcher.wait_idle()
        core.combos_set.assert_not_called()
        box.warning.assert_called_once()

    @mock.patch("polyhost.gui.layout_dialog.combo_tab.message_box")
    def test_an_unknown_name_is_refused(self, box):
        core = _core()
        tab = ComboTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        tab.key_fields[1].setText("KC_NOPE")
        tab._on_save()
        tab._fetcher.wait_idle()
        core.combos_set.assert_not_called()
        self.assertIn("KC_NOPE", box.warning.call_args[0][2])

    def test_clear_writes_an_empty_record(self):
        core = _core()
        tab = ComboTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        tab._on_clear()
        tab._fetcher.wait_idle()
        core.combos_set.assert_called_once_with(combos=[{"slot": 0, "keys": [], "result": 0}])
        self.assertEqual(tab.list.item(0).text(), "1: (empty)")
        self.assertEqual(tab.key_fields[0].text(), "")

    def test_a_build_without_the_feature_disables_the_editor(self):
        tab = ComboTab(_core(data=_data(available=False)))
        tab.reload()
        tab._fetcher.wait_idle()
        self.assertEqual(tab.list.count(), 0)
        self.assertFalse(tab.save_btn.isEnabled())
        self.assertIn("DOOM", tab.note.text())

    def test_a_refusal_from_the_core_is_shown(self):
        tab = ComboTab(_core(ok=False, data="Firmware protocol too old"))
        tab.reload()
        tab._fetcher.wait_idle()
        self.assertFalse(tab.key_fields[0].isEnabled())
        self.assertIn("too old", tab.note.text())

    def test_the_other_half_missing_is_reported(self):
        core = _core()
        core.combos_set.return_value = (True, {"other_half": False})
        tab = ComboTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        tab._on_save()
        tab._fetcher.wait_idle()
        self.assertIn("this half only", tab.note.text())


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class TapDanceTabTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_the_summary_shows_the_tap_hold_action(self):
        data = _data()
        data["tap_dances"][4] = {"slot": 4, "on_tap": KC_A, "on_hold": 0, "on_double_tap": 0,
                                 "on_tap_hold": KC_ESC, "term_ms": 0}
        tab = TapDanceTab(_core(data=data))
        tab.reload()
        tab._fetcher.wait_idle()
        self.assertEqual(tab.list.item(4).text(), "5: A, tap, then hold ESCAPE")

    def test_the_list_summarises_the_actions(self):
        tab = TapDanceTab(_core())
        tab.reload()
        tab._fetcher.wait_idle()
        self.assertEqual(tab.list.item(2).text(), "3: A, hold MO(1)")
        self.assertEqual(tab.list.item(0).text(), "1: (empty)")

    def test_the_term_shows_the_default_for_zero(self):
        tab = TapDanceTab(_core())
        tab.reload()
        tab._fetcher.wait_idle()
        self.assertEqual(tab.term.text(), "Tapping term")
        tab.list.setCurrentRow(2)
        self.assertEqual(tab.term.value(), 250)

    def test_save_sends_the_record(self):
        core = _core()
        tab = TapDanceTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        tab.action_fields["on_tap"].setText("KC_ESC")
        tab.action_fields["on_double_tap"].setText("LCTL(KC_A)")
        tab._on_save()
        tab._fetcher.wait_idle()
        core.combos_set.assert_called_once_with(tap_dances=[{
            "slot": 0, "on_tap": KC_ESC, "on_hold": 0, "on_double_tap": 0x100 | KC_A,
            "on_tap_hold": 0, "term_ms": 0}])

    @mock.patch("polyhost.gui.layout_dialog.combo_tab.message_box")
    def test_an_action_the_firmware_cannot_send_is_refused(self, box):
        core = _core()
        tab = TapDanceTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        tab.action_fields["on_tap"].setText("TD(1)")
        tab._on_save()
        tab._fetcher.wait_idle()
        core.combos_set.assert_not_called()
        box.warning.assert_called_once()

    @mock.patch("polyhost.gui.layout_dialog.combo_tab.message_box")
    def test_no_action_is_refused(self, box):
        core = _core()
        tab = TapDanceTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        tab._on_save()
        tab._fetcher.wait_idle()
        core.combos_set.assert_not_called()
        box.warning.assert_called_once()

    def test_a_hold_only_dance_is_saved(self):
        # The firmware accepts it (a tap sends nothing), and polyctl can write one.
        core = _core()
        tab = TapDanceTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        tab.action_fields["on_hold"].setText("KC_A")
        tab._on_save()
        tab._fetcher.wait_idle()
        core.combos_set.assert_called_once_with(tap_dances=[{
            "slot": 0, "on_tap": 0, "on_hold": KC_A, "on_double_tap": 0,
            "on_tap_hold": 0, "term_ms": 0}])
        self.assertEqual(tab.list.item(0).text(), "1: hold A")

    def test_the_placeholders_name_the_firmware_defaults(self):
        tab = TapDanceTab(_core())
        f = tab.action_fields
        self.assertEqual(f["on_hold"].placeholderText(), "same as Tap")
        self.assertEqual(f["on_double_tap"].placeholderText(), "Tap twice")
        self.assertEqual(f["on_tap_hold"].placeholderText(), "Tap, then hold Tap")

    @mock.patch("polyhost.gui.layout_dialog.combo_tab.message_box")
    def test_a_failed_save_keeps_the_edits_after_a_deferred_reload(self, box):
        import threading
        release = threading.Event()
        core = _core()

        def failing_set(**_kw):
            release.wait(5)
            return False, "link dropped"
        core.combos_set.side_effect = failing_set
        tab = TapDanceTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        tab.action_fields["on_tap"].setText("KC_ESC")
        tab._on_save()
        tab.reload()                      # the tab is shown again during the save
        release.set()
        tab._fetcher.wait_idle()
        tab._fetcher.wait_idle()
        box.warning.assert_called_once()
        self.assertEqual(core.combos_get.call_count, 1)   # no reload after the failure
        self.assertEqual(tab.action_fields["on_tap"].text(), "KC_ESC")

    def test_a_reload_during_a_save_waits_for_it(self):
        import threading
        release = threading.Event()
        core = _core()

        def slow_set(**_kw):
            release.wait(5)
            return True, {"other_half": True}
        core.combos_set.side_effect = slow_set
        tab = TapDanceTab(core)
        tab.reload()
        tab._fetcher.wait_idle()
        tab.action_fields["on_tap"].setText("KC_ESC")
        tab._on_save()
        tab.reload()                      # the tab is shown again during the save
        self.assertEqual(core.combos_get.call_count, 1)
        release.set()
        tab._fetcher.wait_idle()
        tab._fetcher.wait_idle()
        self.assertEqual(core.combos_get.call_count, 2)

    def test_use_on_key_emits_td_of_the_slot(self):
        tab = TapDanceTab(_core())
        tab.reload()
        tab._fetcher.wait_idle()
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
