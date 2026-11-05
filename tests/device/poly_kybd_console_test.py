"""Tests for the HID-console self-heal in PolyKybd.get_console_output.

Covers the two field bugs this logic fixed (2026-07): exception text leaking
into the console output as if the keyboard printed it (the "Success" flood),
and the console interface silently staying detached after a firmware apply.
"""
import time
import unittest
import unittest.mock as mock

from polyhost.device.poly_kybd import (
    CONSOLE_FAIL_REOPEN_THRESHOLD,
    CONSOLE_PARTIAL_LINE_HOLD_S,
    CONSOLE_REOPEN_MIN_INTERVAL_S,
)

from tests.device.poly_kybd_cmd_test import make_keeb


class ConsoleStubHid:
    """Just the console surface of HidHelper that get_console_output touches."""

    def __init__(self, acquired=True, lines=None, raise_on_read=False, reopen_result=False):
        self.acquired = acquired
        self.lines = list(lines or [])
        self.raise_on_read = raise_on_read
        self.reopen_result = reopen_result
        self.reopen_calls = 0

    def console_acquired(self):
        return self.acquired

    def reopen_console(self):
        self.reopen_calls += 1
        return self.reopen_result

    def get_console_output(self):
        if self.raise_on_read:
            raise OSError("Success")   # hidapi's famously unhelpful Windows error
        if self.lines:
            return self.lines.pop(0)
        return bytearray()


def make_console_keeb(**stub_kwargs):
    keeb, _ = make_keeb()
    stub = ConsoleStubHid(**stub_kwargs)
    keeb.hid = stub
    return keeb, stub


class TestConsoleSelfHeal(unittest.TestCase):
    def test_read_exception_is_not_published_as_output(self):
        # The exception text must never appear in the returned console output.
        keeb, _ = make_console_keeb(raise_on_read=True)
        out = keeb.get_console_output()
        self.assertEqual(out, "")

    def test_normal_reads_accumulate_and_flush(self):
        keeb, _ = make_console_keeb(lines=[bytearray(b"hello "), bytearray(b"world\n")])
        self.assertEqual(keeb.get_console_output(), "hello world\n")
        # Flushed — a second call returns the (now empty) buffer.
        self.assertEqual(keeb.get_console_output(), "")

    def test_missing_console_triggers_reopen(self):
        keeb, stub = make_console_keeb(acquired=False)
        keeb.get_console_output()
        self.assertEqual(stub.reopen_calls, 1)

    def test_reopen_is_throttled(self):
        keeb, stub = make_console_keeb(acquired=False)
        keeb.get_console_output()
        keeb.get_console_output()   # immediately again — inside the throttle window
        self.assertEqual(stub.reopen_calls, 1)
        # Age the last attempt past the interval — the next poll retries.
        keeb._console_reopen_at = time.monotonic() - CONSOLE_REOPEN_MIN_INTERVAL_S - 0.1
        keeb.get_console_output()
        self.assertEqual(stub.reopen_calls, 2)

    def test_fail_count_threshold_triggers_reopen(self):
        keeb, stub = make_console_keeb(acquired=True, raise_on_read=True)
        for i in range(CONSOLE_FAIL_REOPEN_THRESHOLD - 1):
            keeb.get_console_output()
            keeb._console_reopen_at = 0.0   # isolate the fail-count gate from the throttle
        self.assertEqual(stub.reopen_calls, 0, "reopen fired before the threshold")
        keeb.get_console_output()   # the Nth consecutive failure
        self.assertEqual(stub.reopen_calls, 1)

    def test_successful_read_resets_fail_count(self):
        keeb, stub = make_console_keeb(acquired=True, raise_on_read=True)
        for _ in range(CONSOLE_FAIL_REOPEN_THRESHOLD - 1):
            keeb.get_console_output()
        stub.raise_on_read = False
        keeb.get_console_output()               # success — resets the counter
        self.assertEqual(keeb._console_fail_count, 0)
        stub.raise_on_read = True
        keeb.get_console_output()               # one new failure must not reopen
        self.assertEqual(stub.reopen_calls, 0)


class TestConsolePartialLines(unittest.TestCase):
    """A console line split across two polls reaches the log as one line.

    Field console log, 2026-11-05: "Set brightness to: 4 (flags 0x1," and
    " auto 1)." were written as two log lines 253 ms apart."""

    def test_a_line_split_across_two_polls_comes_out_whole(self):
        keeb, stub = make_console_keeb(lines=[bytearray(b"Set brightness to: 4 (flags 0x1,")])
        self.assertEqual(keeb.get_console_output(), "")
        stub.lines.append(bytearray(b" auto 1).\n"))
        self.assertEqual(keeb.get_console_output(), "Set brightness to: 4 (flags 0x1, auto 1).\n")

    def test_complete_lines_go_out_and_the_unfinished_one_waits(self):
        keeb, stub = make_console_keeb(lines=[bytearray(b"Stop idle.\nSplit link: 2400 tx e")])
        self.assertEqual(keeb.get_console_output(), "Stop idle.\n")
        stub.lines.append(bytearray(b"rr=0.0%\n"))
        self.assertEqual(keeb.get_console_output(), "Split link: 2400 tx err=0.0%\n")

    def test_an_unfinished_line_is_released_after_the_hold(self):
        keeb, _ = make_console_keeb(lines=[bytearray(b"no newline")])
        self.assertEqual(keeb.get_console_output(), "")
        self.assertEqual(keeb.get_console_output(), "", "released before the hold ran out")
        keeb._console_partial_since = time.monotonic() - CONSOLE_PARTIAL_LINE_HOLD_S - 0.1
        self.assertEqual(keeb.get_console_output(), "no newline")
        self.assertEqual(keeb.get_console_output(), "")

    def test_the_hold_restarts_for_the_line_after_a_newline(self):
        # The text after a newline is a new line and gets its own full wait,
        # even when the line before it had nearly used up its own.
        keeb, stub = make_console_keeb(lines=[bytearray(b"first")])
        keeb.get_console_output()
        keeb._console_partial_since = time.monotonic() - CONSOLE_PARTIAL_LINE_HOLD_S + 0.2
        stub.lines.append(bytearray(b" line\nsecond"))
        self.assertEqual(keeb.get_console_output(), "first line\n")
        self.assertGreater(keeb._console_partial_since,
                           time.monotonic() - CONSOLE_PARTIAL_LINE_HOLD_S + 0.2)
        self.assertEqual(keeb.get_console_output(), "")

    def test_a_failed_read_keeps_the_unfinished_line(self):
        keeb, stub = make_console_keeb(lines=[bytearray(b"half")])
        keeb.get_console_output()
        stub.raise_on_read = True
        self.assertEqual(keeb.get_console_output(), "")
        stub.raise_on_read = False
        stub.lines.append(bytearray(b" line\n"))
        self.assertEqual(keeb.get_console_output(), "half line\n")


    def test_a_read_that_does_not_flush_starts_the_hold(self):
        keeb, _ = make_console_keeb(lines=[bytearray(b"buffered")])
        self.assertIsNone(keeb.get_console_output(flush_and_return=False))
        self.assertIsNotNone(keeb._console_partial_since)
        keeb._console_partial_since = time.monotonic() - CONSOLE_PARTIAL_LINE_HOLD_S - 0.1
        self.assertEqual(keeb.get_console_output(), "buffered")

    def test_a_reattached_console_does_not_join_the_old_fragment(self):
        keeb, stub = make_console_keeb(lines=[bytearray(b"half a li")])
        self.assertEqual(keeb.get_console_output(), "")
        stub.acquired = False
        stub.reopen_result = True
        stub.lines.append(bytearray(b"== banner ==\n"))
        self.assertEqual(keeb.get_console_output(), "half a li\n== banner ==\n")
        self.assertEqual(stub.reopen_calls, 1)

    def test_a_reconnect_does_not_join_the_old_fragment(self):
        keeb, _ = make_console_keeb(lines=[bytearray(b"half a li")])
        self.assertEqual(keeb.get_console_output(), "")
        fresh = ConsoleStubHid(lines=[bytearray(b"== banner ==\n")])
        with mock.patch("polyhost.device.poly_kybd.HidHelper", return_value=fresh):
            self.assertTrue(keeb._open_interfaces())
        self.assertEqual(keeb.get_console_output(), "half a li\n== banner ==\n")


if __name__ == '__main__':
    unittest.main()
