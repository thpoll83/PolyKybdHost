import unittest

from polyhost.services.unicode_cache import _unicode_flag_to_codepoints


class TestUnicodeFlagToCodepoints(unittest.TestCase):
    """_unicode_flag_to_codepoints converts a 2-letter country code to the
    hex codepoint string used by Twemoji (e.g. "1f1fa-1f1f8" for "US").

    Regional indicator letters are U+1F1E6 (A) .. U+1F1FF (Z).
    Each letter maps as: ord(letter) + 127397 = ord(letter) + 0x1F1C3.
    """

    def test_us_flag_uppercase(self):
        self.assertEqual(_unicode_flag_to_codepoints("US"), "1f1fa-1f1f8")

    def test_us_flag_lowercase_same_as_upper(self):
        self.assertEqual(_unicode_flag_to_codepoints("us"), "1f1fa-1f1f8")

    def test_de_flag(self):
        # D → 0x1F1E9, E → 0x1F1EA
        self.assertEqual(_unicode_flag_to_codepoints("DE"), "1f1e9-1f1ea")

    def test_gb_flag(self):
        # G → 0x1F1EC, B → 0x1F1E7
        self.assertEqual(_unicode_flag_to_codepoints("GB"), "1f1ec-1f1e7")

    def test_jp_flag(self):
        # J → 0x1F1EF, P → 0x1F1F5
        self.assertEqual(_unicode_flag_to_codepoints("JP"), "1f1ef-1f1f5")

    def test_fr_flag(self):
        # F → 0x1F1EB, R → 0x1F1F7
        self.assertEqual(_unicode_flag_to_codepoints("FR"), "1f1eb-1f1f7")

    def test_mixed_case_normalises_to_uppercase(self):
        self.assertEqual(_unicode_flag_to_codepoints("De"), _unicode_flag_to_codepoints("DE"))

    def test_output_is_dash_separated_hex(self):
        result = _unicode_flag_to_codepoints("US")
        parts = result.split("-")
        self.assertEqual(len(parts), 2)
        # each part must be valid lowercase hex
        for part in parts:
            int(part, 16)

    def test_all_letters_a_to_z_produce_regional_indicator_range(self):
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            expected = ord(letter) + 127397
            codepoint_str = _unicode_flag_to_codepoints(letter + "A").split("-")[0]
            self.assertEqual(int(codepoint_str, 16), expected)


if __name__ == '__main__':
    unittest.main()
