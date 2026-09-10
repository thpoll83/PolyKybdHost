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


class WriteSettingsTest(unittest.TestCase):
    """The file-only writer `read_setting`'s sibling.

    PolyForwarder records where it pushes here at every startup, so this runs on a
    path that must not construct PolySettings (which creates the config dir, merges
    and re-saves every default, and log-dumps the lot) and must never raise.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self._tmp.name, "cfg")
        self.path = os.path.join(self.dir, "settings.yaml")
        self._patch = mock.patch("polyhost.settings.user_config_dir",
                                 return_value=self.dir)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _read(self):
        import yaml
        with open(self.path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def test_it_writes_into_a_config_dir_that_does_not_exist_yet(self):
        self.assertTrue(settings.write_settings(forwarder_host="keeb-box"))
        self.assertEqual(self._read()["forwarder_host"], "keeb-box")

    def test_it_MERGES_rather_than_replacing_the_file(self):
        """The forwarder writes two keys; everything else in there is somebody's
        settings and a whole-file write would take them with it."""
        settings.write_settings(ui_theme="light", telemetry_enabled=False)
        settings.write_settings(forwarder_host="keeb-box")
        data = self._read()
        self.assertEqual(data["ui_theme"], "light")
        self.assertIs(data["telemetry_enabled"], False)
        self.assertEqual(data["forwarder_host"], "keeb-box")

    def test_an_UNCHANGED_write_does_not_touch_the_file(self):
        """This runs at every forwarder launch, so rewriting the file each time is
        pure churn -- and a needless race with a PolyHost saving its own settings on
        the same machine."""
        settings.write_settings(forwarder_host="keeb-box")
        before = os.stat(self.path)
        os.utime(self.path, (before.st_atime - 10, before.st_mtime - 10))
        stamp = os.stat(self.path).st_mtime
        self.assertTrue(settings.write_settings(forwarder_host="keeb-box"))
        self.assertEqual(os.stat(self.path).st_mtime, stamp)

    def test_a_CHANGED_value_is_written_even_when_a_sibling_matches(self):
        """A forwarder repointed --host-file -> --host writes one key that already
        matches ("" stays "") and one that does not; an all-or-nothing compare that
        got the quantifier wrong would skip the whole write."""
        settings.write_settings(forwarder_host="first-box", forwarder_host_file="")
        settings.write_settings(forwarder_host="second-box", forwarder_host_file="")
        self.assertEqual(self._read()["forwarder_host"], "second-box")

    def test_a_MALFORMED_file_is_replaced_rather_than_raising(self):
        os.makedirs(self.dir, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{{{ not yaml")
        self.assertTrue(settings.write_settings(forwarder_host="keeb-box"))
        self.assertEqual(self._read()["forwarder_host"], "keeb-box")

    def test_a_file_holding_a_LIST_is_replaced_rather_than_raising(self):
        """Valid YAML, wrong shape -- `.get` on a list is an AttributeError, and this
        is startup code in a tray app with no console."""
        os.makedirs(self.dir, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("- one\n- two\n")
        self.assertTrue(settings.write_settings(forwarder_host="keeb-box"))
        self.assertEqual(self._read()["forwarder_host"], "keeb-box")

    def test_an_UNWRITABLE_location_reports_False_and_does_not_raise(self):
        with mock.patch("polyhost.settings.user_config_dir",
                        return_value="/proc/nope/cfg"):
            self.assertFalse(settings.write_settings(forwarder_host="keeb-box"))


if __name__ == "__main__":
    unittest.main()
