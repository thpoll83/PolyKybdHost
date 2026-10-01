"""The mock keyboard's board view, against a stub core (no device, no thread)."""
import base64
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from polyhost.device.keys import KeyCode, Modifier  # noqa: E402

_app = QApplication.instance() or QApplication([])

from polyhost.gui.mock_board_dialog import MockBoardDialog, bitmap_to_image, held_variant  # noqa: E402

_FULL = base64.b64encode(bytes([0xFF]) * 360).decode()


class _Core:
    def __init__(self, ok=True, images=None, enabled=True):
        self.ok, self.images, self.enabled = ok, images or {}, enabled
        self.calls = []

    def mock_keycaps(self, modifier=0):
        self.calls.append(modifier)
        if not self.ok:
            return False, "No mock keyboard is running."
        return True, {"primary": True, "protocol": 21, "overlays_enabled": self.enabled,
                      "modifier": modifier, "images": self.images,
                      "base_layer": {"0,0": KeyCode.KC_ESCAPE.value, "1,1": KeyCode.KC_Q.value},
                      "stats": {"image_reports": 3, "fill_reports": 0, "mapping_reports": 1,
                                "control_reports": 1},
                      "refused": []}


def _with_keycap(dialog):
    return [(k["row"], k["col"]) for k, item in dialog.keys if item._keycap is not None]


class MockBoardDialogTest(unittest.TestCase):

    def _dialog(self, core):
        dlg = MockBoardDialog(core)
        dlg.timer.stop()
        self.addCleanup(dlg.close)
        return dlg

    def test_every_physical_key_is_drawn(self):
        dlg = self._dialog(_Core())
        self.assertEqual(len(dlg.keys), 74)

    def test_a_key_shows_the_overlay_for_the_keycode_it_types(self):
        dlg = self._dialog(_Core(images={str(KeyCode.KC_Q.value): _FULL}))
        self.assertEqual(_with_keycap(dlg), [(1, 1)])
        self.assertIn("1 keycap(s) with an overlay", dlg.status.text())

    def test_the_modifier_picker_asks_for_that_variant(self):
        core = _Core()
        dlg = self._dialog(core)
        dlg.modifier.setCurrentIndex(2)
        self.assertEqual(core.calls[-1], dlg.modifier.itemData(2))

    def test_no_mock_is_said_in_the_status_line(self):
        dlg = self._dialog(_Core(ok=False))
        self.assertIn("No mock keyboard", dlg.status.text())

    def test_a_failing_refresh_is_reported_not_raised(self):
        # The refresh runs from a QTimer, where an exception is qFatal().
        core = _Core()
        dlg = self._dialog(core)
        core.mock_keycaps = mock.Mock(side_effect=ConnectionError("daemon gone"))
        dlg.refresh()
        self.assertIn("daemon gone", dlg.status.text())

    def test_overlays_off_dims_the_pictures(self):
        lit = bitmap_to_image(bytes([0xFF]) * 360, True)
        dim = bitmap_to_image(bytes([0xFF]) * 360, False)
        self.assertGreater(lit.pixelColor(0, 0).value(), dim.pixelColor(0, 0).value())
        dlg = self._dialog(_Core(images={str(KeyCode.KC_Q.value): _FULL}, enabled=False))
        self.assertIn("overlays OFF", dlg.status.text())

    def test_the_board_outline_is_drawn_under_the_keys(self):
        dlg = self._dialog(_Core())
        under = [i for i in dlg.scene.items() if i.zValue() < 0]
        self.assertTrue(under, "no plate drawn")
        self.assertTrue(all(item.zValue() >= 0 for _, item in dlg.keys))

    def test_following_selects_the_held_variant(self):
        core = _Core()
        dlg = self._dialog(core)
        dlg.follow.setChecked(True)
        dlg.follow_timer.stop()
        self.assertFalse(dlg.modifier.isEnabled())
        dlg.follow_modifiers(int(Qt.ControlModifier))
        self.assertEqual(core.calls[-1], Modifier.CTRL.value)
        asked = len(core.calls)
        dlg.follow_modifiers(int(Qt.ControlModifier))      # still held: no refresh
        self.assertEqual(len(core.calls), asked)
        dlg.follow_modifiers(0)                             # released
        self.assertEqual(core.calls[-1], Modifier.NO_MOD.value)
        dlg.follow.setChecked(False)
        self.assertTrue(dlg.modifier.isEnabled())
        self.assertFalse(dlg.follow_timer.isActive())

    def test_save_writes_one_png_per_keycode(self):
        dlg = self._dialog(_Core(images={str(KeyCode.KC_Q.value): _FULL,
                                         str(KeyCode.KC_A.value): _FULL}))
        with tempfile.TemporaryDirectory() as out, \
                mock.patch("polyhost.gui.mock_board_dialog.QFileDialog.getExistingDirectory",
                           return_value=out):
            dlg.save_pngs()
            self.assertEqual(sorted(os.listdir(out)), ["kc0x04_mod0.png", "kc0x14_mod0.png"])


class HeldVariantTest(unittest.TestCase):

    def test_each_modifier_sets_its_bit(self):
        self.assertEqual(held_variant(0), Modifier.NO_MOD.value)
        self.assertEqual(held_variant(int(Qt.ControlModifier | Qt.ShiftModifier)),
                         Modifier.CTRL_SHIFT.value)
        self.assertEqual(held_variant(int(Qt.AltModifier)), Modifier.ALT.value)
        self.assertEqual(held_variant(int(Qt.MetaModifier)), Modifier.GUI_KEY.value)

    def test_on_macos_cmd_is_the_gui_key(self):
        # Qt reports Cmd as ControlModifier and Control as MetaModifier there.
        self.assertEqual(held_variant(int(Qt.ControlModifier), mac_swapped=True),
                         Modifier.GUI_KEY.value)
        self.assertEqual(held_variant(int(Qt.MetaModifier), mac_swapped=True),
                         Modifier.CTRL.value)

    def test_a_pre_v12_keyboard_folds_gui_chords(self):
        chord = int(Qt.MetaModifier | Qt.ShiftModifier)
        self.assertEqual(held_variant(chord, protocol=11), Modifier.GUI_KEY.value)
        self.assertEqual(held_variant(chord, protocol=12), Modifier.GUI_SHIFT.value)


if __name__ == "__main__":
    unittest.main()
