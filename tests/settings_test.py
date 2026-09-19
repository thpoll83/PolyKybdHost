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
        config."""
        a = settings.PolySettings()
        with open(a.path, "w", encoding="utf-8") as f:
            f.write("{{{ not yaml")
        a.collection["hid_reconnect_retries"] = 5
        a.save()
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 5)

    def test_an_unreadable_file_does_not_RESET_the_other_settings(self):
        """`None` and `{}` from _read_file mean different things, and the
        difference is destructive: merging against `{}` fills every key this
        process did not change with a DEFAULT, so one transient read error
        would silently reset the user's other settings (Greptile, #245)."""
        a = settings.PolySettings()
        a.collection["hid_reconnect_retries"] = 9
        a.collection["browser_report_port"] = 10000
        a.save()

        b = settings.PolySettings()          # loads both customised values
        with open(b.path, "w", encoding="utf-8") as f:
            f.write("{{{ not yaml")          # now the file cannot be read
        b.collection["irradiance_gamma"] = b.collection.get("brightness_gamma")
        b.collection["brightness_gamma"] = 2.0
        b.save()

        # The key we changed is persisted, and the two we did NOT change must
        # survive as the user's values rather than snapping back to defaults.
        self.assertEqual(settings.read_setting("brightness_gamma"), 2.0)
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 9)
        self.assertEqual(settings.read_setting("browser_report_port"), 10000)
        self.assertNotEqual(a.defaults["hid_reconnect_retries"], 9)   # a real contrast

    def test_startup_on_an_unreadable_file_preserves_it(self):
        """Starting up used to RAISE on a corrupt settings.yaml; degrading to
        defaults is kinder, but the constructor saves straight afterwards — so
        without preserving it, the first launch after a bad write destroys the
        only copy (Greptile, #246)."""
        a = settings.PolySettings()
        a.collection["hid_reconnect_retries"] = 9
        a.save()
        corrupt = "{{{ not yaml\nbrightness_gamma: 7\n"
        with open(a.path, "w", encoding="utf-8") as f:
            f.write(corrupt)

        settings.PolySettings()          # a normal startup on the bad file

        kept = [n for n in os.listdir(self._tmp.name) if ".unreadable-" in n]
        self.assertEqual(len(kept), 1, f"original not preserved: {os.listdir(self._tmp.name)}")
        with open(os.path.join(self._tmp.name, kept[0]), encoding="utf-8") as f:
            self.assertEqual(f.read(), corrupt)   # byte-for-byte, hand-recoverable
        # And the app still came up, on defaults.
        self.assertEqual(settings.read_setting("hid_reconnect_retries"),
                         a.defaults["hid_reconnect_retries"])

    def test_an_unknown_key_never_reaches_the_file(self):
        """`mine` is applied after _normalize, so without a re-filter a key
        absent from `defaults` rides into the file on the delta and is never
        dropped again (Greptile, #246)."""
        a = settings.PolySettings()
        a.collection["not_a_real_setting"] = "x"
        a.save()
        self.assertIsNone(settings.read_setting("not_a_real_setting"))

    def test_each_save_uses_its_own_temp_file(self):
        """The lock is best effort, so two threads in one process can both be
        writing — a pid-based temp name would have them share one path."""
        a = settings.PolySettings()
        seen = []
        real = settings.tempfile.mkstemp

        def _watch(**kw):
            fd, path = real(**kw)
            seen.append(path)
            return fd, path

        with mock.patch.object(settings.tempfile, "mkstemp", _watch):
            a.collection["hid_reconnect_retries"] = 3
            a.save()
            a.collection["hid_reconnect_retries"] = 4
            a.save()
        self.assertEqual(len(seen), 2)
        self.assertNotEqual(seen[0], seen[1])
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 4)

    def test_a_save_holds_the_settings_lock(self):
        """read -> merge -> replace is itself a read-modify-write: without a
        cross-process lock two hosts saving at once both read the same base and
        the second replace discards the first's update (Greptile, #245)."""
        from polyhost.util import filelock

        a = settings.PolySettings()
        seen = []
        real = filelock.try_lock

        def _watch(fd):
            got = real(fd)
            seen.append(got)
            return got

        with mock.patch.object(filelock, "try_lock", _watch):
            a.collection["hid_reconnect_retries"] = 6
            a.save()
        self.assertTrue(seen and seen[0], "save() did not take the settings lock")
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 6)

    def test_a_wedged_lock_still_lets_the_save_through(self):
        """Best effort on purpose — losing a save to a stuck lock holder is
        worse than the rare interleaving the lock prevents."""
        from polyhost.util import filelock

        a = settings.PolySettings()
        with mock.patch.object(filelock, "try_lock", return_value=False), \
             mock.patch.object(settings, "SAVE_LOCK_TIMEOUT_S", 0):
            a.collection["hid_reconnect_retries"] = 7
            a.save()
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 7)



if __name__ == "__main__":
    unittest.main()
