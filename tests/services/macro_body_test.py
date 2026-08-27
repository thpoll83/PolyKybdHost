"""Tests for the macro body encoding.

This is the host half of a contract whose other half is the firmware's
base/macro_decode.c. Both ends are pinned, deliberately: a host fixture can only ever
catch the host misreading a body, never the firmware emitting or playing the wrong one.
"""

import unittest

from polyhost.services import macro_body as mb


class EncodeTextTest(unittest.TestCase):
    def test_printable_ascii_is_one_byte_per_character(self):
        self.assertEqual(mb.encode_text("hi"), b"hi")

    def test_tab_and_newline_are_allowed(self):
        # send_string translates both, so they are typeable even though they are
        # outside the printable range everything else is checked against.
        self.assertEqual(mb.encode_text("a\tb\n"), b"a\tb\n")

    def test_non_ascii_is_refused_rather_than_dropped(self):
        # A macro that silently types less than you asked for is worse than one that
        # refuses -- you would only find out when it mattered.
        with self.assertRaises(mb.MacroError):
            mb.encode_text("café")

    def test_the_error_names_the_offending_character(self):
        with self.assertRaises(mb.MacroError) as cm:
            mb.encode_text("naïve")
        self.assertIn("ï", str(cm.exception))


class EncodeStepsTest(unittest.TestCase):
    def test_tap_down_up(self):
        got = mb.encode_steps([
            mb.Step("down", code=0xE0), mb.Step("tap", code=0x06), mb.Step("up", code=0xE0),
        ])
        self.assertEqual(got, bytes((1, 2, 0xE0, 1, 1, 0x06, 1, 3, 0xE0)))

    def test_delay_is_ascii_digits(self):
        self.assertEqual(mb.encode_steps([mb.Step("delay", ms=250)]), b"\x01\x04250")

    def test_delay_out_of_range_is_refused(self):
        with self.assertRaises(mb.MacroError):
            mb.encode_steps([mb.Step("delay", ms=70000)])

    def test_keycode_wider_than_a_byte_is_refused(self):
        # The wire format carries 8-bit keycodes, so a mod-tap cannot be encoded. Say so
        # rather than truncating it into a different, valid-looking key.
        with self.assertRaises(mb.MacroError):
            mb.encode_steps([mb.Step("tap", code=0x3204)])


class RoundTripTest(unittest.TestCase):
    def test_text_round_trips(self):
        body = mb.encode_text("tom@example.com")
        self.assertEqual(mb.to_text(mb.decode(body)), "tom@example.com")

    def test_steps_round_trip(self):
        steps = [mb.Step("down", code=0xE0), mb.Step("tap", code=0x06),
                 mb.Step("up", code=0xE0), mb.Step("delay", ms=50),
                 mb.Step("char", code=ord("o")), mb.Step("char", code=ord("k"))]
        self.assertEqual(mb.decode(mb.encode_steps(steps)), steps)

    def test_the_byte_after_a_delay_is_not_eaten(self):
        # send_string re-reads the terminator as the next step; consuming it would
        # silently swallow a character after every delay.
        steps = mb.decode(mb.encode_steps([mb.Step("delay", ms=10)]) + b"x")
        self.assertEqual(steps, [mb.Step("delay", ms=10), mb.Step("char", code=ord("x"))])

    def test_a_macro_with_a_chord_is_not_expressible_as_text(self):
        # This is what decides whether the editor may show a macro in its Text tab.
        # Pretending it were text would lose the chord the moment the user saved.
        self.assertIsNone(mb.to_text([mb.Step("tap", code=0x04)]))


class BufferTest(unittest.TestCase):
    def test_split_finds_each_macro(self):
        buf = b"first\0second\0" + b"\0" * 20
        self.assertEqual(mb.split_buffer(buf, 3)[:2], [b"first", b"second"])

    def test_unwritten_macros_read_as_empty(self):
        buf = b"only\0" + b"\0" * 20
        self.assertEqual(mb.split_buffer(buf, 4), [b"only", b"", b"", b""])

    def test_join_terminates_and_zero_fills(self):
        # The zero fill is not cosmetic: the firmware refuses to play a buffer whose
        # LAST byte is not NUL, which is what stops a half-streamed macro from typing
        # an arbitrary prefix of a password.
        out = mb.join_buffer([b"ab", b"cd"], 16)
        self.assertEqual(len(out), 16)
        self.assertEqual(out[-1], 0)
        self.assertEqual(out[:6], b"ab\0cd\0")

    def test_trailing_empty_macros_cost_nothing(self):
        a = mb.join_buffer([b"abc"], 16)
        b = mb.join_buffer([b"abc", b"", b"", b""], 16)
        self.assertEqual(a, b)

    def test_a_leading_empty_macro_still_costs_its_terminator(self):
        out = mb.join_buffer([b"", b"x"], 16)
        self.assertEqual(out[:3], b"\0x\0")

    def test_overflow_is_refused_with_both_numbers(self):
        # The bodies share one buffer, so the caller has to be told which way the trade
        # went -- "too big" alone does not say by how much.
        with self.assertRaises(mb.MacroError) as cm:
            mb.join_buffer([b"x" * 40], 16)
        self.assertIn("41", str(cm.exception))
        self.assertIn("16", str(cm.exception))

    def test_round_trip_through_a_whole_buffer(self):
        bodies = [mb.encode_text("one"), mb.encode_text("two"), b""]
        packed = mb.join_buffer(bodies, 64)
        self.assertEqual(mb.split_buffer(packed, 3), bodies)


if __name__ == "__main__":
    unittest.main()
