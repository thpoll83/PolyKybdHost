"""Properties of polyhost/services/macro_body.py (macro bodies read from the keyboard)."""
import unittest

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.services import macro_body as mb

load_profile()

PRINTABLE = st.sampled_from([chr(c) for c in range(0x20, 0x7F)] + ["\n", "\t"])
STEPS = st.one_of(
    PRINTABLE.map(lambda ch: mb.Step("char", code=ord(ch))),
    st.builds(mb.Step, st.sampled_from(["tap", "down", "up"]), st.integers(0, 0xFF)),
    st.integers(0, 0xFFFF).map(lambda ms: mb.Step("delay", ms=ms)),
)

# The keycode that types each digit (KC_1..KC_9, KC_0).
DIGIT_TAP = {str(d): 0x1E + (d - 1) % 10 for d in range(10)}


def _typed(steps):
    """The steps with each digit character written as the tap that types it."""
    return [mb.Step("tap", code=DIGIT_TAP[chr(s.code)])
            if s.kind == "char" and chr(s.code) in DIGIT_TAP else s for s in steps]


class MacroBodyFuzzTest(unittest.TestCase):
    @given(st.text(PRINTABLE, max_size=60))
    def test_text_round_trip(self, text):
        self.assertEqual(mb.to_text(mb.decode(mb.encode_text(text))), text)

    @given(st.lists(STEPS, max_size=20))
    def test_steps_round_trip(self, steps):
        # A digit after a delay is sent as its tap (see encode_steps), so compare
        # what is typed, not the spelling.
        self.assertEqual(_typed(mb.decode(mb.encode_steps(steps))), _typed(steps))

    @given(st.binary(max_size=64))
    def test_decode_arbitrary_bytes(self, body):
        for s in mb.decode(body):
            self.assertIn(s.kind, ("char", "tap", "down", "up", "delay"))
            self.assertLessEqual(s.ms, 0xFFFF)
            self.assertLessEqual(s.code, 0xFF)

    @given(st.lists(st.binary(max_size=20).map(lambda b: b.replace(b"\0", b"")), max_size=8),
           st.integers(0, 64))
    def test_join_split_round_trip(self, bodies, spare):
        capacity = sum(len(b) + 1 for b in bodies) + spare
        buf = mb.join_buffer(bodies, capacity)
        self.assertEqual(len(buf), capacity)
        self.assertEqual(mb.split_buffer(buf, len(bodies)), bodies)

    @given(st.binary(max_size=64), st.integers(0, 16))
    def test_split_arbitrary_buffer(self, buf, count):
        self.assertEqual(len(mb.split_buffer(buf, count)), count)


if __name__ == "__main__":
    unittest.main()
