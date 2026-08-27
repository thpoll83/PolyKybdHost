"""macro_keys — the keycode table, the Qt-key translation and the summary line.

Qt-free, so the translation table is exercised in the ordinary suite rather than only
through a widget under xvfb. That is the whole reason the recorder's mapping lives in a
service: it is the part with a real chance of being wrong.
"""
import unittest

from polyhost.services import macro_body as mb
from polyhost.services import macro_keys as mk

# Qt::Key values, spelled out here as well so a change to the module's copy has to be
# made deliberately in two places rather than agreeing with itself.
K_A = 0x41
K_MINUS = 0x2D
K_UNDERSCORE = 0x5F
K_CONTROL = 0x01000021
K_SHIFT = 0x01000020
K_META = 0x01000022
K_F5 = 0x01000034
K_RETURN = 0x01000004
K_ENTER = 0x01000005
K_SPACE = 0x20
K_ESCAPE = 0x01000000


class KeycodeTableTest(unittest.TestCase):
    def test_only_one_byte_keycodes_are_offered(self):
        """The wire format stores the keycode in ONE byte, so anything above 0xFF is not
        a step a macro can hold -- offering it would build a macro the firmware plays as
        some other key."""
        table = mk.keycodes()
        self.assertTrue(table, "no keycodes parsed -- res/keycodes.h missing?")
        self.assertTrue(all(0 < v <= 0xFF for v in table.values()))

    def test_names_match_the_rest_of_the_app(self):
        """Same header the keycode browser parses, so a macro step and a keymap entry
        call the same key by the same name."""
        self.assertEqual(mk.value_for("KC_A"), 0x04)
        self.assertEqual(mk.value_for("KC_LEFT_CTRL"), 0xE0)
        self.assertEqual(mk.name_for(0x28), "KC_ENTER")

    def test_the_short_aliases_resolve(self):
        """QMK's short spellings are what a person types, and what a VIA-style script
        carries -- `{KC_LSFT}`, not `{KC_LEFT_SHIFT}`.

        They live in the enum as name-to-name assignments (`KC_ENT = KC_ENTER,`, 128 of
        them), which a hex-only parse silently skips. This test exists because that
        skip was invisible: the table simply did not contain the names, and every
        lookup of one failed as though the key did not exist.
        """
        for short, long in (("KC_LSFT", "KC_LEFT_SHIFT"), ("KC_LCTL", "KC_LEFT_CTRL"),
                            ("KC_ENT", "KC_ENTER"), ("KC_ESC", "KC_ESCAPE"),
                            ("KC_BSPC", "KC_BACKSPACE"), ("KC_SPC", "KC_SPACE"),
                            ("KC_MINS", "KC_MINUS")):
            with self.subTest(alias=short):
                self.assertEqual(mk.value_for(short), mk.value_for(long))

    def test_a_value_renders_as_its_CANONICAL_name(self):
        """Now that a value has several names, which one comes back matters: the long
        form is what the enum defines and what every other surface in the app shows, so
        an alias winning would rename keys in the editor for no reason.

        This is the tie-break `_load` was written for before any alias existed. It is
        live now -- the test that pinned "no value has two names" failed the moment the
        aliases were parsed, which is exactly what it was there to do.
        """
        self.assertEqual(mk.name_for(0xE1), "KC_LEFT_SHIFT")
        self.assertEqual(mk.name_for(0x28), "KC_ENTER")
        self.assertEqual(mk.name_for(0x2A), "KC_BACKSPACE")

    def test_the_placeholders_are_excluded_in_EVERY_spelling(self):
        """QMK spells each of them three ways and the alias pass brings all three, so a
        name blocklist leaks whichever spelling it forgot -- `_______` and `KC_TRNS` both
        got in when this was filtered by name. Excluded by value instead.
        """
        table = mk.keycodes()
        for name in ("KC_NO", "XXXXXXX", "KC_TRANSPARENT", "KC_TRNS", "_______"):
            self.assertNotIn(name, table)
        self.assertNotIn(0x00, set(table.values()))
        self.assertNotIn(0x01, set(table.values()))

    def test_an_unnamed_keycode_is_shown_not_refused(self):
        """The firmware plays whatever byte it is handed, so the editor has to be able
        to display a value the header has no name for."""
        self.assertEqual(mk.name_for(0xFD), "0xFD")

    def test_value_for_accepts_a_raw_number(self):
        self.assertEqual(mk.value_for("0x2c"), 0x2C)
        self.assertEqual(mk.value_for("44"), 44)

    def test_value_for_rejects_what_it_cannot_use(self):
        self.assertIsNone(mk.value_for("KC_NOT_A_KEY"))
        self.assertIsNone(mk.value_for("0x1FF"))     # would not fit the byte
        self.assertIsNone(mk.value_for(""))


class QtKeyTranslationTest(unittest.TestCase):
    def test_letters(self):
        """Qt::Key_A is the character 'A', not 'a' -- getting that backwards maps every
        letter to nothing."""
        self.assertEqual(mk.qt_key_to_keycode(K_A, "a"), mk.value_for("KC_A"))

    def test_both_characters_of_one_key_land_on_that_key(self):
        """A US key produces two characters and Qt reports whichever the shift state
        made. Mapping only the unshifted one means recording `_` silently stores nothing
        while `-` works, which reads as the recorder dropping keys at random.
        """
        self.assertEqual(mk.qt_key_to_keycode(K_MINUS, "-"), mk.value_for("KC_MINUS"))
        self.assertEqual(mk.qt_key_to_keycode(K_UNDERSCORE, "_"), mk.value_for("KC_MINUS"))

    def test_shifted_digits_are_the_digit_key(self):
        self.assertEqual(mk.qt_key_to_keycode(ord("!"), "!"), mk.value_for("KC_1"))
        self.assertEqual(mk.qt_key_to_keycode(ord("9"), "9"), mk.value_for("KC_9"))

    def test_modifiers_are_their_own_events(self):
        """The recorder reads each event's own key rather than the modifier MASK, which
        is what gives it a true down/up ordering."""
        self.assertEqual(mk.qt_key_to_keycode(K_CONTROL), mk.value_for("KC_LEFT_CTRL"))
        self.assertEqual(mk.qt_key_to_keycode(K_SHIFT), mk.value_for("KC_LEFT_SHIFT"))
        self.assertEqual(mk.qt_key_to_keycode(K_META), mk.value_for("KC_LEFT_GUI"))

    def test_the_two_enters_stay_apart(self):
        """Qt distinguishes the main Return from the keypad Enter and so does QMK; a
        macro aimed at a numpad field wants the one it pressed."""
        self.assertEqual(mk.qt_key_to_keycode(K_RETURN), mk.value_for("KC_ENTER"))
        self.assertEqual(mk.qt_key_to_keycode(K_ENTER), mk.value_for("KC_KP_ENTER"))

    def test_function_keys_and_space(self):
        self.assertEqual(mk.qt_key_to_keycode(K_F5), mk.value_for("KC_F5"))
        self.assertEqual(mk.qt_key_to_keycode(K_SPACE, " "), mk.value_for("KC_SPACE"))

    def test_an_unmapped_key_returns_none_rather_than_a_wrong_guess(self):
        """A key with no basic keycode must record as nothing, not as whatever the
        fallback happened to reach -- a macro that types the wrong key is worse than one
        missing a step the user can see is missing."""
        self.assertIsNone(mk.qt_key_to_keycode(0x01000030 - 1))   # below F1, unassigned

    def test_the_text_fallback_only_helps_when_the_key_is_unknown(self):
        """A layout can produce a character Qt has no Key_* constant for; the event's
        own text() is the only thing left to go on."""
        self.assertEqual(mk.qt_key_to_keycode(0x01FFFFFF, "q"), mk.value_for("KC_Q"))


class DescribeTest(unittest.TestCase):
    def test_a_chord_reads_as_a_chord(self):
        """down/down/tap/up/up is exactly the list the summary exists to save the reader
        from."""
        steps = [mb.Step("down", code=0xE0), mb.Step("down", code=0xE1),
                 mb.Step("tap", code=0x13),
                 mb.Step("up", code=0xE1), mb.Step("up", code=0xE0)]
        self.assertEqual(mk.describe(steps), "Ctrl+Shift+P")

    def test_a_RECORDED_chord_reads_as_a_chord_too(self):
        """A recorder emits down/down/up/up and never a tap, so the release is what
        has to complete the chord.

        Found by driving the recorder rather than by reading the code: a captured
        Ctrl+A summarised as the empty string, i.e. the one macro someone had just
        pressed the keys for rendered as nothing at all.
        """
        steps = [mb.Step("down", code=0xE0), mb.Step("down", code=0x04),
                 mb.Step("up", code=0x04), mb.Step("up", code=0xE0)]
        self.assertEqual(mk.describe(steps), "Ctrl+A")

    def test_a_recorded_key_with_no_modifier_is_just_the_key(self):
        self.assertEqual(
            mk.describe([mb.Step("down", code=0x04), mb.Step("up", code=0x04)]), "A")

    def test_a_chord_is_reported_once_not_twice(self):
        """The tap already named it, so the releases that follow must stay quiet --
        otherwise every hand-built chord reads as `Ctrl+P  ·  Ctrl`.
        """
        steps = [mb.Step("down", code=0xE0), mb.Step("tap", code=0x13),
                 mb.Step("up", code=0xE0)]
        self.assertEqual(mk.describe(steps), "Ctrl+P")

    def test_several_modifiers_left_held_are_named_together(self):
        self.assertEqual(
            mk.describe([mb.Step("down", code=0xE0), mb.Step("down", code=0xE1)]),
            "hold Ctrl+Shift")

    def test_characters_collapse_into_a_string(self):
        steps = [mb.Step("char", code=ord(c)) for c in "hi"]
        self.assertEqual(mk.describe(steps), '"hi"')

    def test_a_delay_is_named_in_ms(self):
        self.assertEqual(mk.describe([mb.Step("delay", ms=120)]), "120 ms")

    def test_a_modifier_left_held_is_reported_not_dropped(self):
        """A macro that arms a modifier and stops is a real thing to write, so the
        summary has to say so rather than rendering as empty."""
        self.assertEqual(mk.describe([mb.Step("down", code=0xE3)]), "hold Gui")

    def test_an_empty_list_is_empty(self):
        self.assertEqual(mk.describe([]), "")

    def test_the_pieces_are_joined_in_order(self):
        steps = [mb.Step("down", code=0xE0), mb.Step("tap", code=0x06),
                 mb.Step("up", code=0xE0), mb.Step("delay", ms=50),
                 mb.Step("char", code=ord("x"))]
        self.assertEqual(mk.describe(steps), 'Ctrl+C  ·  50 ms  ·  "x"')

    def test_it_survives_a_release_with_no_matching_press(self):
        """decode() will hand back whatever is in the buffer, including a body written
        by something other than this editor."""
        self.assertEqual(mk.describe([mb.Step("up", code=0xE0), mb.Step("tap", code=0x04)]),
                         "A")


class RoundTripTest(unittest.TestCase):
    def test_a_described_macro_encodes_and_decodes_unchanged(self):
        """The summary is a view of the steps, so it must not be the only thing that
        survives -- what is stored has to come back as what was built."""
        steps = [mb.Step("down", code=0xE0), mb.Step("tap", code=0x13),
                 mb.Step("up", code=0xE0), mb.Step("delay", ms=250),
                 mb.Step("char", code=ord("o")), mb.Step("char", code=ord("k"))]
        self.assertEqual(mb.decode(mb.encode_steps(steps)), steps)


if __name__ == "__main__":
    unittest.main()
