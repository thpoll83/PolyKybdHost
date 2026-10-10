"""`lang_demo.parse_ime_key` -- what KC_IME draws per language, read from firmware C.

The language list in `poly_ime_family()` is the part that drifts: a language the
firmware adds must reach the editor's preview without a host edit, and a parser
that matches nothing reports "no IME key" rather than an error. Fixtures use the
firmware's own spelling; one test reads the real tree when it is checked out beside
this repo.
"""
import os
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))

import lang_demo as ld  # noqa: E402

FIRMWARE_C = os.path.join(os.path.dirname(REPO), "qmk_firmware", "keyboards",
                          "polykybd", "poly_keymap.c")

LANGS = ["en-US", "de-DE", "ko-KR", "ja-JP", "en-AU"]

FIXTURE = """
    uint8_t poly_ime_family(uint8_t lang) {
        switch (lang) {
            case LANG_KOKR: return IME_FAMILY_KOREAN;
            case LANG_JAJP: return IME_FAMILY_JAPANESE;
            // an English list, as the firmware writes it
            case LANG_ENUS:
            case LANG_ENAU: return IME_FAMILY_RALT;
            default:        return IME_FAMILY_NONE;
        }
    }

    const uint32_t* to_static_text(uint16_t keycode, led_t state) {
        switch (keycode) {
            case KC_IME:
                if (poly_ime_family(local_state->lang) == IME_FAMILY_JAPANESE) {
                    return (local_layer->mods & MOD_MASK_SHIFT) != 0 ? ICON_KATAKANA : ICON_EISU_KANA;
                }
                return ICON_HAN_YEONG;

            case KC_GLYPH_SIZE_UP: {
                return ICON_FONT_BIGGER;
            }
        }
    }
"""


def _write(tmp, text):
    path = os.path.join(tmp, "poly_keymap.c")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(text))
    return path


class ParseImeKeyTest(unittest.TestCase):
    def test_families_and_icons_come_out_of_the_firmware_spelling(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = ld.parse_ime_key(_write(tmp, FIXTURE), LANGS)
        self.assertEqual(got["families"], {"ko-KR": "KOREAN", "ja-JP": "JAPANESE",
                                           "en-US": "RALT", "en-AU": "RALT"})
        self.assertEqual(got["icons"], {"KOREAN": "ICON_HAN_YEONG",
                                        "JAPANESE": "ICON_EISU_KANA",
                                        "JAPANESE_SHIFT": "ICON_KATAKANA"})

    def test_a_language_without_a_case_is_absent_so_it_draws_as_nubs(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = ld.parse_ime_key(_write(tmp, FIXTURE), LANGS)
        self.assertNotIn("de-DE", got["families"])

    def test_an_earlier_case_in_another_function_is_not_taken(self):
        """Only to_static_text()'s case is the legend: a key-event handler above it
        with its own `case KC_IME:` must not be read for icons."""
        earlier = """
            bool process_record_user(uint16_t keycode, keyrecord_t* record) {
                switch (keycode) {
                    case KC_IME:
                        return ICON_WRONG ? ICON_WRONG_A : ICON_WRONG_B;
                    default:
                        return true;
                }
            }
        """
        with tempfile.TemporaryDirectory() as tmp:
            got = ld.parse_ime_key(_write(tmp, earlier + FIXTURE), LANGS)
        self.assertEqual(got["icons"], {"KOREAN": "ICON_HAN_YEONG",
                                        "JAPANESE": "ICON_EISU_KANA",
                                        "JAPANESE_SHIFT": "ICON_KATAKANA"})

    def test_a_tree_without_the_key_returns_None(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write(tmp, "const uint32_t* to_static_text(uint16_t k) { switch (k) { } }")
            self.assertIsNone(ld.parse_ime_key(path, LANGS))

    @unittest.skipUnless(os.path.exists(FIRMWARE_C), "no qmk_firmware checkout beside this repo")
    def test_the_real_tree_parses_when_it_has_the_key(self):
        with open(FIRMWARE_C, encoding="utf-8") as fh:
            if "KC_IME" not in fh.read():
                self.skipTest("this firmware checkout predates KC_IME")
        got = ld.parse_ime_key(FIRMWARE_C, ["en-US", "ko-KR", "ja-JP", "de-DE"])
        self.assertIsNotNone(got)
        self.assertEqual(got["families"].get("ko-KR"), "KOREAN")
        self.assertEqual(got["families"].get("ja-JP"), "JAPANESE")
        self.assertEqual(got["families"].get("en-US"), "RALT")
        self.assertNotIn("de-DE", got["families"])
        self.assertEqual(set(got["icons"]), {"KOREAN", "JAPANESE", "JAPANESE_SHIFT"})


if __name__ == "__main__":
    unittest.main()
