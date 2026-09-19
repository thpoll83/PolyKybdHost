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


class ConcurrentWriterTest(unittest.TestCase):
    """Two processes hold settings at once under daemon-by-default — the core
    daemon and the tray client — so a whole-file rewrite from a stale in-memory
    copy silently reverts the other one's work.

    That is not hypothetical. The GUI generated and saved the telemetry install
    id at 11:44:47; the daemon still held the empty value it had loaded at
    11:44:45; the daemon's next save at 11:53:16 wiped it, so the following run
    generated a fresh id and the machine counted as two installs (field,
    2026-09-19).
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.object(
            settings, "user_config_dir", return_value=self._tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_stale_writer_does_not_revert_the_other_process(self):
        daemon = settings.PolySettings()          # loads, install id == ""
        gui = settings.PolySettings()
        self.assertEqual(daemon.get("telemetry_install_id"), "")

        # The GUI generates and persists the id.
        gui.collection["telemetry_install_id"] = "d54c3950600b426fa5d7e3fa65f14ca3"
        gui.save()

        # The daemon saves minutes later from its stale copy. It must not
        # reimpose the empty id it loaded before the GUI wrote.
        daemon.save()
        self.assertEqual(
            settings.read_setting("telemetry_install_id"),
            "d54c3950600b426fa5d7e3fa65f14ca3")

    def test_each_process_keeps_its_own_change(self):
        """A merge per key, not per file: both writers' edits survive."""
        daemon = settings.PolySettings()
        gui = settings.PolySettings()

        gui.collection["browser_report_port"] = 10000
        gui.save()
        daemon.collection["hid_reconnect_retries"] = 9
        daemon.save()

        self.assertEqual(settings.read_setting("browser_report_port"), 10000)
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 9)

    def test_saving_picks_up_the_other_process_change(self):
        daemon = settings.PolySettings()
        gui = settings.PolySettings()
        gui.collection["browser_report_port"] = 10000
        gui.save()

        daemon.save()
        self.assertEqual(daemon.get("browser_report_port"), 10000)

    def test_an_explicit_change_still_wins_over_the_file(self):
        a = settings.PolySettings()
        b = settings.PolySettings()
        a.collection["hid_reconnect_retries"] = 3
        a.save()
        b.collection["hid_reconnect_retries"] = 7      # b changed it too, later
        b.save()
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 7)

    def test_restore_defaults_overwrites_every_key(self):
        a = settings.PolySettings()
        a.collection["hid_reconnect_retries"] = 9
        a.collection["browser_report_port"] = 10000
        a.save()
        a.restore_defaults()
        self.assertEqual(settings.read_setting("hid_reconnect_retries"),
                         a.defaults["hid_reconnect_retries"])
        self.assertEqual(settings.read_setting("browser_report_port"),
                         a.defaults["browser_report_port"])

    def test_restore_defaults_does_not_alias_the_defaults_table(self):
        """`collection = self.defaults` would make every later write mutate the
        defaults this process compares against, including save()'s merge."""
        a = settings.PolySettings()
        a.restore_defaults()
        a.collection["hid_reconnect_retries"] = 42
        self.assertNotEqual(a.defaults["hid_reconnect_retries"], 42)

    def test_save_is_atomic_leaving_no_temp_file_behind(self):
        a = settings.PolySettings()
        a.collection["hid_reconnect_retries"] = 4
        a.save()
        leftovers = [n for n in os.listdir(self._tmp.name) if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])
        # And the file it left is complete, parseable YAML.
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 4)

    def test_an_unreadable_file_does_not_break_a_save(self):
        """A save must never take the host down over a transiently unreadable
        config — it just means there are no other writer's keys to preserve."""
        a = settings.PolySettings()
        with open(a.path, "w", encoding="utf-8") as f:
            f.write("{{{ not yaml")
        a.collection["hid_reconnect_retries"] = 5
        a.save()
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 5)



if __name__ == "__main__":
    unittest.main()
