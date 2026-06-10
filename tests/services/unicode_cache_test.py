import tempfile
import unittest
from unittest import mock

from polyhost.services.unicode_cache import UnicodeCache, _unicode_flag_to_codepoints


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


class TestDownloadFailureHandling(unittest.TestCase):
    """Icon downloads run on the GUI thread: they must use a bounded timeout
    and must not be retried within the same session once they failed."""

    def _make_cache(self):
        tmp = tempfile.mkdtemp(prefix="unicode_cache_test_")
        with mock.patch("polyhost.services.unicode_cache.user_config_dir",
                        return_value=tmp):
            return UnicodeCache()

    @mock.patch("polyhost.services.unicode_cache.requests.get")
    def test_download_uses_bounded_timeout(self, get):
        get.side_effect = ConnectionError("offline")
        cache = self._make_cache()
        cache.get_icon_for("ZZ")   # not shipped in res/flags -> download path
        self.assertEqual(get.call_args.kwargs.get("timeout"), 5)

    @mock.patch("polyhost.services.unicode_cache.requests.get")
    def test_failed_download_not_retried_in_same_session(self, get):
        get.side_effect = ConnectionError("offline")
        cache = self._make_cache()
        cache.get_icon_for("ZZ")
        cache.get_icon_for("ZZ")   # reconnect would call this again
        self.assertEqual(get.call_count, 1)

    @mock.patch("polyhost.services.unicode_cache.requests.get")
    def test_distinct_flags_each_get_one_attempt(self, get):
        get.side_effect = ConnectionError("offline")
        cache = self._make_cache()
        cache.get_icon_for("ZZ")
        cache.get_icon_for("ZY")
        self.assertEqual(get.call_count, 2)


if __name__ == '__main__':
    unittest.main()
