"""Opening Settings and pressing OK must not change any value.

A QSpinBox clamps whatever it is given to its range, and OK writes the
clamped value back. A 10_000 cap on every int editor turned
browser_report_port 50164 into 10000 on every OK, so the browser extension
lost the host without anyone editing the field.
"""
import os
import unittest


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("QT_QPA_PLATFORM"),
                     "building the dialog needs a display (xvfb-run)")
class SettingsRoundTripTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _round_trip(self, settings):
        from polyhost.gui.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        self.addCleanup(dlg.deleteLater)
        dlg.setup(settings, developer_mode=True)
        return dlg.get_updated_settings()

    def test_every_default_survives_ok_unchanged(self):
        from polyhost.settings import DEFAULT_SETTINGS
        self.assertEqual(self._round_trip(dict(DEFAULT_SETTINGS)), DEFAULT_SETTINGS)

    def test_a_port_above_ten_thousand_is_kept(self):
        self.assertEqual(self._round_trip({"browser_report_port": 50164}),
                         {"browser_report_port": 50164})

    def test_negative_and_large_numbers_are_kept(self):
        values = {"some_offset": -5, "some_scale": 2500.5, "neg_scale": -0.25}
        self.assertEqual(self._round_trip(dict(values)), values)

    def test_a_stored_value_is_never_an_end_of_its_range(self):
        from polyhost.gui.settings_dialog import create_editor
        for value in (-5, 50164, -0.25, 2500.5, 0.75):
            with self.subTest(value=value):
                box = create_editor(value)
                self.addCleanup(box.deleteLater)
                self.assertLess(box.minimum(), value)
                self.assertGreater(box.maximum(), value)


if __name__ == "__main__":
    unittest.main()
