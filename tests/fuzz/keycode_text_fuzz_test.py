"""Properties of polyhost/services/keycode_text.py (keycodes typed by the user or
read from keymap files)."""
import unittest

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.services.keycode_text import keycode_text, parse_keycode

load_profile()


class KeycodeTextFuzzTest(unittest.TestCase):
    @given(st.integers(1, 0xFFFF))
    def test_text_parse_round_trip(self, value):
        self.assertEqual(parse_keycode(keycode_text(value)), value)

    @given(st.text(max_size=40))
    def test_parse_arbitrary_text(self, text):
        try:
            value = parse_keycode(text)
        except ValueError:
            return
        self.assertTrue(0 <= value <= 0xFFFF)

    @given(st.from_regex(r"[A-Za-z_]{1,6}\((\w{1,8}|\d{1,4}|[A-Z]+\(\w+\))\)", fullmatch=True))
    def test_parse_function_forms(self, text):
        try:
            value = parse_keycode(text)
        except ValueError:
            return
        self.assertTrue(0 <= value <= 0xFFFF)


if __name__ == "__main__":
    unittest.main()
