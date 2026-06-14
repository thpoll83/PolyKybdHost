"""daemon_launch — the daemon-by-default spawn/attach helper (headless-core H4b).

Pure decision table + a mocked spawn (no real process) + a polled wait against a
monkeypatched probe. Qt-free, no real device, no real subprocess.
"""
import subprocess
import sys
import unittest
from unittest import mock

from polyhost.server import daemon_launch as dl
from polyhost.server import instance as inst


class TestDecideStartupMode(unittest.TestCase):
    def test_daemon_mode_off_matches_legacy_single_instance(self):
        self.assertEqual(dl.decide_startup_mode(inst.STALE, False), dl.IN_PROCESS)
        self.assertEqual(dl.decide_startup_mode(inst.LIVE, False), dl.DEFER)
        self.assertEqual(dl.decide_startup_mode(inst.INCOMPATIBLE, False), dl.DEFER)
        self.assertEqual(dl.decide_startup_mode(inst.AUTH_MISMATCH, False), dl.DEFER)

    def test_daemon_mode_on_attaches_or_spawns(self):
        self.assertEqual(dl.decide_startup_mode(inst.LIVE, True), dl.CLIENT)
        self.assertEqual(dl.decide_startup_mode(inst.STALE, True), dl.SPAWN_CLIENT)
        # A real but incompatible owner must never be fought over.
        self.assertEqual(dl.decide_startup_mode(inst.INCOMPATIBLE, True), dl.DEFER)
        self.assertEqual(dl.decide_startup_mode(inst.AUTH_MISMATCH, True), dl.DEFER)


class TestBuildArgv(unittest.TestCase):
    def test_argv_is_this_interpreter_headless(self):
        argv = dl.build_daemon_argv()
        self.assertEqual(argv[0], sys.executable)
        self.assertEqual(argv[1:], ["-m", "polyhost", "--headless"])

    def test_extra_args_appended(self):
        argv = dl.build_daemon_argv(["--no-autostart", "--debug", "1"])
        self.assertEqual(argv[-3:], ["--no-autostart", "--debug", "1"])


class TestSpawn(unittest.TestCase):
    def test_spawn_is_detached_and_silent(self):
        with mock.patch.object(subprocess, "Popen") as popen:
            popen.return_value = mock.Mock(pid=4321)
            proc = dl.spawn_headless_daemon(["--no-autostart"])
        self.assertIsNotNone(proc)
        argv, kwargs = popen.call_args.args[0], popen.call_args.kwargs
        self.assertEqual(argv[1:], ["-m", "polyhost", "--headless", "--no-autostart"])
        # stdio detached so the daemon never inherits the GUI's console handles.
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
        if sys.platform == "win32":
            self.assertTrue(kwargs["creationflags"] & subprocess.DETACHED_PROCESS)
            self.assertTrue(kwargs["creationflags"] & subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            self.assertTrue(kwargs["start_new_session"])

    def test_spawn_failure_returns_none(self):
        with mock.patch.object(subprocess, "Popen", side_effect=OSError("no exec")):
            self.assertIsNone(dl.spawn_headless_daemon(log=None))


class TestWaitUntilLive(unittest.TestCase):
    def test_returns_true_once_live(self):
        outcomes = iter([inst.STALE, inst.STALE, inst.LIVE])
        with mock.patch.object(inst, "probe_existing",
                               side_effect=lambda *a, **k: next(outcomes)):
            self.assertTrue(dl.wait_until_live(timeout=2.0, poll_interval=0.0))

    def test_returns_false_on_timeout(self):
        with mock.patch.object(inst, "probe_existing", return_value=inst.STALE):
            self.assertFalse(dl.wait_until_live(timeout=0.05, poll_interval=0.01))


if __name__ == "__main__":
    unittest.main()
