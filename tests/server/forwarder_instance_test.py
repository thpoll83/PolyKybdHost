"""The forwarder's single-instance lock.

⚠️ These live here, and not in a forwarder test, because `polyhost/forwarder.py`
imports pywinctl at module load and cannot be imported in the documented test
environment at all (CLAUDE.md). That is the same reason the `--host-file`
reconnect fix put its logic in `server/window_report_client.py`: the testable
part goes in a Qt-free module and the forwarder keeps only the call.
"""
import os
import subprocess
import sys
import unittest
from unittest import mock

from polyhost.server import instance


def _acquire_in_subprocess(name, cfg):
    """Try the lock from a SEPARATE process; 'held' or 'free'."""
    code = ("import sys; sys.argv=['x'];"
            "from polyhost.server import instance;"
            f"print('free' if instance.acquire_singleton({name!r}) else 'held')")
    env = dict(os.environ, XDG_CONFIG_HOME=cfg)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, env=env, cwd=os.getcwd())
    return r.stdout.strip()


class ForwarderLockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"),
                                f"polylock_{os.getpid()}")
        os.makedirs(self.tmp, exist_ok=True)
        self._old = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = self.tmp

    def tearDown(self):
        if self._old is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self._old

    def test_the_first_caller_gets_a_handle(self):
        h = instance.acquire_singleton("t1")
        self.addCleanup(h.close)
        self.assertIsNotNone(h)

    def test_a_SECOND_PROCESS_is_refused_while_the_first_holds_it(self):
        """The whole point: this is what stops a second forwarder."""
        if sys.platform == "win32":
            self.skipTest("POSIX flock semantics")
        h = instance.acquire_singleton("t2")
        self.addCleanup(h.close)
        self.assertEqual(_acquire_in_subprocess("t2", self.tmp), "held")

    def test_releasing_the_handle_frees_it_for_the_next_process(self):
        """⚠️ Pins that the HANDLE is the lock. A version that kept the lock
        after close -- or never really took one -- passes the test above and
        fails this, which is the half that matters after a forwarder quits."""
        if sys.platform == "win32":
            self.skipTest("POSIX flock semantics")
        h = instance.acquire_singleton("t3")
        self.assertEqual(_acquire_in_subprocess("t3", self.tmp), "held")
        h.close()
        self.assertEqual(_acquire_in_subprocess("t3", self.tmp), "free")

    def test_a_lock_survives_a_CRASHED_holder(self):
        """No stale-lock cleanup is needed, unlike `probe_existing`'s socket:
        the kernel drops the lock when it closes a dead process's descriptors."""
        if sys.platform == "win32":
            self.skipTest("POSIX flock semantics")
        code = ("import os, sys, time; sys.argv=['x'];"
                "from polyhost.server import instance;"
                "h = instance.acquire_singleton('t4');"
                "print('got', flush=True); os.kill(os.getpid(), 9)")
        env = dict(os.environ, XDG_CONFIG_HOME=self.tmp)
        subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, env=env, cwd=os.getcwd())
        h = instance.acquire_singleton("t4")
        self.addCleanup(h.close)
        self.assertIsNotNone(h, "a SIGKILLed holder must not block the next launch")

    def test_an_unwritable_config_dir_STARTS_ANYWAY(self):
        """Fail OPEN. A duplicate forwarder is a degradation; refusing to launch
        over an unrelated filesystem fault leaves the user with none at all.
        ⚠️ It must not return None -- None is the caller's signal to exit."""
        with mock.patch("os.makedirs", side_effect=OSError("read-only")):
            h = instance.acquire_singleton("t5")
        self.addCleanup(h.close)        # the stand-in must still be closeable
        self.assertIsNotNone(h)

    def test_it_never_raises_when_locking_is_unsupported(self):
        with mock.patch("fcntl.flock", side_effect=RuntimeError("no flock")):
            h = instance.acquire_singleton("t6")
        self.addCleanup(h.close)
        self.assertIsNotNone(h)

    def test_the_refusal_log_line_names_the_HOLDING_PID(self):
        """The log line is the whole user-facing half of this feature -- without
        it a second launch just vanishes with no way to tell why.

        ⚠️ The first version of this test asserted nothing at all (an
        `assertIsNone(... if False else None)` left behind while working out
        whether same-process re-entry is refused). It is: `flock` binds to the
        open file DESCRIPTION, so a second `open()` conflicts even in one
        process -- which is what makes this testable without a subprocess.
        """
        if sys.platform == "win32":
            self.skipTest("POSIX flock semantics")
        h = instance.acquire_singleton("t7")
        self.addCleanup(h.close)
        log = mock.MagicMock()
        self.assertIsNone(instance.acquire_singleton("t7", log))
        log.warning.assert_called_once()
        rendered = log.warning.call_args[0][0] % log.warning.call_args[0][1:]
        self.assertIn(str(os.getpid()), rendered,
                      "the refusal must name who holds the lock")
        self.assertIn("already running", rendered)

    def test_the_pid_is_written_so_the_NEXT_process_can_read_it(self):
        """Pins the write, not just the message: the holder records its pid, and
        a refused caller reads it back out of the locked file."""
        if sys.platform == "win32":
            self.skipTest("POSIX flock semantics")
        h = instance.acquire_singleton("t8")
        self.addCleanup(h.close)
        with open(instance._lock_path("t8")) as f:
            self.assertEqual(f.read().strip(), str(os.getpid()))


if __name__ == "__main__":
    unittest.main()
