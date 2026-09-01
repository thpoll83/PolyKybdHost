"""`lang_demo`'s second legend seam and its derived keycode-alias table.

Both are PARSERS over firmware C, which is the shape this repo keeps getting bitten
by silently -- a pattern that matches nothing, or matches the wrong block, produces
a keycap that renders blank rather than an error. Fixtures here are written in the
firmware's own spelling (trailing `// ß` comments, a nested `switch (keycode)`, a
GCC case range) so a regression fails here instead of on a keycap.

Qt-free, and reads no firmware checkout: everything is a literal fixture.
"""
import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))

import lang_demo as ld  # noqa: E402


def _write(tmp, name, text):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(text))
    return path


class ToStaticTextMapTest(unittest.TestCase):
    """`to_static_text()` in poly_keymap.c -- the seam keycode_helper.c falls through to."""

    FN = '''
        const uint32_t* to_static_text(uint16_t keycode, led_t state) {
            if (local_state->unicode_mode == UNICODE_MODE_MACOS) {
                switch (keycode) {
                    case KC_KP_7: return U"7";
                    case KC_KP_8: return U"8";
                }
            }
            switch (keycode) {
                case KC_L0:  return local_layer->def_layer == _L0 ? WORD("Qwerty", ON)
                                                                  : WORD("Qwerty", OFF);
                case KC_L1:  return local_layer->def_layer == _L1 ? WORD("Stag!", ON)
                                                                  : WORD("Stag!", OFF);
                case KC_IDDQD: return doom_egg_armed() ? U"IDDQD" : U"";
                case KC_OS_SET_AUTO ... KC_OS_SET_END - 1: {
                    return os_legend[keycode - KC_OS_SET_BASE];
                }
                case KC_GLYPH_SIZE_UP: {
                    return legend[shifted ? 1 : 0][size];
                }
                case KC_COMPUTED: {
                    const uint32_t *p = pick();
                    return p;
                }
                case KC_RANGE_LO ... KC_RANGE_HI: return U"range";
                case KC_ALPHA:
                case KC_BETA: return U"ab";
            }
            return NULL;
        }
    '''

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.m = ld.parse_to_static_text_map(_write(self.tmp, "poly_keymap.c", self.FN))

    def test_the_nested_macos_switch_is_not_harvested(self):
        """⚠️ The function opens with a `switch (keycode)` for the macOS numpad,
        guarded by a mode a resting keycap is not in. Matching the first switch in
        the text returned twelve numpad digits and none of the real legends."""
        self.assertNotIn("KC_KP_7", self.m)
        self.assertNotIn("KC_KP_8", self.m)
        self.assertIn("KC_L0", self.m)

    def test_the_boot_layout_is_the_one_switch_drawn_on(self):
        """A board boots on _L0, so exactly one base-layer key rests in the ON state.
        Reading every `== _L<n>` as false renders a board with no layout selected."""
        self.assertEqual(self.m["KC_L0"], 'WORD("Qwerty", ON)')
        self.assertEqual(self.m["KC_L1"], 'WORD("Stag!", OFF)')

    def test_an_unarmed_easter_egg_rests_blank(self):
        self.assertEqual(self.m["KC_IDDQD"], 'U""')

    def test_a_case_range_is_left_out_rather_than_approximated(self):
        """Its legend is indexed off the keycode at runtime; there is no static
        answer. ⚠️ Assert on the SHAPE of every key, not on the absence of the one
        name: accepting the range appends the whole `A ... B - 1` string as a label,
        so `assertNotIn("KC_OS_SET_AUTO", ...)` passes over a map full of garbage."""
        self.assertNotIn("KC_OS_SET_AUTO", self.m)
        # ⚠️ A range whose body is a plain `return` is the shape the label filter
        # alone has to stop. Every range in the firmware today ALSO opens a block, so
        # a fixture without this one is caught by the brace guard and leaves the
        # filter untested -- which is exactly how this escaped a mutation once.
        self.assertNotIn("KC_RANGE_LO", self.m)
        for key in self.m:
            self.assertRegex(key, r"^[A-Za-z_]\w*$", f"non-token label kept: {key!r}")

    def test_a_block_case_is_left_out_even_when_its_return_looks_static(self):
        """⚠️ The lookup-table case is excluded twice over -- the `[` in
        `legend[...]` would catch it on its own -- so a block returning a plain
        local is what actually exercises the brace guard."""
        self.assertNotIn("KC_GLYPH_SIZE_UP", self.m)
        self.assertNotIn("KC_COMPUTED", self.m)

    def test_c_fall_through_gives_every_label_the_shared_return(self):
        self.assertEqual(self.m["KC_ALPHA"], 'U"ab"')
        self.assertEqual(self.m["KC_BETA"], 'U"ab"')


class DerivedAliasTest(unittest.TestCase):
    """QMK's own alias tables, read rather than re-typed."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        ld._DERIVED_ALIAS.clear()
        qmk = os.path.join(self.tmp, "qmk")
        os.makedirs(os.path.join(qmk, "quantum", "keymap_extras"))
        _write(qmk, os.path.join("quantum", "keycodes.h"), '''
            enum qk_keycode_defines {
                KC_A       = 0x0004,
                KC_MUTE    = KC_AUDIO_MUTE,
                KC_LBRC    = KC_LEFT_BRACKET,
                QK_BOOT    = QK_BOOTLOADER,
            };
        ''')
        _write(qmk, os.path.join("quantum", "keymap_extras", "keymap_german.h"), '''
            #define DE_SS   KC_MINS // ß
            #define DE_UDIA KC_LBRC // Ü
        ''')
        _write(qmk, os.path.join("quantum", "keymap_extras", "keymap_french.h"), '''
            #define FR_A KC_Q
        ''')
        fw = os.path.join(self.tmp, "polykybd")
        os.makedirs(fw)
        _write(fw, "poly_keymap.c", '#include "quantum/keymap_extras/keymap_german.h"\n')
        self.aliases = ld.load_qmk_aliases(qmk, fw)

    def tearDown(self):
        ld._DERIVED_ALIAS.clear()

    def test_only_the_extras_the_firmware_includes_are_read(self):
        """⚠️ Scoped, not globbed: 116 names are defined DIFFERENTLY across
        `keymap_extras/` (FR_MINS is four different keycodes), so loading them all
        resolves a token to whichever file was read last."""
        self.assertIn("DE_SS", self.aliases)
        self.assertNotIn("FR_A", self.aliases)

    def test_a_trailing_comment_does_not_hide_the_define(self):
        # Every line in keymap_german.h carries one; requiring end-of-line found none.
        self.assertEqual(self.aliases["DE_UDIA"], "KC_LBRC")

    def test_a_numeric_enum_entry_is_not_an_alias(self):
        self.assertNotIn("KC_A", self.aliases)
        self.assertEqual(self.aliases["KC_MUTE"], "KC_AUDIO_MUTE")

    def test_without_a_known_set_nothing_is_folded(self):
        """The fold is a fallback for a caller that says what it can draw. Applied
        unconditionally it is not safe in the harmless direction -- this repo keys on
        the SHORT name about as often as the long one, and 24 keys that rendered fine
        moved onto long names nothing has a legend for."""
        self.assertEqual(ld.normalize_kc("KC_MUTE"), "KC_MUTE")

    def test_a_token_we_can_already_draw_keeps_its_own_name(self):
        self.assertEqual(ld.normalize_kc("KC_MUTE", {"KC_MUTE", "KC_AUDIO_MUTE"}),
                         "KC_MUTE")

    def test_a_token_we_cannot_draw_folds_onto_one_we_can(self):
        self.assertEqual(ld.normalize_kc("KC_MUTE", {"KC_AUDIO_MUTE"}), "KC_AUDIO_MUTE")

    def test_the_chain_stops_at_the_first_renderable_hop(self):
        """⚠️ `DE_UDIA -> KC_LBRC -> KC_LEFT_BRACKET`, and the language LUT keys on
        the MIDDLE hop. Collapsing the chain to its endpoint at load time walked
        straight past the only name that renders."""
        self.assertEqual(ld.normalize_kc("DE_UDIA", {"KC_LBRC"}), "KC_LBRC")

    def test_a_chain_reaching_nothing_renderable_is_left_alone(self):
        self.assertEqual(ld.normalize_kc("DE_UDIA", {"KC_NOPE"}), "DE_UDIA")

    def test_a_second_load_re_reads_the_sources(self):
        """⚠️ The derived table must NOT survive as a populated process-global.

        A `KeycapPreview` is built per editor open and re-reads every other source it
        uses, so an alias map that skipped the work when already filled was the one
        piece of preview state with a process lifetime -- a checkout edited while the
        host runs would pair a fresh legend map with a stale alias table. Caught in
        review of #207; this fails against the early-return version.
        """
        qmk2 = os.path.join(self.tmp, "qmk2")
        os.makedirs(os.path.join(qmk2, "quantum", "keymap_extras"))
        _write(qmk2, os.path.join("quantum", "keycodes.h"), """
            enum qk_keycode_defines {
                KC_MUTE = KC_SOMETHING_ELSE,
            };
        """)
        fw2 = os.path.join(self.tmp, "fw2")
        os.makedirs(fw2)
        _write(fw2, "poly_keymap.c", "\n")
        again = ld.load_qmk_aliases(qmk2, fw2)
        self.assertEqual(again["KC_MUTE"], "KC_SOMETHING_ELSE")
        # and the previous checkout's entries are GONE, not merged over
        self.assertNotIn("DE_SS", again)

    def test_an_include_past_the_scan_bound_is_still_found(self):
        """The bound is measured against the real tree (deepest #include at byte
        4982), so a file with a long header comment must still be scanned."""
        qmk = os.path.join(self.tmp, "qmk")
        fw = os.path.join(self.tmp, "fw_deep")
        os.makedirs(fw)
        _write(fw, "poly_keymap.c",
               "// pad\n" * 700 + '#include "quantum/keymap_extras/keymap_german.h"\n')
        self.assertIn("keymap_german.h", ld._included_keymap_extras(fw))
        ld._DERIVED_ALIAS.clear()
        self.assertIn("DE_SS", ld.load_qmk_aliases(qmk, fw))

    def test_the_hand_kept_table_still_wins(self):
        # KC_ALIAS is the exception list precisely for names QMK answers differently.
        self.assertEqual(ld.normalize_kc("XXXXXXX", {"XXXXXXX", "KC_NO"}), "KC_NO")


if __name__ == "__main__":
    unittest.main()
