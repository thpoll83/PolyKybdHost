import unittest

from polyhost.gui.layout_dialog.qmk_keycode_helper import (
    MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI, MOD_RIGHT,
    encode_mods, encode_layer_switch, encode_one_shot_mod,
    encode_mod_tap, encode_layer_tap, encode_modded,
    decompose_keycode, describe_keycode,
    BADGE_COLOR_LAYER, BADGE_COLOR_TAP, BADGE_COLOR_MOD,
)

# Minimal code->name mapping for the inner keys used in the tests.
KC = {0x0000: "KC_NO", 0x0001: "KC_TRANSPARENT", 0x0004: "KC_A", 0x002C: "KC_SPACE"}


class TestEncodeMods(unittest.TestCase):
    def test_individual_bits(self):
        self.assertEqual(encode_mods(ctrl=True), MOD_CTRL)
        self.assertEqual(encode_mods(shift=True), MOD_SHIFT)
        self.assertEqual(encode_mods(alt=True), MOD_ALT)
        self.assertEqual(encode_mods(gui=True), MOD_GUI)

    def test_combo_and_right(self):
        self.assertEqual(encode_mods(ctrl=True, shift=True), MOD_CTRL | MOD_SHIFT)
        self.assertEqual(encode_mods(shift=True, right=True), MOD_SHIFT | MOD_RIGHT)

    def test_right_ignored_without_mods(self):
        # right-hand flag is meaningless with no modifier selected
        self.assertEqual(encode_mods(right=True), 0)


class TestEncoders(unittest.TestCase):
    def test_layer_switches(self):
        self.assertEqual(encode_layer_switch("TO", 1), 0x5201)
        self.assertEqual(encode_layer_switch("MO", 2), 0x5222)
        self.assertEqual(encode_layer_switch("DF", 1), 0x5241)
        self.assertEqual(encode_layer_switch("TG", 3), 0x5263)
        self.assertEqual(encode_layer_switch("OSL", 1), 0x5281)
        self.assertEqual(encode_layer_switch("TT", 0), 0x52C0)

    def test_one_shot_mod(self):
        self.assertEqual(encode_one_shot_mod(MOD_SHIFT), 0x52A2)

    def test_mod_tap(self):
        self.assertEqual(encode_mod_tap(MOD_SHIFT, 0x04), 0x2204)

    def test_layer_tap(self):
        self.assertEqual(encode_layer_tap(1, 0x04), 0x4104)

    def test_modded(self):
        self.assertEqual(encode_modded(MOD_CTRL, 0x04), 0x0104)
        self.assertEqual(encode_modded(MOD_CTRL | MOD_RIGHT, 0x04), 0x1104)


class TestRoundTrip(unittest.TestCase):
    """encode_* must produce keycodes that decompose_keycode reads back correctly."""

    def test_layer_switch_roundtrip(self):
        for tag in ("MO", "TO", "TG", "DF", "TT", "OSL"):
            kc = encode_layer_switch(tag, 3)
            self.assertEqual(decompose_keycode(kc, KC), f"{tag}(3)")

    def test_mod_tap_roundtrip(self):
        kc = encode_mod_tap(MOD_SHIFT, 0x04)
        self.assertEqual(decompose_keycode(kc, KC), "MT(LSFT,A)")

    def test_layer_tap_roundtrip(self):
        kc = encode_layer_tap(2, 0x2C)
        self.assertEqual(decompose_keycode(kc, KC), "LT(2,SPACE)")

    def test_modded_roundtrip(self):
        kc = encode_modded(MOD_CTRL, 0x04)
        self.assertEqual(decompose_keycode(kc, KC), "LCTL(A)")
        kc_r = encode_modded(MOD_CTRL | MOD_RIGHT, 0x04)
        self.assertEqual(decompose_keycode(kc_r, KC), "RCTL(A)")

    def test_one_shot_mod_roundtrip(self):
        kc = encode_one_shot_mod(MOD_SHIFT)
        self.assertEqual(decompose_keycode(kc, KC), "OSM(LSFT)")


class TestDescribeKeycode(unittest.TestCase):
    def test_plain_key_no_badge(self):
        main, badge, color = describe_keycode(0x0004, KC)
        self.assertEqual(main, "A")
        self.assertEqual(badge, "")
        self.assertIsNone(color)

    def test_layer_switch_badge(self):
        main, badge, color = describe_keycode(encode_layer_switch("MO", 2), KC)
        self.assertEqual(main, "L2")
        self.assertEqual(badge, "MO")
        self.assertEqual(color, BADGE_COLOR_LAYER)

    def test_mod_tap_badge(self):
        main, badge, color = describe_keycode(encode_mod_tap(MOD_SHIFT, 0x04), KC)
        self.assertEqual(main, "A")
        self.assertIn("⇧", badge)
        self.assertEqual(color, BADGE_COLOR_TAP)

    def test_layer_tap_badge(self):
        main, badge, color = describe_keycode(encode_layer_tap(1, 0x2C), KC)
        self.assertEqual(main, "SPACE")
        self.assertEqual(badge, "L1")
        self.assertEqual(color, BADGE_COLOR_TAP)

    def test_modded_badge(self):
        main, badge, color = describe_keycode(encode_modded(MOD_CTRL, 0x04), KC)
        self.assertEqual(main, "A")
        self.assertIn("⌃", badge)
        self.assertEqual(color, BADGE_COLOR_MOD)

    def test_osm_badge(self):
        main, badge, color = describe_keycode(encode_one_shot_mod(MOD_SHIFT), KC)
        self.assertIn("⇧", main)
        self.assertEqual(badge, "OSM")
        self.assertEqual(color, BADGE_COLOR_LAYER)


if __name__ == "__main__":
    unittest.main()
