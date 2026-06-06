import unittest

from polyhost.gui.layout_dialog.qmk_keycode_helper import (
    MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI, MOD_RIGHT,
    encode_mods, encode_layer_switch, encode_one_shot_mod,
    encode_mod_tap, encode_layer_tap, encode_modded, encode_layer_mod,
    encode_persistent_def_layer, encode_swap_hands_tap,
    decompose_keycode, describe_keycode, decode_for_composer,
    BADGE_COLOR_LAYER, BADGE_COLOR_TAP, BADGE_COLOR_MOD, BADGE_COLOR_FW,
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

    def test_layer_mod(self):
        # LM(layer, mod) = QK_LAYER_MOD | (layer << 5) | mod
        self.assertEqual(encode_layer_mod(1, MOD_CTRL), 0x5021)
        self.assertEqual(encode_layer_mod(2, MOD_SHIFT), 0x5042)

    def test_persistent_def_layer(self):
        self.assertEqual(encode_persistent_def_layer(2), 0x52E2)

    def test_swap_hands_tap(self):
        self.assertEqual(encode_swap_hands_tap(0x04), 0x5604)
        self.assertEqual(encode_swap_hands_tap(0xEF), 0x56EF)

    def test_swap_hands_tap_rejects_named_action_range(self):
        # 0xF0..0xFF would collide with the named swap-hands action block.
        for bad in (0xF0, 0xFF, -1, 0x100):
            with self.assertRaises(ValueError):
                encode_swap_hands_tap(bad)


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

    def test_layer_mod_roundtrip(self):
        kc = encode_layer_mod(2, MOD_CTRL | MOD_SHIFT)
        self.assertEqual(decompose_keycode(kc, KC), "LM(2,LCTL+LSFT)")
        self.assertEqual(decode_for_composer(kc), ("LM", 2, MOD_CTRL | MOD_SHIFT, 0))

    def test_persistent_def_layer_roundtrip(self):
        kc = encode_persistent_def_layer(3)
        self.assertEqual(decompose_keycode(kc, KC), "PDF(3)")
        self.assertEqual(decode_for_composer(kc), ("PDF", 3, 0, 0))

    def test_swap_hands_tap_roundtrip(self):
        kc = encode_swap_hands_tap(0x04)
        self.assertEqual(decompose_keycode(kc, KC), "SH_T(A)")
        self.assertEqual(decode_for_composer(kc), ("SH_T", 0, 0, 0x04))


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


class TestDecodeForComposer(unittest.TestCase):
    def test_layer_switches(self):
        for tag in ("MO", "TO", "TG", "DF", "TT", "OSL"):
            self.assertEqual(
                decode_for_composer(encode_layer_switch(tag, 3)),
                (tag, 3, 0, 0),
            )

    def test_one_shot_mod(self):
        self.assertEqual(
            decode_for_composer(encode_one_shot_mod(MOD_SHIFT)),
            ("OSM", 0, MOD_SHIFT, 0),
        )

    def test_mod_tap(self):
        self.assertEqual(
            decode_for_composer(encode_mod_tap(MOD_SHIFT, 0x04)),
            ("MT", 0, MOD_SHIFT, 0x04),
        )

    def test_layer_tap(self):
        self.assertEqual(
            decode_for_composer(encode_layer_tap(2, 0x2C)),
            ("LT", 2, 0, 0x2C),
        )

    def test_modded_left_and_right(self):
        self.assertEqual(
            decode_for_composer(encode_modded(MOD_CTRL, 0x04)),
            ("MOD", 0, MOD_CTRL, 0x04),
        )
        self.assertEqual(
            decode_for_composer(encode_modded(MOD_CTRL | MOD_RIGHT, 0x04)),
            ("MOD", 0, MOD_CTRL | MOD_RIGHT, 0x04),
        )

    def test_plain_and_unsupported_return_none(self):
        self.assertIsNone(decode_for_composer(0x0004))   # KC_A
        self.assertIsNone(decode_for_composer(0x0000))   # KC_NO
        self.assertIsNone(decode_for_composer(0x5703))   # TD() — firmware-defined
        self.assertIsNone(decode_for_composer(0x56F0))   # SH_TOGG — named action, not SH_T
        self.assertIsNone(decode_for_composer(0x7702))   # MACRO() — firmware-defined


class TestFirmwareKeycodeDisplay(unittest.TestCase):
    """Parametric / firmware-defined keycodes that used to fall through to hex."""

    def test_decompose_labels(self):
        cases = {
            0x52E2: "PDF(2)",          # persistent default layer
            0x5604: "SH_T(A)",         # swap-hands tap-hold
            0x5703: "TD(3)",           # tap dance
            0x7702: "MACRO(2)",
            0x7441: "PB(1)",           # programmable button
            0x7E05: "KB(5)",           # keyboard custom
            0x7E43: "USER(3)",         # user custom
        }
        for kc, expected in cases.items():
            self.assertEqual(decompose_keycode(kc, KC), expected, hex(kc))

    def test_no_raw_hex_for_these(self):
        for kc in (0x52E2, 0x5604, 0x5703, 0x7702, 0x7441, 0x7E05, 0x7E43):
            self.assertNotIn("0x", decompose_keycode(kc, KC), hex(kc))

    def test_named_constant_still_wins(self):
        # A named entry in the mapping must take priority over parametric decode.
        mapping = dict(KC)
        mapping[0x7702] = "MC_MYMACRO"
        self.assertEqual(decompose_keycode(0x7702, mapping), "MC_MYMACRO")

    def test_describe_badges(self):
        self.assertEqual(describe_keycode(0x52E2, KC), ("L2", "PDF", BADGE_COLOR_LAYER))
        self.assertEqual(describe_keycode(0x5604, KC), ("A", "SH", BADGE_COLOR_TAP))
        self.assertEqual(describe_keycode(0x5703, KC), ("TD", "3", BADGE_COLOR_FW))

    def test_describe_firmware_fallthrough_single_line(self):
        main, badge, color = describe_keycode(0x7702, KC)   # MACRO(2)
        self.assertEqual(main, "MACRO(2)")
        self.assertEqual(badge, "")
        self.assertIsNone(color)


if __name__ == "__main__":
    unittest.main()
