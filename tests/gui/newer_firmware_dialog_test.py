"""Tests for the newer-firmware dialog's choice contract.

The dialog itself needs a QApplication/display (covered by the host smoke tests
under xvfb); here we pin the pure choice metadata that both the dialog and the
tests rely on — the three offered choices and the safe default — so a rename can't
silently break the host wiring that matches on these strings.
"""
import unittest

from polyhost.gui.newer_firmware_dialog import NEWER_FW_CHOICES, NEWER_FW_DEFAULT


class NewerFirmwareChoicesTest(unittest.TestCase):
    def test_offers_exactly_the_three_expected_choices(self):
        choices = [c for _label, c in NEWER_FW_CHOICES]
        self.assertEqual(set(choices), {"safe", "update", "ignore"})
        # No duplicates, and every entry has a non-empty label.
        self.assertEqual(len(choices), len(set(choices)))
        self.assertTrue(all(label.strip() for label, _c in NEWER_FW_CHOICES))

    def test_default_is_safe_and_is_an_offered_choice(self):
        self.assertEqual(NEWER_FW_DEFAULT, "safe")
        self.assertIn(NEWER_FW_DEFAULT, [c for _l, c in NEWER_FW_CHOICES])

    def test_safe_is_the_first_button(self):
        # host.py relies on safe being the default/focus button; keep it first.
        self.assertEqual(NEWER_FW_CHOICES[0][1], "safe")


if __name__ == "__main__":
    unittest.main()
