"""The file-only `read_setting` helper.

main_app needs `developer_mode` before it knows which launch path it is taking,
and long before any logging is configured — so it must be readable WITHOUT
constructing PolySettings (which creates the config dir, merges + re-saves the
defaults and log-dumps every key). It must also never raise: a missing, empty,
malformed or unreadable config is a normal first-run/edited-by-hand state, and
the app has to launch anyway.
"""
import os
import tempfile
import unittest
from unittest import mock

from polyhost import settings


class ReadSettingTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "settings.yaml")
        patcher = mock.patch.object(settings, "settings_path", return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def _write(self, text):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_reads_a_persisted_value(self):
        self._write("developer_mode: true\ndaemon_mode: false\n")
        self.assertIs(settings.read_setting("developer_mode", False), True)
        self.assertIs(settings.read_setting("daemon_mode", True), False)

    def test_missing_file_returns_the_default(self):
        self.assertEqual(settings.read_setting("developer_mode", False), False)
        self.assertEqual(settings.read_setting("developer_mode", "fallback"), "fallback")

    def test_missing_key_returns_the_default(self):
        # An older config predating the key — must not blow up the launch.
        self._write("daemon_mode: true\n")
        self.assertIs(settings.read_setting("developer_mode", False), False)

    def test_malformed_yaml_returns_the_default(self):
        self._write("developer_mode: [unclosed\n")
        self.assertIs(settings.read_setting("developer_mode", False), False)

    def test_non_mapping_yaml_returns_the_default(self):
        # A file that parses but isn't a mapping would break .get().
        self._write("- just\n- a list\n")
        self.assertIs(settings.read_setting("developer_mode", False), False)

    def test_empty_file_returns_the_default(self):
        self._write("")
        self.assertIs(settings.read_setting("developer_mode", False), False)

    def test_does_not_create_the_file(self):
        # PolySettings() would write it; the early lookup must leave the disk alone.
        settings.read_setting("developer_mode", False)
        self.assertFalse(os.path.exists(self.path))


class DeveloperModeDefaultTest(unittest.TestCase):
    def test_developer_mode_is_a_known_key_and_defaults_off(self):
        # polyctl settings set developer_mode true relies on it being in defaults
        # (load() drops any key that isn't).
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("polyhost.settings.user_config_dir", return_value=tmp):
                s = settings.PolySettings()
        self.assertIn("developer_mode", s.defaults)
        self.assertIs(s.get("developer_mode"), False)


if __name__ == "__main__":
    unittest.main()
