"""MacCompose: the F20 sequence the keyboard sends, and what the host types for it.

The firmware (protocol v38, cmd 20 value 6) holds F20 instead of Option while it
types the hex code of a character. A code point above U+FFFF arrives as a UTF-16
surrogate pair, 8 digits, as in QMK's macOS mode. These tests pin the decoding,
which keys are dropped, and the tap callback with a fake Quartz API. The real
Quartz calls only run on a Mac.
"""
import sys
import unittest
import unittest.mock as mock

from polyhost.input import mac_compose as mc
from polyhost.input.mac_compose import KEY_F20, ComposeDecoder, MacComposeTap, code_point_text

# Virtual key codes by hex digit, the inverse of mac_compose.HEX_KEYS.
KEY_OF = {format(v, "x"): k for k, v in mc.HEX_KEYS.items()}
KEY_Q = 0x0C   # kVK_ANSI_Q: not a hex digit


def sequence(digits):
    """The key events the firmware sends for ``digits``: F20 down, each digit
    tapped, F20 up."""
    events = [(KEY_F20, True, False)]
    for d in digits:
        events += [(KEY_OF[d], True, False), (KEY_OF[d], False, False)]
    return events + [(KEY_F20, False, False)]


def run(decoder, events):
    results = [decoder.feed(*e) for e in events]
    return [r[0] for r in results], [r[1] for r in results if r[1]]


class CodePointTextTest(unittest.TestCase):
    def test_a_bmp_code_point(self):
        self.assertEqual(code_point_text("e4"), "ä")
        self.assertEqual(code_point_text("20ac"), "€")

    def test_a_surrogate_pair_is_combined(self):
        self.assertEqual(code_point_text("d83dde00"), "\U0001F600")   # 😀

    def test_a_full_code_point_above_the_bmp(self):
        self.assertEqual(code_point_text("1f600"), "\U0001F600")

    def test_invalid_digits_give_no_text(self):
        for digits in ("", "d83d", "dc00", "d83d0041", "110000", "123456789"):
            self.assertIsNone(code_point_text(digits), digits)


class ComposeDecoderTest(unittest.TestCase):
    def test_a_sequence_is_dropped_and_typed(self):
        swallowed, texts = run(ComposeDecoder(), sequence("d83dde00"))
        self.assertTrue(all(swallowed))
        self.assertEqual(texts, ["\U0001F600"])

    def test_keys_outside_a_sequence_pass(self):
        d = ComposeDecoder()
        self.assertEqual(d.feed(KEY_OF["a"], True), (False, None))
        self.assertEqual(d.feed(KEY_Q, True), (False, None))

    def test_an_autorepeated_f20_does_not_restart_the_sequence(self):
        d = ComposeDecoder()
        events = sequence("e4")
        events.insert(3, (KEY_F20, True, True))   # repeat after the first digit
        _, texts = run(d, events)
        self.assertEqual(texts, ["ä"])

    def test_another_key_ends_the_sequence_and_passes(self):
        d = ComposeDecoder()
        d.feed(KEY_F20, True)
        d.feed(KEY_OF["e"], True)
        self.assertEqual(d.feed(KEY_Q, True), (False, None))
        self.assertFalse(d.composing)
        self.assertEqual(d.feed(KEY_F20, False), (True, None))

    def test_more_than_8_digits_ends_the_sequence(self):
        _, texts = run(ComposeDecoder(), sequence("d83dde001"))
        self.assertEqual(texts, [])

    def test_a_lone_f20_tap_types_nothing(self):
        swallowed, texts = run(ComposeDecoder(), sequence(""))
        self.assertEqual(swallowed, [True, True])
        self.assertEqual(texts, [])


class FakeApi:
    def __init__(self, tap="tap"):
        self.tap = tap
        self.posted = []
        self.re_enabled = 0

    def create_tap(self, callback):
        self.callback = callback
        return self.tap

    def run(self, tap):
        return "loop"

    def run_loop(self):
        pass

    def stop(self, loop):
        pass

    def re_enable(self, tap):
        self.re_enabled += 1

    def is_disable_event(self, type_):
        return type_ == "disabled"

    def key_event(self, event):
        return event

    def post_text(self, proxy, text):
        self.posted.append(text)


class TapCallbackTest(unittest.TestCase):
    def test_the_callback_drops_the_sequence_and_posts_the_character(self):
        api = FakeApi()
        tap = MacComposeTap(api=api)
        out = [tap._on_event("proxy", "key", e) for e in sequence("e4")]
        self.assertEqual(out, [None] * len(out))
        self.assertEqual(api.posted, ["ä"])
        self.assertEqual(tap.typed, 1)

    def test_other_keys_are_passed_on_unchanged(self):
        tap = MacComposeTap(api=FakeApi())
        event = (KEY_Q, True, False)
        self.assertIs(tap._on_event("proxy", "key", event), event)

    def test_a_disabled_tap_is_re_enabled(self):
        api = FakeApi()
        tap = MacComposeTap(api=api)
        tap._on_event("proxy", "disabled", None)
        self.assertEqual(api.re_enabled, 1)

    def test_a_refused_tap_does_not_run(self):
        tap = MacComposeTap(api=FakeApi(tap=None))
        self.assertFalse(tap.start(timeout=2.0))

    def test_no_pyobjc_does_not_run(self):
        with mock.patch.dict(sys.modules, {"Quartz": None}):
            self.assertFalse(MacComposeTap().start(timeout=0.1))


if __name__ == "__main__":
    unittest.main()
