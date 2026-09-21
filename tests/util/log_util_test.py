"""Regression tests for MultiLineFormatter (keyboard-console log file).

The old implementation re-emitted the first line (glued to itself without a
newline) and silently dropped the LAST line of every multi-line record —
i.e. the tail console message of each 250 ms flush never reached
polykybd_console.txt (seen in the field 2026-06-13).
"""
import logging
import unittest
import unittest.mock as mock

from polyhost.util.log_util import (MultiLineFormatter, RepeatCollapseHandler,
                                    make_stream_handler)


def _format(msg: str) -> str:
    formatter = MultiLineFormatter(fmt="[%(asctime)s] %(message)s")
    record = logging.LogRecord(
        name="PolyKybdConsole", level=logging.INFO, pathname=__file__,
        lineno=1, msg=msg, args=(), exc_info=None)
    return formatter.format(record)


class TestMultiLineFormatter(unittest.TestCase):

    def test_single_line_passes_through(self):
        out = _format("Overlay flags 0x1 set.")
        self.assertEqual(len(out.splitlines()), 1)
        self.assertTrue(out.endswith("Overlay flags 0x1 set."))
        self.assertRegex(out, r"^\[.+\] Overlay flags 0x1 set\.$")

    def test_multiline_keeps_every_line_exactly_once(self):
        msgs = ["Overlay flags 0x60 set.",
                "Overlay flags 0x1 set.",
                "Start with compressed data for keycode 0x2d (modifiers: 0x1)."]
        out = _format("\n".join(msgs))
        lines = out.splitlines()
        self.assertEqual(len(lines), 3)
        for line, msg in zip(lines, msgs):
            self.assertRegex(line, r"^\[.+\] " + msg.replace("(", r"\(")
                             .replace(")", r"\)").replace(".", r"\."))
            # exactly one timestamp prefix per line, no "[ts] [ts] msg"
            self.assertEqual(line.count("] " + msg), 1)
            self.assertNotRegex(line, r"^\[.+\] \[.+\] ")
        # the last console message must not be dropped
        self.assertIn(msgs[-1], out)

    def test_trailing_newline_does_not_drop_last_message(self):
        out = _format("first line\nlast line\n")
        self.assertIn("last line", out)
        self.assertEqual(len(out.splitlines()), 2)


class TestMakeStreamHandler(unittest.TestCase):
    """Under pythonw.exe (the Windows tray GUI and the GUI-spawned daemon)
    sys.stdout is None. make_stream_handler must not call None.isatty() — that
    AttributeError crashed run_headless (daemon never bound its socket) and
    PolyHost.__init__ (the GUI never appeared)."""

    def test_none_stdout_returns_noop_handler(self):
        import sys
        real = sys.stdout
        sys.stdout = None
        try:
            handler = make_stream_handler("%(message)s")
        finally:
            sys.stdout = real
        self.assertIsInstance(handler, logging.NullHandler)
        # Emitting must be a harmless no-op (no console to write to).
        handler.emit(logging.LogRecord("x", logging.INFO, "", 0, "hi", (), None))

    def test_real_stream_returns_stream_handler(self):
        import io
        import sys
        real = sys.stdout
        sys.stdout = io.StringIO()
        try:
            handler = make_stream_handler("%(message)s")
        finally:
            sys.stdout = real
        self.assertIsInstance(handler, logging.StreamHandler)


class TestABadFormatStringCannotBreakTheCaller(unittest.TestCase):
    """⚠️ A log line must never be able to break the code that writes it.

    `RepeatCollapseHandler.emit` calls `record.getMessage()` itself, so a
    format/arguments mismatch raised straight out of `logger.info(...)` and
    into the caller. Stock logging never does that: `StreamHandler.emit`
    formats inside its own try and routes a failure to `handleError`, which
    prints "--- Logging error ---" to stderr and carries on.

    What that cost: `ActiveWindow.log_win` formatted the window handle with
    `%d`, and on macOS pywinctl's handle is a **tuple** -- so the TypeError
    landed in the caller's `except`, was logged as "Failed retrieving active
    window", and every Mac reported no active window at all, forever. No
    overlays, no per-app language switch, from a cosmetic log line
    (field, 2026-09-21).
    """

    class _Collect(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(record.getMessage())

    def _handler(self):
        inner = self._Collect()
        return RepeatCollapseHandler(inner), inner

    def test_a_MISMATCHED_format_does_not_reach_the_caller(self):
        h, inner = self._handler()
        bad = logging.LogRecord("t", logging.INFO, "", 0,
                                "handle: %d", ((1234, 5),), None)
        with mock.patch.object(h, "handleError") as handled:
            h.emit(bad)                      # must not raise
        handled.assert_called_once_with(bad)
        self.assertEqual(inner.records, [])

    def test_the_handler_KEEPS_WORKING_after_a_bad_record(self):
        """The swallow must not wedge the collapse state -- a handler that
        stops logging after one bad line is barely better than one that
        raises."""
        h, inner = self._handler()
        with mock.patch.object(h, "handleError"):
            h.emit(logging.LogRecord("t", logging.INFO, "", 0,
                                     "handle: %d", ((1,),), None))
        h.emit(logging.LogRecord("t", logging.INFO, "", 0, "after", (), None))
        self.assertEqual(inner.records, ["after"])


if __name__ == '__main__':
    unittest.main()
