"""services/keycode_text: the keycode spellings polyctl and the combo editor share."""

import unittest

from polyhost.services.keycode_text import keycode_text, parse_keycode


class KeycodeTextTest(unittest.TestCase):
    def test_names_and_numbers(self):
        self.assertEqual(parse_keycode("KC_J"), 0x0D)
        self.assertEqual(parse_keycode("esc"), 0x29)
        self.assertEqual(parse_keycode("0x5221"), 0x5221)
        self.assertRaises(ValueError, parse_keycode, "KC_NOPE")

    def test_modifier_wrappers(self):
        self.assertEqual(parse_keycode("S(KC_9)"), 0x0226)
        self.assertEqual(parse_keycode("lctl(kc_c)"), 0x0106)
        self.assertRaises(ValueError, parse_keycode, "S(MO(1))")

    def test_td_is_limited_to_the_firmware_slots(self):
        self.assertEqual(parse_keycode("TD(15)"), 0x570F)
        self.assertRaises(ValueError, parse_keycode, "TD(16)")

    def test_every_written_form_reads_back(self):
        """The editor shows keycode_text() and saves parse_keycode() of it, so a
        spelling that does not read back makes a stored record unsavable."""
        for value in (0x0D, 0x0100, 0x0226, 0x1106, 0x5200, 0x5221, 0x527F, 0x5700, 0x570F):
            self.assertEqual(parse_keycode(keycode_text(value)), value, keycode_text(value))

    def test_a_tap_dance_past_the_slots_is_shown_as_a_number(self):
        self.assertEqual(keycode_text(0x5710), "0x5710")


if __name__ == "__main__":
    unittest.main()
