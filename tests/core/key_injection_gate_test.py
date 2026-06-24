"""The host-side key-injection gate (security).

`press`/`release` script commands inject real keystrokes on the keyboard
(firmware HID cmd 14). They are honoured only when the host runs in debug
mode; otherwise `PolyCore.execute_commands` strips them. Here we test the pure
filter that does the stripping — no device/worker needed.
"""
import unittest

from polyhost.core.poly_core import strip_key_injection


class StripKeyInjectionTest(unittest.TestCase):
    def test_drops_press_and_release(self):
        lines = ["press 0x04", "release 0x04", "PRESS 0x05"]
        kept, dropped = strip_key_injection(lines)
        # only exact `press`/`release` heads are dropped (case-sensitive keyword)
        self.assertEqual(kept, ["PRESS 0x05"])
        self.assertEqual(dropped, 2)

    def test_keeps_legitimate_commands(self):
        lines = ["wait 0.5", "overlay send foo.png", "overlay reset"]
        kept, dropped = strip_key_injection(lines)
        self.assertEqual(kept, lines)
        self.assertEqual(dropped, 0)

    def test_mixed_script_strips_only_injection(self):
        lines = ["overlay reset", "press 0x29", "wait 1", "release 0x29"]
        kept, dropped = strip_key_injection(lines)
        self.assertEqual(kept, ["overlay reset", "wait 1"])
        self.assertEqual(dropped, 2)

    def test_handles_leading_whitespace(self):
        kept, dropped = strip_key_injection(["   press 0x04", "\toverlay reset"])
        self.assertEqual(kept, ["\toverlay reset"])
        self.assertEqual(dropped, 1)


if __name__ == "__main__":
    unittest.main()
