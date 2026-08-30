import unittest

from polyhost.gui.layout_dialog.qmk_keycode_helper import (
    MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI, MOD_RIGHT,
    encode_mods, encode_layer_switch, encode_one_shot_mod,
    encode_mod_tap, encode_layer_tap, encode_modded, encode_layer_mod,
    encode_persistent_def_layer, encode_swap_hands_tap,
    decompose_keycode, describe_keycode, decode_for_composer,
    build_keycode_to_name, mod_stack_name, DISPLAY_NAME_OVERRIDE,
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



class TestBuildKeycodeToName(unittest.TestCase):
    """The inversion picks WHICH of a value's several names a tile shows.

    Naive last-wins is right for the short aliases the tiles want, and wrong for the
    one case where the later name is not a name for the key at all.
    """

    def test_a_KC_name_beats_a_non_KC_alias(self):
        # XXXXXXX = KC_NO is declared later, so last-wins picked the literal.
        self.assertEqual(build_keycode_to_name({"KC_NO": 0, "XXXXXXX": 0})[0], "KC_NO")

    def test_declaration_order_does_not_matter(self):
        self.assertEqual(build_keycode_to_name({"XXXXXXX": 0, "KC_NO": 0})[0], "KC_NO")

    def test_the_LAST_KC_name_still_wins_so_short_aliases_survive(self):
        # This is the property that makes tiles say ENT rather than ENTER; a rule of
        # "first name wins" would read as a fix and regress 500+ keys.
        got = build_keycode_to_name({"KC_ENTER": 0x28, "KC_ENT": 0x28})
        self.assertEqual(got[0x28], "KC_ENT")

    def test_a_value_with_no_KC_name_at_all_is_untouched(self):
        # MS_UP / SH_TOGG / the RGB set only ever have QK_ and bare names.
        got = build_keycode_to_name({"QK_MOUSE_CURSOR_UP": 0xCD, "MS_UP": 0xCD})
        self.assertEqual(got[0xCD], "MS_UP")

    def test_the_real_header_changes_exactly_one_value(self):
        """Blast-radius guard: the header is the input this runs against in the app."""
        from polyhost.gui.layout_dialog.qmk_keycode_helper import (
            HEADER_FILE, parse_qmk_keycodes)
        names = parse_qmk_keycodes(HEADER_FILE)
        naive = {v: k for k, v in names.items()}
        picked = build_keycode_to_name(names)
        differing = {v for v in naive if naive[v] != picked[v]}
        # The inversion rule itself moves ONE value; everything else that differs
        # must be a deliberate composite label, never collateral.
        self.assertEqual(differing, {0x0000} | set(DISPLAY_NAME_OVERRIDE))
        self.assertEqual(picked[0x0000], "KC_NO")


class TestModStackNaming(unittest.TestCase):
    """A mod combo over KC_NO is Hyper/Meh, not 'the inner key is unassigned'."""

    def test_hyper_and_meh(self):
        self.assertEqual(mod_stack_name(MOD_CTRL | MOD_SHIFT | MOD_ALT | MOD_GUI), "Hyper")
        self.assertEqual(mod_stack_name(MOD_CTRL | MOD_SHIFT | MOD_ALT), "Meh")

    def test_a_right_hand_stack_is_NOT_called_hyper(self):
        mods = MOD_CTRL | MOD_SHIFT | MOD_ALT | MOD_GUI | MOD_RIGHT
        self.assertEqual(mod_stack_name(mods), "RCTL+RSFT+RALT+RGUI")

    def test_an_unnamed_stack_falls_back_to_the_mod_string(self):
        self.assertEqual(mod_stack_name(MOD_CTRL | MOD_SHIFT), "LCTL+LSFT")

    def test_decompose_names_the_stack_instead_of_wrapping_the_inner_key(self):
        self.assertEqual(decompose_keycode(0x0F00, KC), "Hyper")
        self.assertEqual(decompose_keycode(0x0700, KC), "Meh")

    def test_the_tile_says_hyper_and_keeps_the_mod_badge(self):
        main, badge, color = describe_keycode(0x0F00, KC)
        self.assertEqual(main, "Hyper")
        self.assertEqual(badge, "\u2303\u21e7\u2325\u2318")
        self.assertEqual(color, BADGE_COLOR_MOD)

    def test_a_mod_combo_WITH_an_inner_key_is_unchanged(self):
        self.assertEqual(decompose_keycode(0x0104, KC), "LCTL(A)")
        self.assertEqual(describe_keycode(0x0104, KC)[0], "A")




class TestDisplayNameOverride(unittest.TestCase):
    """Values whose several names are DIFFERENT KEYS get a composite label.

    QMK defines KC_BRMD = KC_SCROLL_LOCK and KC_BRMU = KC_PAUSE, so picking either
    real name hides the other meaning; the editor states both instead.
    """

    def test_scroll_lock_and_pause_say_both_meanings(self):
        got = build_keycode_to_name({"KC_SCROLL_LOCK": 0x47, "KC_SCRL": 0x47,
                                     "KC_BRMD": 0x47, "KC_PAUSE": 0x48,
                                     "KC_BRK": 0x48, "KC_BRMU": 0x48})
        self.assertEqual(got[0x47], "KC_SCRL_BRMD")
        self.assertEqual(got[0x48], "KC_PAUS_BRK_BRMU")

    def test_the_label_becomes_a_multi_line_tile_caption(self):
        # create_nice_name turns each underscore into a line break.
        from polyhost.gui.layout_dialog.qmk_keycode_helper import create_nice_name
        self.assertEqual(create_nice_name("KC_SCRL_BRMD"), "SCRL\nBRMD")

    def test_an_override_for_a_value_the_header_lacks_is_ignored(self):
        # Never invent a key: the override annotates a value that exists, it does
        # not add one.
        self.assertNotIn(0x47, build_keycode_to_name({"KC_A": 0x04}))

    def test_overrides_are_display_only_and_not_real_keycode_names(self):
        from polyhost.gui.layout_dialog.qmk_keycode_helper import (
            HEADER_FILE, parse_qmk_keycodes)
        names = parse_qmk_keycodes(HEADER_FILE)
        for label in DISPLAY_NAME_OVERRIDE.values():
            self.assertNotIn(label, names)



if __name__ == "__main__":
    unittest.main()
