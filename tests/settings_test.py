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

    def test_a_SAVE_over_an_unreadable_file_preserves_it_too(self):
        """⚠️ Startup preserves a corrupt settings.yaml and a SAVE destroyed it
        -- same file, same condition, opposite treatment, because the save path
        cannot tell "there is nothing there" from "there is something I cannot
        read". `_read_file()` answers `None` to both, so `_save_merged` wrote
        what it held straight over the top and the only copy was gone.

        The content a save cannot read is exactly the content worth keeping:
        another process's newer values, or the user's whole file after a bad
        write (Greptile, #240)."""
        a = settings.PolySettings()
        a.collection["hid_reconnect_retries"] = 9
        a.save()
        corrupt = "{{{ not yaml\nbrightness_gamma: 7\n"
        with open(a.path, "w", encoding="utf-8") as f:
            f.write(corrupt)

        a.collection["browser_report_port"] = 10001
        a.save()

        kept = [n for n in os.listdir(self._tmp.name) if ".unreadable-" in n]
        self.assertEqual(len(kept), 1,
                         f"the save destroyed it: {os.listdir(self._tmp.name)}")
        with open(os.path.join(self._tmp.name, kept[0]), encoding="utf-8") as f:
            self.assertEqual(f.read(), corrupt)   # byte-for-byte, recoverable
        # And the save still landed -- losing the write is not the alternative.
        self.assertEqual(settings.read_setting("browser_report_port"), 10001)

    def test_a_SECOND_corruption_does_not_DESTROY_the_first_copy(self):
        """⚠️ The kept name was `…unreadable-{strftime("%Y%m%d-%H%M%S")}`, i.e.
        one-second resolution, and `os.replace` overwrites silently. Two
        corruptions inside the same second therefore preserved the first copy
        and then destroyed it with the second — the one outcome this whole
        function exists to prevent (Greptile, #248, raised against the merge
        commit rather than that PR's diff).

        The stamp is pinned here rather than raced for: the collision is a
        property of the NAME, and a test that hopes two constructions land in
        the same wall-clock second is a test that passes for the wrong reason
        most of the time.

        Note the concurrent case was already safe and is not what this pins —
        the loser's `os.replace` raises FileNotFoundError once the winner has
        moved the file. This is two SEQUENTIAL corruptions."""
        a = settings.PolySettings()
        a.collection["hid_reconnect_retries"] = 9
        a.save()

        first = "{{{ not yaml -- the FIRST corruption\n"
        second = "{{{ not yaml -- the SECOND corruption, a moment later\n"
        with mock.patch.object(settings.time, "strftime",
                               return_value="20260101-000000"):
            for corrupt in (first, second):
                with open(a.path, "w", encoding="utf-8") as f:
                    f.write(corrupt)
                settings.PolySettings()      # preserves, then saves defaults

        kept = sorted(n for n in os.listdir(self._tmp.name)
                      if ".unreadable-" in n)
        self.assertEqual(len(kept), 2,
                         f"a copy was overwritten: {os.listdir(self._tmp.name)}")
        bodies = set()
        for name in kept:
            with open(os.path.join(self._tmp.name, name), encoding="utf-8") as f:
                bodies.add(f.read())
        # BOTH are recoverable, byte-for-byte -- not just the newer one.
        self.assertEqual(bodies, {first, second})

    def test_an_ABSENT_file_is_not_treated_as_unreadable(self):
        """The ordinary first save. Nothing is there to preserve, so preserving
        would leave a stray `.unreadable-` file on every clean first run --
        which is what conflating the two states buys you in the other
        direction.

        ⚠️ Asserted on the CALL, not on the absence of a `.unreadable-` file.
        `_preserve_unreadable` is `os.replace(path, kept)`, which on a missing
        path raises OSError, is caught, logs an error and leaves no file -- so
        an "is the directory clean" assertion passes whether or not the branch
        fired, and two mutations sailed through it."""
        from unittest import mock
        a = settings.PolySettings()
        os.unlink(a.path)
        a.collection["hid_reconnect_retries"] = 7
        with mock.patch.object(a, "_preserve_unreadable") as preserve:
            a.save()
        preserve.assert_not_called()
        kept = [n for n in os.listdir(self._tmp.name) if ".unreadable-" in n]
        self.assertEqual(kept, [])
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 7)

    def test_VALID_yaml_of_the_wrong_shape_is_unreadable_not_absent(self):
        """A file holding a list, or a bare string, parses fine and is useless
        -- but there ARE bytes there, so it is the case worth preserving. The
        parse succeeding is what makes this miss an exception-shaped test."""
        from unittest import mock
        a = settings.PolySettings()
        a.save()
        wrong = "- hid_reconnect_retries\n- brightness_gamma\n"
        with open(a.path, "w", encoding="utf-8") as f:
            f.write(wrong)
        a.collection["hid_reconnect_retries"] = 6
        with mock.patch.object(a, "_preserve_unreadable",
                               wraps=a._preserve_unreadable) as preserve:
            a.save()
        preserve.assert_called_once_with()
        kept = [n for n in os.listdir(self._tmp.name) if ".unreadable-" in n]
        self.assertEqual(len(kept), 1)
        with open(os.path.join(self._tmp.name, kept[0]), encoding="utf-8") as f:
            self.assertEqual(f.read(), wrong)
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 6)

    def test_the_file_is_preserved_ONCE_not_on_every_save(self):
        """After the first save the file is readable again, so a second save
        must find nothing to preserve -- otherwise a corrupt file turns into a
        directory full of dated copies."""
        a = settings.PolySettings()
        a.save()
        with open(a.path, "w", encoding="utf-8") as f:
            f.write("{{{ not yaml")
        a.collection["hid_reconnect_retries"] = 3
        a.save()
        a.collection["hid_reconnect_retries"] = 4
        a.save()
        kept = [n for n in os.listdir(self._tmp.name) if ".unreadable-" in n]
        self.assertEqual(len(kept), 1)
        self.assertEqual(settings.read_setting("hid_reconnect_retries"), 4)

    def test_INVALID_UTF8_is_unreadable_rather_than_an_exception(self):
        """⚠️ `UnicodeDecodeError` is a ValueError, not an OSError, so it was
        caught by neither arm and escaped `_read_file` entirely -- taking the
        CONSTRUCTOR down on a corrupt file, which is the #246 defect through a
        door that fix did not close, and raising out of `save()`.

        Pre-existing on `main` (measured: `PolySettings()` and `save()` both
        raise there), but it is the commonest way a settings file becomes
        unreadable -- a write truncated mid multi-byte character -- so a change
        whose whole subject is the unreadable file cannot leave it open
        (Greptile P1, #249)."""
        a = settings.PolySettings()
        a.collection["hid_reconnect_retries"] = 9
        a.save()
        corrupt = b"hid_reconnect_retries: 4\n\xff\xfe not utf-8\n"
        with open(a.path, "wb") as f:
            f.write(corrupt)

        self.assertEqual(a._read_file_ex(), (None, a.READ_UNREADABLE))

        b = settings.PolySettings()          # startup must not raise
        b.collection["browser_report_port"] = 10003
        b.save()                             # nor must the save
        self.assertEqual(settings.read_setting("browser_report_port"), 10003)
        kept = [n for n in os.listdir(self._tmp.name) if ".unreadable-" in n]
        self.assertTrue(kept, "the undecodable original was not preserved")
        with open(os.path.join(self._tmp.name, kept[0]), "rb") as f:
            self.assertEqual(f.read(), corrupt)   # byte-for-byte, recoverable

    @staticmethod
    def _preservation_cannot_reserve_a_name():
        """Obstruct ONLY `_preserve_unreadable`'s own `mkstemp` reservation.

        ⚠️ Shared by both callers on purpose. Two tests obstructed the
        preservation by squatting a DIRECTORY on the exact name it would pick,
        and that worked only while the name was predictable; when it stopped
        being, one of them was fixed and the other silently went vacuous
        (Sourcery, #253). One helper means the next change to the mechanism
        cannot fix half the callers.

        Scoped to the preservation's own call, so `_save_merged`'s temp-file
        write still works -- a blanket failure makes the save abort on its own
        writer, and then the save-abort test passes without the stand-down it
        exists to pin. (A read-only config dir would be the real-collision
        equivalent, but this suite runs as root, where it is no obstruction at
        all -- measured, not assumed.)

        Returns ``(patcher, refused)``. ⚠️ **Assert `refused` is truthy.**
        "No backup file appeared" does NOT prove the failure path ran -- it is
        equally true when `_preserve_unreadable` is never CALLED, which is the
        other half of what these tests cannot see on their own.
        """
        real_mkstemp = tempfile.mkstemp
        refused = []

        def side_effect(*args, **kwargs):
            if "unreadable" in kwargs.get("prefix", ""):
                refused.append(kwargs["prefix"])
                raise OSError(13, "Permission denied")
            return real_mkstemp(*args, **kwargs)

        return (mock.patch.object(settings.tempfile, "mkstemp",
                                  side_effect=side_effect), refused)

    def test_a_save_ABORTS_when_the_original_cannot_be_preserved(self):
        """⚠️ `_preserve_unreadable` swallows its OSError, so the save used to
        carry on and `os.replace` destroyed the very file the preservation
        exists to keep (Greptile P1, #249).

        The trade is deliberate and it is not symmetric: the file is
        unparseable, so its ONLY value is hand-recovery, and overwriting it
        removes the last copy for good. A save that does not land costs the
        user one setting change they can make again. So the overwrite stands
        down -- loudly -- and the in-memory value stays pending for the next
        save once the obstruction is gone."""
        a = settings.PolySettings()
        a.collection["hid_reconnect_retries"] = 9
        a.save()
        corrupt = "{{{ not yaml\nbrightness_gamma: 7\n"
        with open(a.path, "w", encoding="utf-8") as f:
            f.write(corrupt)

        # ⚠️ This used to squat a DIRECTORY on the exact name
        # `_preserve_unreadable` would pick. That worked only while the name
        # was PREDICTABLE, and it is not any more -- it is reserved with
        # `mkstemp` so two corruptions in one second cannot collide. The
        # obstruction has to be the syscall now. (A read-only config dir would
        # be the real-collision equivalent, but the suite runs as root here,
        # where it is not an obstruction at all -- measured, not assumed.)
        #
        # It is scoped to the PRESERVATION's own call, so `_save_merged`'s
        # temp-file write still works: with a blanket failure the save would
        # abort on its own writer and this test would pass without the
        # stand-down it exists to pin.
        obstruction, refused = self._preservation_cannot_reserve_a_name()
        with obstruction:
            a.collection["browser_report_port"] = 10004
            a.save()
        self.assertTrue(refused, "preservation was never attempted")

        with open(a.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), corrupt, "the save destroyed the original")
        self.assertEqual(a.collection["browser_report_port"], 10004)  # still pending

    def test_the_CONSTRUCTOR_still_comes_up_when_preservation_fails(self):
        """Startup cannot abort -- it has to hand back a usable PolySettings --
        so only the SAVE path gates on the preserve result. Same helper, two
        callers, opposite obligations."""
        a = settings.PolySettings()
        a.save()
        with open(a.path, "w", encoding="utf-8") as f:
            f.write("{{{ not yaml")
        obstruction, refused = self._preservation_cannot_reserve_a_name()
        with obstruction:
            b = settings.PolySettings()      # must not raise
        self.assertEqual(b.get("hid_reconnect_retries"),
                         b.defaults["hid_reconnect_retries"])
        # ⚠️ Without this the test is VACUOUS, which is exactly what it became
        # when the kept name stopped being predictable: it used to obstruct by
        # squatting a DIRECTORY on `{path}.unreadable-{stamp}`, `mkstemp` then
        # picked a different random suffix, preservation SUCCEEDED, and "the
        # constructor did not raise" held for a reason that had nothing to do
        # with a failure it was no longer producing (Sourcery, #253). Assert
        # the failure path was really taken, not just that startup survived.
        # ⚠️ TWO, and counting them is the whole point: the constructor
        # preserves, and then its own save preserves again (the corrupt file is
        # still there, because startup does NOT stand down). A bare "at least
        # one" is satisfied by the SAVE's call alone, so it passes even when the
        # constructor skips preservation entirely -- the other half of what
        # Sourcery flagged, and it is not visible from "no backup appeared"
        # either. Mutation-checked: dropping the constructor's call makes this 1.
        self.assertEqual(len(refused), 2,
                         "expected the CONSTRUCTOR and its save to each attempt "
                         f"preservation; got {len(refused)}")
        self.assertEqual([n for n in os.listdir(self._tmp.name)
                          if ".unreadable-" in n], [],
                         "preservation SUCCEEDED -- this test proves nothing")

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
