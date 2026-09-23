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
        crash_log.stop_dump_watch()
        sys.excepthook = self._saved_excepthook
        threading.excepthook = self._saved_threadhook
        faulthandler.disable()
        if crash_log._crash_file is not None:
            crash_log._crash_file.close()
        crash_log._crash_file = None
        crash_log._installed = False
        crash_log._clean_exit_noted = False
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


class ThreadHookChainingTest(CrashLogTestBase):
    """The thread hook reports; it does not replace what was there before."""

    def test_chains_to_the_previous_thread_hook(self):
        seen = []
        threading.excepthook = lambda args: seen.append(args.exc_type)
        crash_log.install(self.log, str(self.path))
        t = threading.Thread(target=lambda: (_ for _ in ()).throw(KeyError("x")))
        t.start()
        t.join()
        self.assertEqual(seen, [KeyError])

    def test_chains_even_for_systemexit_which_we_do_not_report(self):
        """The stdlib default ignores SystemExit, so we must not invent noise —
        but the previous hook still gets to decide for itself."""
        seen = []
        threading.excepthook = lambda args: seen.append(args.exc_type)
        crash_log.install(self.log, str(self.path))
        t = threading.Thread(target=lambda: (_ for _ in ()).throw(SystemExit(0)))
        t.start()
        t.join()
        self.assertEqual(seen, [SystemExit])
        self.assertEqual(self.log.levels(), [])      # reported by us: no

    def test_a_failing_previous_thread_hook_cannot_break_reporting(self):
        def angry(_args):
            raise RuntimeError("hook is broken")
        threading.excepthook = angry
        crash_log.install(self.log, str(self.path))
        t = threading.Thread(target=lambda: (_ for _ in ()).throw(KeyError("x")),
                             name="chained")
        t.start()
        t.join()
        self.assertEqual(self.log.levels(), [logging.CRITICAL])
        self.assertIn("chained", self.text())


class CleanExitTest(CrashLogTestBase):
    def test_marks_a_deliberate_exit(self):
        crash_log.install(self.log, str(self.path))
        crash_log.note_clean_exit(self.log, "Qt event loop", 0)
        self.assertIn("clean exit (Qt event loop, rc=0)", self.text())

    def test_atexit_marks_a_graceful_exit_nobody_announced(self):
        """The routine `sys.exit(0)` paths (a second launch finding the socket
        already served) must not read as crashes — atexit covers them all."""
        crash_log.install(self.log, str(self.path))
        crash_log._atexit_marker()
        self.assertIn("clean exit (interpreter shutdown)", self.text())

    def test_atexit_does_not_double_stamp_an_explicit_exit(self):
        crash_log.install(self.log, str(self.path))
        crash_log.note_clean_exit(self.log, "Qt event loop", 0)
        crash_log._atexit_marker()
        self.assertEqual(self.text().count("clean exit"), 1)

    def test_a_crashed_session_has_no_matching_exit_marker(self):
        """The whole diagnostic value is in the absence of this line."""
        crash_log.install(self.log, str(self.path))
        self._had = self.text()
        self.assertIn("session start", self._had)
        self.assertNotIn("clean exit", self._had)



class DumpWatchTest(CrashLogTestBase):
    """A faulthandler dump has no timestamp; the watch stamps one after it.

    The file is shared by the GUI and the daemon, so the other process is
    simulated by appending through a second handle, as faulthandler does."""

    def setUp(self):
        super().setUp()
        crash_log.install(self.log, str(self.path))

    def other(self, *lines):
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def dated_markers(self):
        return [line for line in self.text().splitlines()
                if crash_log.DUMP_DATED in line]

    def test_install_starts_the_watch_thread(self):
        names = [t.name for t in threading.enumerate()]
        self.assertIn("poly-crash-watch", names)

    def test_a_dump_gets_ONE_timed_marker(self):
        self.other("Windows fatal exception: code 0x80010108", "",
                   "Thread 0x00002430 (most recent call first):",
                   '  File "x.py", line 1 in f')
        self.assertFalse(crash_log.check_for_undated_dump())   # found: settle
        self.assertTrue(crash_log.check_for_undated_dump())    # steady: stamp
        self.assertFalse(crash_log.check_for_undated_dump())
        markers = self.dated_markers()
        self.assertEqual(len(markers), 1)
        self.assertIsNotNone(crash_log.parse_marker(markers[0]))

    def test_nothing_new_writes_nothing(self):
        before = self.text()
        self.assertFalse(crash_log.check_for_undated_dump())
        self.assertEqual(self.text(), before)

    def test_marker_growth_alone_is_never_answered(self):
        """Otherwise the GUI and the daemon would answer each other forever."""
        self.other(crash_log.format_marker("session start", 999))
        self.assertFalse(crash_log.check_for_undated_dump())
        self.assertEqual(self.dated_markers(), [])

    def test_a_dump_the_OTHER_process_already_dated_is_left_alone(self):
        self.other("Windows fatal exception: access violation",
                   crash_log.format_marker(crash_log.DUMP_DATED, 999))
        self.assertFalse(crash_log.check_for_undated_dump())
        self.assertEqual(len(self.dated_markers()), 1)

    def test_a_python_traceback_under_its_own_marker_is_not_a_dump(self):
        self.other(crash_log.format_marker("unhandled exception: KeyError", 999),
                   "Traceback (most recent call last):",
                   '  File "x.py", line 1, in f', "KeyError: 'x'")
        self.assertFalse(crash_log.check_for_undated_dump())

    def test_a_file_trimmed_by_another_process_is_not_an_error(self):
        self.other("Windows fatal exception: code 0x80010108")
        crash_log.check_for_undated_dump()
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("x\n")
        self.assertFalse(crash_log.check_for_undated_dump())

    def test_the_dated_marker_is_not_counted_as_an_exception(self):
        """crash_summary counts every marker containing 'exception'."""
        self.assertNotIn("exception", crash_log.DUMP_DATED)

    def test_a_dump_still_being_WRITTEN_is_not_split_by_a_marker(self):
        """faulthandler writes a dump in many small writes; a pause between
        the header and the thread list must not get a marker between them."""
        self.other("Windows fatal exception: code 0x80010108")
        self.assertFalse(crash_log.check_for_undated_dump())
        self.other("", "Thread 0x00002430 (most recent call first):")
        self.assertFalse(crash_log.check_for_undated_dump())   # grew: wait
        self.other('  File "x.py", line 1 in f')
        self.assertFalse(crash_log.check_for_undated_dump())   # grew: wait
        self.assertTrue(crash_log.check_for_undated_dump())    # steady
        lines = self.text().splitlines()
        self.assertIn(crash_log.DUMP_DATED, lines[-1])
        self.assertEqual(lines[-2], '  File "x.py", line 1 in f')

    def test_a_dump_cut_off_MID_LINE_is_still_dated_on_a_line_of_its_own(self):
        """The fatal dump in the 2026-09-23 field bundle stopped mid-line;
        a newline requirement would never date it."""
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("Windows fatal exception: access violation\n\n  File ")
        self.assertFalse(crash_log.check_for_undated_dump())
        self.assertTrue(crash_log.check_for_undated_dump())
        last = self.text().splitlines()[-1]
        self.assertIsNotNone(crash_log.parse_marker(last))

    def test_a_dump_written_after_a_TRUNCATION_is_still_found(self):
        """Another process trims the shared file and a dump lands before
        this process looks again; jumping to the new end would skip it."""
        self.other("x" * 4000)
        crash_log.check_for_undated_dump()
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(crash_log.format_marker("session start", 999) + "\n"
                     "Windows fatal exception: code 0x80010108\n")
        self.assertFalse(crash_log.check_for_undated_dump())
        self.assertTrue(crash_log.check_for_undated_dump())
        self.assertEqual(len(self.dated_markers()), 1)

    def test_a_FAILED_stamp_is_retried(self):
        self.other("Windows fatal exception: code 0x80010108")
        crash_log.check_for_undated_dump()
        real = crash_log._stamp
        crash_log._stamp = lambda *_a, **_k: False
        try:
            self.assertFalse(crash_log.check_for_undated_dump())
        finally:
            crash_log._stamp = real
        self.assertTrue(crash_log.check_for_undated_dump())
        self.assertEqual(len(self.dated_markers()), 1)

    def test_stop_ends_the_thread(self):
        crash_log.stop_dump_watch()
        names = [t.name for t in threading.enumerate()]
        self.assertNotIn("poly-crash-watch", names)


if __name__ == "__main__":
    unittest.main()


class TrimTest(unittest.TestCase):
    """The size bound on crash_log.txt (see trim_if_oversized's docstring).

    The file is the one source the bundle collector never time-slices, so its
    size is bundle size — these pin that a crash loop cannot grow it without
    limit, and that trimming keeps whole records rather than half a traceback.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "crash_log.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_sessions(self, n, dump_bytes=0):
        """n complete session records, optionally each with a fake dump."""
        with open(self.path, "w", encoding="utf-8") as fh:
            for i in range(n):
                fh.write(crash_log.format_marker("session start", 1000 + i) + "\n")
                if dump_bytes:
                    fh.write("Fatal Python error: Segmentation fault\n")
                    fh.write("x" * dump_bytes + "\n")
                fh.write(crash_log.format_marker("clean exit (test)", 1000 + i) + "\n")

    def test_a_small_file_is_left_completely_alone(self):
        self._write_sessions(3)
        before = self.path.read_bytes()
        self.assertFalse(crash_log.trim_if_oversized(self.path))
        self.assertEqual(self.path.read_bytes(), before)

    def test_a_missing_file_is_not_an_error(self):
        self.assertFalse(crash_log.trim_if_oversized(self.path))
        self.assertFalse(self.path.exists())

    def test_an_oversized_file_is_bounded(self):
        self._write_sessions(400, dump_bytes=6000)
        self.assertGreater(self.path.stat().st_size, crash_log.MAX_BYTES)
        self.assertTrue(crash_log.trim_if_oversized(self.path))
        # Bounded by what we keep, plus the note line — never by max_bytes.
        self.assertLessEqual(self.path.stat().st_size, crash_log.KEEP_BYTES + 4096)

    def test_it_keeps_the_NEWEST_records_not_the_oldest(self):
        # The crash being reported is the recent one; dropping the tail would
        # keep only history nobody is asking about.
        self._write_sessions(400, dump_bytes=6000)
        crash_log.trim_if_oversized(self.path)
        text = self.path.read_text(encoding="utf-8", errors="replace")
        self.assertIn("pid 1399", text)      # the last session written
        self.assertNotIn("pid 1000", text)   # the first

    def test_the_retained_text_starts_on_a_whole_record(self):
        self._write_sessions(400, dump_bytes=6000)
        crash_log.trim_if_oversized(self.path)
        lines = self.path.read_text(encoding="utf-8").splitlines()
        # Line 0 is the trim note; line 1 must be a marker, not the middle of
        # somebody's traceback.
        self.assertIsNotNone(crash_log.parse_marker(lines[0]))
        self.assertIsNotNone(crash_log.parse_marker(lines[1]))

    def test_the_trim_is_recorded_in_the_file(self):
        self._write_sessions(400, dump_bytes=6000)
        crash_log.trim_if_oversized(self.path)
        first = self.path.read_text(encoding="utf-8").splitlines()[0]
        what, _pid, _ts = crash_log.parse_marker(first)
        self.assertIn("trimmed", what)

    def test_the_result_is_still_valid_utf8_after_cutting_mid_character(self):
        # The seek lands at an arbitrary byte offset; a naive slice could split
        # a multi-byte character and make the whole file undecodable.
        with open(self.path, "w", encoding="utf-8") as fh:
            for i in range(200):
                fh.write(crash_log.format_marker("session start", 2000 + i) + "\n")
                fh.write("ünïcodé — ✓ " * 500 + "\n")
        self.assertGreater(self.path.stat().st_size, crash_log.MAX_BYTES)
        crash_log.trim_if_oversized(self.path)
        self.path.read_text(encoding="utf-8")  # must not raise

    def test_install_bounds_an_oversized_file_before_handing_it_to_faulthandler(self):
        # The integration that matters: install() is the single choke point, and
        # the trim has to happen while there is still no fd to disturb.
        self._write_sessions(400, dump_bytes=6000)
        saved_hook, saved_thread = sys.excepthook, threading.excepthook
        try:
            crash_log.install(CollectingLogger(), filename=str(self.path))
            size = self.path.stat().st_size
            self.assertLess(size, crash_log.MAX_BYTES)
            # …and the fresh session marker still landed, i.e. the file the
            # trim left behind is the one that got opened.
            self.assertIn("session start", self.path.read_text(encoding="utf-8"))
        finally:
            crash_log.stop_dump_watch()
            if crash_log._crash_file is not None:
                crash_log._crash_file.close()
            crash_log._crash_file = None
            crash_log._installed = False
            crash_log._clean_exit_noted = False
            faulthandler.disable()
            sys.excepthook, threading.excepthook = saved_hook, saved_thread


