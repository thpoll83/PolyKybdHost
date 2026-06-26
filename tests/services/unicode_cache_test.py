import os
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
    """Icon downloads run OFF the GUI thread (so the language menu never blocks)
    with a bounded timeout, and a failure must not be retried — within the
    session or across launches (persistent negative cache)."""

    def _make_cache(self, config_dir=None):
        tmp = config_dir or tempfile.mkdtemp(prefix="unicode_cache_test_")
        with mock.patch("polyhost.services.unicode_cache.user_config_dir",
                        return_value=tmp):
            return UnicodeCache(), tmp

    @mock.patch("polyhost.services.unicode_cache.requests.Session.get")
    def test_download_uses_bounded_timeout(self, get):
        get.side_effect = ConnectionError("offline")
        cache, _ = self._make_cache()
        cache.get_icon_for("ZZ")   # not shipped in res/flags -> download path
        cache.flush()              # wait for the background worker to run
        self.assertEqual(get.call_args.kwargs.get("timeout"), 10)

    @mock.patch("polyhost.services.unicode_cache.requests.Session.get")
    def test_failed_download_not_retried_in_same_session(self, get):
        get.side_effect = ConnectionError("offline")
        cache, _ = self._make_cache()
        cache.get_icon_for("ZZ")
        cache.flush()
        cache.get_icon_for("ZZ")   # reconnect would call this again
        cache.flush()
        self.assertEqual(get.call_count, 1)

    @mock.patch("polyhost.services.unicode_cache.requests.Session.get")
    def test_distinct_flags_each_get_one_attempt(self, get):
        get.side_effect = ConnectionError("offline")
        cache, _ = self._make_cache()
        cache.get_icon_for("ZZ")
        cache.get_icon_for("ZY")
        cache.flush()
        self.assertEqual(get.call_count, 2)

    @mock.patch("polyhost.services.unicode_cache.requests.Session.get")
    def test_failure_persists_across_instances(self, get):
        # A new process (new UnicodeCache) sharing the same config dir must NOT
        # re-attempt a flag that already failed — this is what stopped the
        # offline machine from re-downloading ~130 flags on every launch.
        get.side_effect = ConnectionError("offline")
        cache1, cfg = self._make_cache()
        cache1.get_icon_for("ZZ")
        cache1.flush()
        cache2, _ = self._make_cache(config_dir=cfg)
        cache2.get_icon_for("ZZ")
        cache2.flush()
        self.assertEqual(get.call_count, 1)

    def test_common_flags_are_bundled(self):
        # The whole point of bundling: common flags resolve from disk with no
        # network at all. Checked on the filesystem (no QGuiApplication needed).
        cache, _ = self._make_cache()
        for code, cps in [("US", "1f1fa-1f1f8"), ("DE", "1f1e9-1f1ea"),
                          ("GB", "1f1ec-1f1e7"), ("JP", "1f1ef-1f1f5")]:
            self.assertTrue((cache.flag_dir / f"{cps}.png").exists(),
                            f"{code} flag not bundled")


class TestBundledIconResolution(unittest.TestCase):
    """A bundled flag must resolve to a real icon with zero network. QIcon
    rendering needs a QGuiApplication, constructed here on the offscreen
    platform so the test runs headlessly (no display required)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PyQt5.QtWidgets import QApplication
            cls.app = QApplication.instance() or QApplication([])
        except Exception as e:  # pragma: no cover - platform without Qt plugins
            raise unittest.SkipTest(f"no usable Qt platform: {e}")

    @mock.patch("polyhost.services.unicode_cache.requests.Session.get")
    def test_bundled_flag_resolves_without_download(self, get):
        tmp = tempfile.mkdtemp(prefix="unicode_cache_test_")
        with mock.patch("polyhost.services.unicode_cache.user_config_dir",
                        return_value=tmp):
            cache = UnicodeCache()
        icon = cache.get_icon_for("US")   # 1f1fa-1f1f8, bundled
        cache.flush()
        self.assertEqual(get.call_count, 0)
        self.assertFalse(icon.isNull())


if __name__ == '__main__':
    unittest.main()
