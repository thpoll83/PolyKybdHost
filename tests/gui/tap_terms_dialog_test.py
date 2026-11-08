"""TapTermsDialog: shows the keyboard's terms and returns valid values."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.tap_terms_dialog import TapTermsDialog
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TapTermsDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_shows_the_keyboards_values(self):
        d = TapTermsDialog({"tapping_term": 260, "flow_tap_term": 0,
                            "flow_tap_available": True})
        self.assertEqual(d.values(), (260, 0))
        self.assertEqual(d.flow_tap.text(), "Off")

    def test_range_matches_the_firmware(self):
        d = TapTermsDialog({"tapping_term": 200, "flow_tap_term": 150})
        self.assertEqual((d.tapping.minimum(), d.tapping.maximum()), (100, 500))
        self.assertEqual((d.flow_tap.minimum(), d.flow_tap.maximum()), (0, 300))

    def test_a_typed_value_is_snapped_to_the_10_ms_grid(self):
        d = TapTermsDialog({"tapping_term": 200, "flow_tap_term": 150})
        d.tapping.setValue(237)
        d.flow_tap.setValue(144)
        self.assertEqual(d.values(), (240, 140))

    def test_restore_defaults(self):
        d = TapTermsDialog({"tapping_term": 400, "flow_tap_term": 0})
        d.restore_defaults()
        self.assertEqual(d.values(), (200, 150))

    def test_no_flow_tap_in_firmware_leaves_it_unchanged(self):
        d = TapTermsDialog({"tapping_term": 200, "flow_tap_term": 150,
                            "flow_tap_available": False})
        self.assertFalse(d.flow_tap.isEnabled())
        self.assertEqual(d.values(), (200, None))


if __name__ == "__main__":
    unittest.main()
