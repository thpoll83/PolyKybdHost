import unittest

from polyhost.device.keys import KeyCode, keycode_to_mapping_idx


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


if __name__ == '__main__':
    unittest.main()
