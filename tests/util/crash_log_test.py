"""Tests for the crash capture (polyhost/util/crash_log.py).

Installing global hooks is invasive, so every test restores ``sys.excepthook``,
``threading.excepthook`` and the module's own state in tearDown.
"""
import faulthandler
import logging
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from polyhost.util import crash_log


class CollectingLogger(logging.Logger):
    """Logger that records (level, message, exc_info) instead of emitting."""

    def __init__(self):
        super().__init__("crash-log-test")
        self.records = []

    def handle(self, record):
        self.records.append(record)

    def levels(self):
        return [r.levelno for r in self.records]


class CrashLogTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "crash_log.txt"
        self.log = CollectingLogger()
        self._saved_excepthook = sys.excepthook
        self._saved_threadhook = threading.excepthook
        # Chain into a no-op by default: the real default hook prints the test's
        # deliberate traceback to stderr, and a suite that prints tracebacks on a
        # green run teaches people to ignore them.
        sys.excepthook = lambda *_a: None

    def tearDown(self):
        sys.excepthook = self._saved_excepthook
        threading.excepthook = self._saved_threadhook
        faulthandler.disable()
        if crash_log._crash_file is not None:
            crash_log._crash_file.close()
        crash_log._crash_file = None
        crash_log._installed = False
        self._tmp.cleanup()

    def text(self):
        return self.path.read_text(encoding="utf-8")


class InstallTest(CrashLogTestBase):
    def test_writes_a_pid_stamped_session_marker(self):
        self.assertTrue(crash_log.install(self.log, str(self.path)))
        self.assertIn("session start", self.text())
        self.assertIn("pid %d" % os.getpid(), self.text())

    def test_is_idempotent(self):
        crash_log.install(self.log, str(self.path))
        hook = sys.excepthook
        self.assertFalse(crash_log.install(self.log, str(self.path)))
        self.assertIs(sys.excepthook, hook)     # not re-wrapped on every call

    def test_enables_faulthandler_against_our_file_not_stderr(self):
        """`file=` is load-bearing: under pythonw stderr is None and the default
        would raise, leaving no native-fault capture at all."""
        crash_log.install(self.log, str(self.path))
        self.assertTrue(faulthandler.is_enabled())

    def test_unwritable_path_still_installs_the_hooks(self):
        before = sys.excepthook
        crash_log.install(self.log, str(self.path / "no" / "such" / "dir.txt"))
        self.assertIsNot(sys.excepthook, before)
        self.assertIsNone(crash_log._crash_file)
        self.assertEqual(self.log.levels(), [logging.WARNING])


class ExceptHookTest(CrashLogTestBase):
    def _raise_through_hook(self):
        try:
            raise ValueError("boom")
        except ValueError:
            sys.excepthook(*sys.exc_info())

    def test_logs_the_traceback_and_records_it_in_the_crash_file(self):
        crash_log.install(self.log, str(self.path))
        self._raise_through_hook()
        self.assertEqual(self.log.levels(), [logging.CRITICAL])
        self.assertIsNotNone(self.log.records[0].exc_info)
        body = self.text()
        self.assertIn("unhandled exception: ValueError: boom", body)
        self.assertIn("ValueError: boom", body)
        self.assertIn("_raise_through_hook", body)   # the real traceback, not just a label

    def test_chains_to_the_previously_installed_hook(self):
        seen = []
        sys.excepthook = lambda *a: seen.append(a)
        crash_log.install(self.log, str(self.path))
        self._raise_through_hook()
        self.assertEqual(len(seen), 1)

    def test_a_failing_previous_hook_cannot_break_reporting(self):
        def angry(*_a):
            raise RuntimeError("hook is broken")
        sys.excepthook = angry
        crash_log.install(self.log, str(self.path))
        self._raise_through_hook()                  # must not propagate
        self.assertEqual(self.log.levels(), [logging.CRITICAL])


class ThreadHookTest(CrashLogTestBase):
    def test_reports_a_thread_that_dies(self):
        crash_log.install(self.log, str(self.path))

        def explode():
            raise KeyError("worker died")

        t = threading.Thread(target=explode, name="test-worker")
        t.start()
        t.join()
        self.assertEqual(self.log.levels(), [logging.CRITICAL])
        self.assertIn("test-worker", self.text())

    def test_ignores_systemexit(self):
        crash_log.install(self.log, str(self.path))

        def bail():
            raise SystemExit(0)

        t = threading.Thread(target=bail, name="quitting")
        t.start()
        t.join()
        self.assertEqual(self.log.levels(), [])


class CleanExitTest(CrashLogTestBase):
    def test_marks_a_deliberate_exit(self):
        crash_log.install(self.log, str(self.path))
        crash_log.note_clean_exit(self.log, "Qt event loop", 0)
        self.assertIn("clean exit (Qt event loop, rc=0)", self.text())

    def test_a_crashed_session_has_no_matching_exit_marker(self):
        """The whole diagnostic value is in the absence of this line."""
        crash_log.install(self.log, str(self.path))
        self._had = self.text()
        self.assertIn("session start", self._had)
        self.assertNotIn("clean exit", self._had)


if __name__ == "__main__":
    unittest.main()
