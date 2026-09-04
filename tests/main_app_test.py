"""Startup diagnostic logging (the pre-GUI launch phase).

The daemon spawn/attach decision, autostart and single-instance handling run
before PolyHost/HeadlessHost configure logging, and on Windows under pythonw.exe
``print()`` is a silent no-op — so ``_setup_startup_logging`` must capture that
phase to ``startup_log.txt`` even with no console, and without disturbing the
root logger that ``logging.basicConfig`` configures later.
"""
import logging
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

from polyhost import main_app


class StartupLoggingTest(unittest.TestCase):
    def setUp(self):
        # Each test gets a clean dedicated logger + a scratch cwd for the file.
        lg = logging.getLogger("PolyHostStartup")
        for h in list(lg.handlers):
            lg.removeHandler(h)
        self._tmp = tempfile.TemporaryDirectory()
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)

    def tearDown(self):
        lg = logging.getLogger("PolyHostStartup")
        for h in list(lg.handlers):
            h.close()
            lg.removeHandler(h)
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def test_writes_file_without_a_console(self):
        # Simulate pythonw.exe: no real stdout. A StreamHandler would raise here,
        # so the helper must skip it and still write the file handler.
        import sys
        real_stdout = sys.stdout
        sys.stdout = None
        try:
            slog = main_app._setup_startup_logging(0)
            slog.info("hello from %s", "pythonw")
        finally:
            sys.stdout = real_stdout
        for h in slog.handlers:
            h.flush()
        with open(os.path.join(self._tmp.name, "startup_log.txt"), encoding="utf-8") as f:
            self.assertIn("hello from pythonw", f.read())
        # Only the file handler — no stream handler was added (stdout was None).
        self.assertTrue(all(not isinstance(h, logging.StreamHandler)
                            or isinstance(h, logging.FileHandler)
                            for h in slog.handlers))

    def test_does_not_touch_root_logger(self):
        # Configuring the startup logger must leave the root untouched, or the
        # later basicConfig in PolyHost/HeadlessHost (a no-op once root has
        # handlers) would silently fail to create host_log.txt/daemon_log.txt.
        root_before = list(logging.getLogger().handlers)
        slog = main_app._setup_startup_logging(0)
        self.assertFalse(slog.propagate)
        self.assertEqual(list(logging.getLogger().handlers), root_before)

    def test_idempotent(self):
        slog1 = main_app._setup_startup_logging(0)
        n = len(slog1.handlers)
        slog2 = main_app._setup_startup_logging(0)
        self.assertIs(slog1, slog2)
        self.assertEqual(len(slog2.handlers), n)


class ResolveDevTest(unittest.TestCase):
    """--dev / the deprecated --debug / the developer_mode setting."""

    def test_no_flag_follows_the_setting_and_stays_at_info(self):
        # The setting governs the developer SURFACE only — log volume stays put,
        # so a user who ticks the box in Settings doesn't also get a DEBUG log.
        self.assertEqual(main_app.resolve_dev(None, None, True), (0, True, "setting"))
        self.assertEqual(main_app.resolve_dev(None, None, False), (0, False, "setting"))

    def test_flag_turns_developer_on_and_carries_the_verbosity(self):
        self.assertEqual(main_app.resolve_dev(1, None, False), (1, True, "--dev"))
        self.assertEqual(main_app.resolve_dev(2, None, False), (2, True, "--dev"))

    def test_dev_zero_forces_developer_off_over_an_enabled_setting(self):
        # The whole reason "flag absent" (None) must stay distinguishable from
        # --dev 0: this is how you reproduce a plain-mode report on a dev box.
        self.assertEqual(main_app.resolve_dev(0, None, True), (0, False, "--dev"))

    def test_legacy_debug_flag_still_works(self):
        level, developer, source = main_app.resolve_dev(None, 2, False)
        self.assertEqual((level, developer), (2, True))
        self.assertIn("deprecated", source)

    def test_dev_wins_over_legacy_debug(self):
        self.assertEqual(main_app.resolve_dev(0, 2, False), (0, False, "--dev"))


class SpawnedDaemonFlagsTest(unittest.TestCase):
    """What a GUI-spawned daemon inherits.

    The daemon re-resolves developer mode from its own argv, so the flag has to
    travel whenever it was GIVEN — including `--dev 0`. Dropping a falsey level
    would let the daemon fall back to the persisted developer_mode setting and
    re-enable developer behaviour (allow_key_injection lives in the core) after
    the user explicitly forced it off for this run.
    """

    class _Args:
        def __init__(self, dev=None, debug_legacy=None, ignore_version=False):
            self.dev = dev
            self.debug_legacy = debug_legacy
            self.ignore_version = ignore_version

    def test_no_flag_passes_no_dev_flag(self):
        # The daemon reads developer_mode from the same settings file itself.
        self.assertEqual(main_app._spawned_daemon_flags(self._Args(), 0),
                         ["--no-autostart"])

    def test_verbosity_travels_as_dev(self):
        self.assertEqual(main_app._spawned_daemon_flags(self._Args(dev=2), 2),
                         ["--no-autostart", "--dev", "2"])

    def test_legacy_debug_launch_reaches_the_daemon_as_dev(self):
        self.assertEqual(main_app._spawned_daemon_flags(self._Args(debug_legacy=2), 2),
                         ["--no-autostart", "--dev", "2"])

    def test_explicit_dev_zero_still_travels(self):
        # The regression this guards: --dev 0 + developer_mode=true in settings
        # must NOT give the daemon developer mode.
        self.assertEqual(main_app._spawned_daemon_flags(self._Args(dev=0), 0),
                         ["--no-autostart", "--dev", "0"])

    def test_explicit_debug_zero_still_travels(self):
        self.assertEqual(main_app._spawned_daemon_flags(self._Args(debug_legacy=0), 0),
                         ["--no-autostart", "--dev", "0"])

    def test_ignore_version_still_propagates(self):
        self.assertEqual(
            main_app._spawned_daemon_flags(self._Args(dev=1, ignore_version=True), 1),
            ["--no-autostart", "--dev", "1", "--ignore-version"])


class WindowsAppIdTest(unittest.TestCase):
    """The taskbar identity — the Windows counterpart of setDesktopFileName().

    Windows groups taskbar buttons by AppUserModelID and identifies a process that
    never sets one by its HOST EXECUTABLE, so the button showed pythonw.exe's Python
    icon no matter what the window icon was (field, 2026-09-04). It is not reachable
    from Linux, so what is testable here is the wiring: that it is asked for on
    Windows, asked for nowhere else, and cannot take the tray down when it fails.
    """

    def _fake_ctypes(self, recorder, boom=False):
        mod = types.ModuleType("ctypes")

        class _Shell:
            @staticmethod
            def SetCurrentProcessExplicitAppUserModelID(app_id):  # noqa: N802 - Win32 name
                if boom:
                    raise OSError("no shell32 here")
                recorder.append(app_id)

        mod.windll = types.SimpleNamespace(shell32=_Shell)
        return mod

    def test_sets_the_id_on_windows(self):
        seen = []
        with mock.patch.object(main_app.sys, "platform", "win32"), \
             mock.patch.dict(sys.modules, {"ctypes": self._fake_ctypes(seen)}):
            self.assertTrue(main_app.set_windows_app_id())
        self.assertEqual(seen, [main_app.WINDOWS_APP_ID])

    def test_does_nothing_off_windows(self):
        seen = []
        for plat in ("linux", "darwin"):
            with mock.patch.object(main_app.sys, "platform", plat), \
                 mock.patch.dict(sys.modules, {"ctypes": self._fake_ctypes(seen)}):
                self.assertFalse(main_app.set_windows_app_id(), plat)
        self.assertEqual(seen, [], "must not touch shell32 off Windows")

    def test_a_failure_is_swallowed_and_logged(self):
        # Cosmetic: an exception here would take the tray down before it appeared.
        log = mock.Mock()
        with mock.patch.object(main_app.sys, "platform", "win32"), \
             mock.patch.dict(sys.modules, {"ctypes": self._fake_ctypes([], boom=True)}):
            self.assertFalse(main_app.set_windows_app_id(log))
        self.assertTrue(log.debug.called, "a swallowed failure must still be traceable")

    def test_the_id_is_stable_and_well_formed(self):
        # Windows keys pinned buttons and jump lists off this string, so renaming it
        # orphans a user's pinned icon. Pinned deliberately, not as a style check.
        self.assertEqual(main_app.WINDOWS_APP_ID, "PolyTasten.PolyKybd.PolyHost.1")
        self.assertLessEqual(len(main_app.WINDOWS_APP_ID), 128)   # Win32 limit
        self.assertNotIn(" ", main_app.WINDOWS_APP_ID)


if __name__ == "__main__":
    unittest.main()
