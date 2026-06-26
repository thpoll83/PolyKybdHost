import os
import unittest
from unittest import mock


@unittest.skipUnless(os.environ.get("DISPLAY"), "host.py imports pynput at module load (needs X)")
class TestLangcodeToFlag(unittest.TestCase):
    """PolyHost.langcode_to_flag renders the country code as a regional-indicator
    flag emoji everywhere except macOS, where the OS would render the pair as a
    real flag and duplicate the per-entry flag icon — there it must be the plain
    upper-case code instead (e.g. "AT", giving "de AT")."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from polyhost.host import PolyHost
        cls.PolyHost = PolyHost

    def test_macos_returns_uppercase_letters(self):
        with mock.patch("polyhost.host.platform.system", return_value="Darwin"):
            self.assertEqual(self.PolyHost.langcode_to_flag("at"), "AT")
            self.assertEqual(self.PolyHost.langcode_to_flag("US"), "US")

    def test_non_macos_returns_regional_indicator_emoji(self):
        # "AT" -> regional indicators A(0x1F1E6) T(0x1F1F9)
        expected = chr(0x1F1E6) + chr(0x1F1F9)
        for plat in ("Linux", "Windows"):
            with mock.patch("polyhost.host.platform.system", return_value=plat):
                self.assertEqual(self.PolyHost.langcode_to_flag("AT"), expected)
                self.assertEqual(self.PolyHost.langcode_to_flag("at"), expected)


if __name__ == "__main__":
    unittest.main()
