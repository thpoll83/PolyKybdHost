"""macro_script — VIA's macro syntax, parsed to and printed from our steps.

The round trip is the contract, so most of this is round-trip: the editor's Table/Script
toggle switches through this module on every flip, and a script view that cannot print
back what it parsed is a field that lies.
"""
import unittest

from polyhost.services import macro_body as mb
from polyhost.services import macro_keys as mk
from polyhost.services import macro_script as msc


class ParseTest(unittest.TestCase):
    def test_literal_text(self):
        self.assertEqual(msc.parse("hi"), [mb.Step("char", code=ord("h")),
                                           mb.Step("char", code=ord("i"))])

    def test_a_tap(self):
        self.assertEqual(msc.parse("{KC_A}"), [mb.Step("tap", code=mk.value_for("KC_A"))])

    def test_hold_and_release(self):
        self.assertEqual(msc.parse("{+KC_LSFT}{-KC_LSFT}"),
                         [mb.Step("down", code=mk.value_for("KC_LEFT_SHIFT")),
                          mb.Step("up", code=mk.value_for("KC_LEFT_SHIFT"))])

    def test_a_delay(self):
        self.assertEqual(msc.parse("{250}"), [mb.Step("delay", ms=250)])

    def test_the_short_aliases_VIA_users_actually_type(self):
        """`{KC_LSFT}`, not `{KC_LEFT_SHIFT}` -- that is what VIA prints and what anyone
        pasting a macro from elsewhere will have."""
        self.assertEqual(msc.parse("{+KC_LCTL}{KC_ENT}{-KC_LCTL}"),
                         [mb.Step("down", code=mk.value_for("KC_LEFT_CTRL")),
                          mb.Step("tap", code=mk.value_for("KC_ENTER")),
                          mb.Step("up", code=mk.value_for("KC_LEFT_CTRL"))])

    def test_a_realistic_mixed_script(self):
        self.assertEqual(
            mk.describe(msc.parse("{+KC_LCTL}{KC_A}{-KC_LCTL}{50}done")),
            'Ctrl+A  ·  50 ms  ·  "done"')

    def test_an_escaped_brace_is_a_character(self):
        self.assertEqual(msc.parse(r"a\{b"), [mb.Step("char", code=ord(c)) for c in "a{b"])

    def test_a_closing_brace_needs_no_escape(self):
        """A token is found from its OPENING brace, so `}` can only ever be literal --
        requiring an escape for it would be ceremony with nothing behind it."""
        self.assertEqual(msc.parse("}"), [mb.Step("char", code=ord("}"))])

    def test_whitespace_inside_a_token_is_tolerated(self):
        self.assertEqual(msc.parse("{ KC_A }"), msc.parse("{KC_A}"))
        self.assertEqual(msc.parse("{+ KC_LSFT}"), msc.parse("{+KC_LSFT}"))

    def test_an_empty_script_is_an_empty_macro(self):
        self.assertEqual(msc.parse(""), [])


class RefusalTest(unittest.TestCase):
    def _refuses(self, text, *expected):
        with self.assertRaises(msc.ScriptError) as ctx:
            msc.parse(text)
        for word in expected:
            self.assertIn(word, str(ctx.exception))

    def test_an_unknown_keycode(self):
        self._refuses("{KC_NOPE}", "KC_NOPE", "not a keycode")

    def test_an_empty_token(self):
        self._refuses("{}", "empty")

    def test_a_prefix_with_no_key(self):
        self._refuses("{+}", "names no key")

    def test_a_delay_longer_than_the_format_holds(self):
        self._refuses("{99999}", "65535")

    def test_the_chord_shorthand_is_refused_WITH_the_way_out(self):
        """VIA's `{KC_LSFT,KC_A}` is the one form whose expansion is not obvious from
        reading it. Refusing it silently would read as a parser bug, so the message
        spells the long form out.
        """
        self._refuses("{KC_LSFT,KC_A}", "shorthand", "{+KC_LSFT}{KC_A}{-KC_LSFT}")

    def test_a_placeholder_is_not_a_key(self):
        self._refuses("{0x01}", "placeholder")

    def test_text_the_keyboard_cannot_type(self):
        """The same refusal the plain text field makes, made here where it can be seen.
        A macro that silently types less than you wrote is worse than one that refuses.
        """
        with self.assertRaises(mb.MacroError):
            msc.parse("café")


class RoundTripTest(unittest.TestCase):
    """`parse(format(steps)) == steps` for every step list -- the direction the editor's
    Table/Script toggle needs."""

    CASES = {
        "chord": [mb.Step("down", code=0xE0), mb.Step("down", code=0xE1),
                  mb.Step("tap", code=0x13),
                  mb.Step("up", code=0xE1), mb.Step("up", code=0xE0)],
        "text": [mb.Step("char", code=ord(c)) for c in "hello world"],
        "a literal brace": [mb.Step("char", code=ord(c)) for c in "{a}"],
        "a literal backslash": [mb.Step("char", code=ord(c)) for c in "a\\b"],
        "both escapes together": [mb.Step("char", code=ord(c)) for c in "\\{"],
        "zero delay": [mb.Step("delay", ms=0)],
        "longest delay": [mb.Step("delay", ms=0xFFFF)],
        "an unnamed keycode": [mb.Step("tap", code=0xFD)],
        "empty": [],
    }

    def test_every_shape_survives(self):
        for name, steps in self.CASES.items():
            with self.subTest(shape=name):
                self.assertEqual(msc.parse(msc.format(steps)), steps)

    def test_every_printable_character_survives(self):
        """The escapes are the interesting characters, and they are two out of 95 -- a
        handful of hand-picked cases would very likely miss whichever one broke."""
        steps = [mb.Step("char", code=c) for c in range(0x20, 0x7F)]
        self.assertEqual(msc.parse(msc.format(steps)), steps)

    def test_tab_and_newline_survive(self):
        steps = [mb.Step("char", code=0x09), mb.Step("char", code=0x0A)]
        self.assertEqual(msc.parse(msc.format(steps)), steps)

    def test_it_also_survives_the_body_encoding(self):
        """The script is one view; the bytes on the keyboard are the other. A form that
        round-trips through itself but not through the wire would still lose the macro.
        """
        steps = self.CASES["chord"] + [mb.Step("delay", ms=120)] + self.CASES["text"]
        self.assertEqual(mb.decode(mb.encode_steps(msc.parse(msc.format(steps)))), steps)


class FormatTest(unittest.TestCase):
    def test_a_value_prints_as_its_canonical_name(self):
        """`{KC_LSFT}` parses, but printing back the alias would make the script view's
        output depend on what the user happened to type."""
        self.assertEqual(msc.format(msc.parse("{+KC_LCTL}")), "{+KC_LEFT_CTRL}")

    def test_a_closing_brace_is_PRINTED_bare(self):
        """The round trip cannot catch this: escaping `}` on the way out and unescaping
        it on the way back in is self-consistent. What it breaks is the point of using
        VIA's syntax at all -- VIA prints `}` bare, so a script of ours carrying `\\}`
        is no longer text you can paste into it.

        Interchange is only testable as an assertion about the OUTPUT, never as a
        property of our own parser.
        """
        self.assertEqual(msc.format([mb.Step("char", code=ord("}"))]), "}")
        self.assertEqual(msc.format([mb.Step("char", code=ord(c)) for c in "{a}"]),
                         r"\{a}")

    def test_an_unknown_step_kind_is_refused_rather_than_dropped(self):
        with self.assertRaises(msc.ScriptError):
            msc.format([mb.Step("nonsense", code=1)])


if __name__ == "__main__":
    unittest.main()
