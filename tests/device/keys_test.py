import unittest

from polyhost.device.keys import KeyCode, Modifier, describe_key, keycode_to_mapping_idx


class TestKeycodeToMappingIdx(unittest.TestCase):
    """keycode_to_mapping_idx maps KeyCode values to 0-based overlay slot indices.

    Three contiguous ranges are mapped:
      range 1: KC_A (0x04)..KC_NUM_LOCK (0x53)  → index 0..79
      range 2: KC_NONUS_BACKSLASH (0x64)..KC_APPLICATION (0x65) → index 80..81
      range 3: KC_LEFT_CTRL (0xE0)..KC_RIGHT_GUI (0xE7) → index 82..89
    """

    # --- range 1: standard HID keys KC_A..KC_NUM_LOCK ---

    def test_kc_a_maps_to_zero(self):
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_A), 0)

    def test_kc_b_maps_to_one(self):
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_B), 1)

    def test_kc_z_maps_to_25(self):
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_Z), 25)

    def test_kc_space_maps_to_40(self):
        # 0x2C - 0x04 = 40
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_SPACE), 40)

    def test_kc_num_lock_is_last_in_range1(self):
        # 0x53 - 0x04 = 79
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_NUM_LOCK), 79)

    # --- range 2: KC_NONUS_BACKSLASH..KC_APPLICATION ---

    def test_kc_nonus_backslash_maps_to_80(self):
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_NONUS_BACKSLASH), 80)

    def test_kc_application_maps_to_81(self):
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_APPLICATION), 81)

    # --- range 3: modifier keys KC_LEFT_CTRL..KC_RIGHT_GUI ---

    def test_kc_left_ctrl_maps_to_82(self):
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_LEFT_CTRL), 82)

    def test_kc_left_shift_maps_to_83(self):
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_LEFT_SHIFT), 83)

    def test_kc_left_alt_maps_to_84(self):
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_LEFT_ALT), 84)

    def test_kc_left_gui_maps_to_85(self):
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_LEFT_GUI), 85)

    def test_kc_right_ctrl_maps_to_86(self):
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_RIGHT_CTRL), 86)

    def test_kc_right_gui_is_last_modifier(self):
        # 0xE7 - 0xE0 + 82 = 89
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_RIGHT_GUI), 89)

    # --- range boundaries are contiguous ---

    def test_ranges_are_contiguous(self):
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_NUM_LOCK), 79)
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_NONUS_BACKSLASH), 80)
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_APPLICATION), 81)
        self.assertEqual(keycode_to_mapping_idx(KeyCode.KC_LEFT_CTRL), 82)



class TestDescribeKey(unittest.TestCase):
    """describe_key names a keycap the way a log reader expects.

    It exists for the overlay-send summary, whose whole job is answering "which
    keys did that just draw on" without anyone decoding hex.
    """

    def test_a_bare_key_is_just_its_name(self):
        self.assertEqual(describe_key(KeyCode.KC_B.value, Modifier.NO_MOD), "B")

    def test_the_kc_prefix_is_dropped(self):
        self.assertFalse(describe_key(KeyCode.KC_B.value, Modifier.NO_MOD).startswith("KC_"))

    def test_escape_is_abbreviated_the_way_a_keycap_reads(self):
        # The ESC cell is where the program icon lands, so this is the name that
        # shows up most often in the summary.
        self.assertEqual(describe_key(KeyCode.KC_ESCAPE.value, Modifier.NO_MOD), "ESC")

    def test_space_is_abbreviated_too(self):
        self.assertEqual(describe_key(KeyCode.KC_SPACE.value, Modifier.NO_MOD), "SPC")

    def test_one_modifier_is_prefixed(self):
        self.assertEqual(describe_key(KeyCode.KC_C.value, Modifier.CTRL), "Ctrl+C")

    def test_modifiers_read_in_the_order_a_shortcut_is_written(self):
        self.assertEqual(describe_key(KeyCode.KC_B.value, Modifier.CTRL_SHIFT),
                         "Ctrl+Shift+B")

    def test_every_bit_of_the_widest_modifier_is_named(self):
        self.assertEqual(describe_key(KeyCode.KC_A.value, Modifier.GUI_CTRL_ALT_SHIFT),
                         "Ctrl+Shift+Alt+GUI+A")

    def test_gui_alone_is_named(self):
        self.assertEqual(describe_key(KeyCode.KC_L.value, Modifier.GUI_KEY), "GUI+L")

    def test_a_plain_int_modifier_works_like_the_enum(self):
        # The caller holds Modifier objects, but nothing in the signature says
        # so -- a raw bitmask must not silently become "no modifier".
        self.assertEqual(describe_key(KeyCode.KC_C.value, 1), "Ctrl+C")

    def test_an_unknown_keycode_falls_back_to_hex_rather_than_raising(self):
        # This runs on the HID worker inside a successful send; an exception
        # here would lose the send's own result to a logging detail.
        self.assertEqual(describe_key(0x7F3, Modifier.NO_MOD), "0x7F3")

    def test_an_unknown_keycode_still_carries_its_modifiers(self):
        self.assertEqual(describe_key(0x7F3, Modifier.CTRL), "Ctrl+0x7F3")

    def test_every_modifier_variant_describes_without_raising(self):
        for modifier in Modifier:
            with self.subTest(modifier=modifier):
                text = describe_key(KeyCode.KC_A.value, modifier)
                self.assertTrue(text.endswith("A"))
                self.assertEqual(text.count("+"), bin(modifier.value).count("1"))


if __name__ == '__main__':
    unittest.main()
