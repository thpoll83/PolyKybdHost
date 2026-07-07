"""Tests for the HID-console self-heal in PolyKybd.get_console_output.

Covers the two field bugs this logic fixed (2026-07): exception text leaking
into the console output as if the keyboard printed it (the "Success" flood),
and the console interface silently staying detached after a firmware apply.
"""
import time
import unittest

from polyhost.device.poly_kybd import (
    CONSOLE_FAIL_REOPEN_THRESHOLD,
    CONSOLE_REOPEN_MIN_INTERVAL_S,
)

from tests.device.poly_kybd_cmd_test import make_keeb


class ConsoleStubHid:
    """Just the console surface of HidHelper that get_console_output touches."""

    def __init__(self, acquired=True, lines=None, raise_on_read=False):
        self.acquired = acquired
        self.lines = list(lines or [])
        self.raise_on_read = raise_on_read
        self.reopen_calls = 0

    def console_acquired(self):
        return self.acquired

    def reopen_console(self):
        self.reopen_calls += 1
        return False

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
        keeb, _ = make_console_keeb(lines=[bytearray(b"hello "), bytearray(b"world")])
        self.assertEqual(keeb.get_console_output(), "hello world")
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


if __name__ == '__main__':
    unittest.main()
