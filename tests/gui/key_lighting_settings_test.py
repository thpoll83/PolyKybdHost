"""Settings > Keyboard > Key lighting (firmware v39+): the RGB matrix rows."""
import logging
import types
import unittest

from PyQt5.QtWidgets import QApplication

from polyhost.gui import keyboard_settings as kbd
from polyhost.gui.menu_fetch import MenuFetcher

RGB = {"enabled": True, "effect": 3, "brightness": 51, "speed": 128, "hue": 10, "sat": 200}


class ReadsTest(unittest.TestCase):
    def test_a_read_fills_every_row(self):
        values, failed = kbd.values_from_reads({"rgb_matrix": (True, RGB)})
        self.assertEqual({k: values[k] for k in kbd.RGB_KEYS},
                         {kbd.RGB_ENABLED: True, kbd.RGB_EFFECT: 3, kbd.RGB_BRIGHTNESS: 51,
                          kbd.RGB_SPEED: 128, kbd.RGB_HUE: 10, kbd.RGB_SAT: 200,
                          kbd.RGB_INDICATE: None})
        self.assertFalse(set(kbd.RGB_KEYS) & set(failed))

    def test_a_switched_off_matrix_shows_effect_1(self):
        values, _f = kbd.values_from_reads({"rgb_matrix": (True, dict(RGB, enabled=False, effect=0))})
        self.assertFalse(values[kbd.RGB_ENABLED])
        self.assertEqual(values[kbd.RGB_EFFECT], 1)

    def test_older_firmware_leaves_the_rows_disabled(self):
        values, failed = kbd.values_from_reads({"rgb_matrix": (False, "need v39+")})
        self.assertFalse(set(kbd.RGB_KEYS) & set(values))
        self.assertEqual(set(kbd.RGB_KEYS) - set(failed), set())


class CallTest(unittest.TestCase):
    def test_nothing_changed(self):
        self.assertIsNone(kbd.rgb_matrix_call({kbd.GLYPH_SIZE: 1}, {}))

    def test_hue_alone_sends_the_read_saturation(self):
        read = {kbd.RGB_HUE: 10, kbd.RGB_SAT: 200}
        self.assertEqual(kbd.rgb_matrix_call({kbd.RGB_HUE: 40}, read), {"hue": 40, "sat": 200})

    def test_switching_off_drops_an_effect_change(self):
        self.assertEqual(kbd.rgb_matrix_call({kbd.RGB_ENABLED: False, kbd.RGB_EFFECT: 5}, {}),
                         {"enabled": False})

    def test_values_go_in_one_call(self):
        self.assertEqual(kbd.rgb_matrix_call({kbd.RGB_ENABLED: True, kbd.RGB_BRIGHTNESS: 255,
                                              kbd.RGB_SPEED: 3}, {}),
                         {"enabled": True, "brightness": 255, "speed": 3})


class DialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, rgb):
        from polyhost.gui.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        self.addCleanup(dlg.deleteLater)
        dlg.setup({"ui_theme": "auto"}, keyboard=True)
        dlg.set_keyboard_reads({"rgb_matrix": rgb})
        return dlg

    def test_rows_fill_and_a_change_is_returned_unsnapped(self):
        dlg = self._dialog((True, RGB))
        w = dlg.keyboard_widgets
        self.assertTrue(w[kbd.RGB_ENABLED].isChecked())
        self.assertEqual(w[kbd.RGB_BRIGHTNESS].value(), 51)
        self.assertEqual(dlg.keyboard_changes(), {})
        w[kbd.RGB_BRIGHTNESS].setValue(57)          # not on the 10 ms grid
        w[kbd.RGB_ENABLED].setChecked(False)
        self.assertEqual(dlg.keyboard_changes(), {kbd.RGB_BRIGHTNESS: 57, kbd.RGB_ENABLED: False})
        self.assertFalse(w[kbd.RGB_EFFECT].isEnabled())   # follows the switch

    def test_effect_is_disabled_while_the_matrix_is_off(self):
        dlg = self._dialog((True, dict(RGB, enabled=False, effect=0)))
        self.assertFalse(dlg.keyboard_widgets[kbd.RGB_EFFECT].isEnabled())
        self.assertEqual(dlg.keyboard_changes(), {})

    def test_blink_emits_and_is_not_a_change(self):
        dlg = self._dialog((True, RGB))
        clicks = []
        dlg.indicate_requested.connect(lambda: clicks.append(1))
        button = dlg.keyboard_widgets[kbd.RGB_INDICATE]
        self.assertTrue(button.isEnabled())
        button.click()
        self.assertEqual(clicks, [1])
        self.assertEqual(dlg.keyboard_changes(), {})

    def test_older_firmware_disables_the_button(self):
        dlg = self._dialog((False, "need v39+"))
        self.assertFalse(dlg.keyboard_widgets[kbd.RGB_INDICATE].isEnabled())


class HostSendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _host(self):
        from polyhost.host import PolyHost
        calls = []
        core = types.SimpleNamespace(
            set_rgb_matrix=lambda v: calls.append(("rgb", v)) or (True, "ok"),
            indicate_device=lambda: calls.append(("indicate",)) or (True, "ok"))
        host = types.SimpleNamespace(_menu_fetch=MenuFetcher(), core=core,
                                     log=logging.getLogger("test"),
                                     report_device_result=lambda *a: calls.append(("err", a)))
        host._core_click = lambda fn, done: PolyHost._core_click(host, fn, done)
        return host, PolyHost, calls

    def test_changes_go_in_one_set_call(self):
        host, PolyHost, calls = self._host()
        PolyHost._send_keyboard_changes(host, {kbd.RGB_ENABLED: False, kbd.RGB_SAT: 9},
                                        {kbd.RGB_HUE: 10, kbd.RGB_SAT: 200})
        self.assertTrue(host._menu_fetch.wait_idle())
        self.assertEqual(calls, [("rgb", {"enabled": False, "hue": 10, "sat": 9})])

    def test_blink_calls_indicate(self):
        host, PolyHost, calls = self._host()
        PolyHost._indicate_clicked(host)
        self.assertTrue(host._menu_fetch.wait_idle())
        self.assertEqual(calls, [("indicate",)])


if __name__ == "__main__":
    unittest.main()
