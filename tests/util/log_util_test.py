"""Regression tests for MultiLineFormatter (keyboard-console log file).

The old implementation re-emitted the first line (glued to itself without a
newline) and silently dropped the LAST line of every multi-line record —
i.e. the tail console message of each 250 ms flush never reached
polykybd_console.txt (seen in the field 2026-06-13).
"""
import logging
import unittest

from polyhost.util.log_util import MultiLineFormatter


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


if __name__ == '__main__':
    unittest.main()
