"""`runtime_legends` -- the emoji/language tables and the resting-state arithmetic.

These are parsers over firmware C plus index maths copied from two layer files, so
both halves fail the same silent way: a wrong answer renders a plausible-looking
keycap rather than an error. Fixtures are written in the firmware's own spelling.
"""
import os
import tempfile
import textwrap
import unittest

from polyhost.services import runtime_legends as rl


def _tree(**files) -> str:
    root = tempfile.mkdtemp()
    for rel, text in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent(text))
    return root


EMOJI_DATA = '''
    static const uint32_t emj_cat0[] = {
        0x1F600, 0x1F601, 0x1F602,   // Main smileys
        0x1F603,
    };
    static const uint32_t emj_cat1[] = {
        0x1F44B, 0x1F44C,
    };
    static const uint32_t emj_cat2[] = {
        0x1F3E0,
    };
    static const uint32_t emj_cat3[] = {
    };
    static const emj_category_t EMJ_CATEGORIES[] = {
        EMJ_CAT_ENTRY(emj_cat0),   // 0: Smileys & Faces        1F600
        EMJ_CAT_ENTRY(emj_cat1),   // 1: Gestures & Body
        EMJ_CAT_ENTRY(emj_cat2),   // 2: People & Jobs
        EMJ_CAT_ENTRY(emj_cat3),   // 3: empty -- draws nothing
    };
'''
EMOJI_LAYER = '''
    static const uint32_t emj_tab_icons[] = {
        0x1F973,  // cat  0
        0,        // cat  1: no hardwired icon
    };
'''
LANG_LAYER = '''
    static const uint8_t REGION_OFFSET[NUM_LANG_REGIONS + 1] = {
        0, 3, 5,
    };
    static const uint8_t REGION_LANGS[NUM_LANG] = {
        // Americas (3)
        78, 88, 32,
        // Europe (2)
         1,  2,
    };
    static const uint32_t *const REGION_LABELS[NUM_LANG_REGIONS] = {
        U"America",
        U"Europe",
    };
'''
POLY_KEYMAP = '''
    static const uint32_t* const lang_code[NUM_LANG] = {
        U"en-US",
        U"de-DE",
        U"fr-FR",
    };
'''


def _fixture() -> rl.RuntimeLegends:
    root = _tree(**{
        "emoji/emoji_data.h": EMOJI_DATA,
        "emoji/emoji_layer.c": EMOJI_LAYER,
        "lang_layer.c": LANG_LAYER,
        "poly_keymap.c": POLY_KEYMAP,
    })
    r = rl.RuntimeLegends()
    r.load(root)
    return r


class LoadingTest(unittest.TestCase):
    def test_a_missing_checkout_is_unusable_rather_than_raising(self):
        """Every accessor then answers None, so the editor falls back to keycode text
        instead of drawing a wrong glyph."""
        r = rl.RuntimeLegends()
        self.assertFalse(r.load(os.path.join(tempfile.mkdtemp(), "nope")))
        self.assertFalse(r.usable)
        self.assertIsNone(r.emoji_slot_cp(0))
        self.assertIsNone(r.lang_slot_index(0))

    def test_a_tree_missing_a_TABLE_is_unusable_too(self):
        """⚠️ Distinct from a missing checkout, which raises and returns early. Here
        every file opens and one table simply is not there -- the case a moved or
        renamed array produces, and the one a load that only catches exceptions
        reports as perfectly fine."""
        root = _tree(**{
            "emoji/emoji_data.h": EMOJI_DATA,
            "emoji/emoji_layer.c": EMOJI_LAYER,
            "lang_layer.c": "static const uint8_t REGION_OFFSET[2] = { 0, 1 };\n",
            "poly_keymap.c": POLY_KEYMAP,
        })
        r = rl.RuntimeLegends()
        self.assertFalse(r.load(root))
        self.assertFalse(r.usable)
        self.assertTrue(r.reason)

    def test_a_loaded_tree_reports_no_reason(self):
        r = _fixture()
        self.assertTrue(r.usable)
        self.assertEqual(r.reason, "")


class EmojiTest(unittest.TestCase):
    def setUp(self):
        self.r = _fixture()

    def test_categories_come_from_the_entry_list_in_its_own_order(self):
        """⚠️ Read the array NAMES out of EMJ_CATEGORIES rather than assuming
        `emj_cat<N>` counts up. That is true today and is not a contract -- the list's
        order IS the tab order."""
        self.assertEqual([len(c) for c in self.r._cats], [4, 2, 1, 0])

    def test_a_hardwired_tab_icon_wins(self):
        self.assertEqual(self.r.emoji_category_cp(0), 0x1F973)

    def test_a_zero_tab_icon_falls_back_to_the_first_codepoint(self):
        # `emj_display_text()`: `if (cp == 0) cp = ...codepoints[0]`.
        self.assertEqual(self.r.emoji_category_cp(1), 0x1F44B)

    def test_a_category_past_the_icon_table_falls_back_too(self):
        self.assertEqual(self.r.emoji_category_cp(2), 0x1F3E0)

    def test_an_unknown_category_draws_nothing(self):
        self.assertIsNone(self.r.emoji_category_cp(9))

    def test_an_EMPTY_category_draws_nothing_rather_than_its_first_codepoint(self):
        """`emj_display_text()` returns U"" for `count == 0`. Without the guard the
        fallback indexes [0] of an empty list -- an IndexError inside the render, i.e.
        a swallowed exception and a blank key, for a reason nothing would name."""
        self.assertIsNone(self.r.emoji_category_cp(3))

    def test_slots_come_from_category_zero_page_zero(self):
        self.assertEqual(self.r.emoji_slot_cp(0), 0x1F600)
        self.assertEqual(self.r.emoji_slot_cp(3), 0x1F603)

    def test_a_slot_past_the_category_is_empty(self):
        # A short category leaves the tail of the page blank, as the firmware does.
        self.assertIsNone(self.r.emoji_slot_cp(4))


class LanguageTest(unittest.TestCase):
    def setUp(self):
        self.r = _fixture()

    def test_region_labels_are_read_in_order(self):
        self.assertEqual(self.r.region_label(0), "America")
        self.assertEqual(self.r.region_label(1), "Europe")
        self.assertIsNone(self.r.region_label(7))

    def test_a_slot_indexes_region_zero_through_the_offset_table(self):
        """REGION_OFFSET carries one EXTRA trailing entry (the end of the last
        region), so a region's count is the gap to the next -- not len()/regions."""
        self.assertEqual([self.r.lang_slot_index(i) for i in range(3)], [78, 88, 32])

    def test_a_slot_past_the_region_is_empty_rather_than_the_next_region(self):
        """⚠️ Region 0 ends at offset 3 and region 1 begins there. Bounding on the
        table's length instead of the region's would spill Europe's languages onto
        America's empty slots -- a keycap showing a flag the board leaves blank."""
        self.assertIsNone(self.r.lang_slot_index(3))
        self.assertIsNone(self.r.lang_slot_index(4))

    def test_the_caption_comes_from_the_firmwares_own_table(self):
        # lang_code[] is cog-generated in poly_keymap.c; reading it there keeps the
        # flag keys free of the language LUT's openpyxl prerequisite.
        self.assertEqual(self.r.lang_code(0), "en-US")
        self.assertEqual(self.r.lang_code(2), "fr-FR")
        self.assertIsNone(self.r.lang_code(99))

    def test_the_flag_codepoint_is_the_pua_base_plus_the_language_index(self):
        self.assertEqual(self.r.flag_codepoint(0), 0xE000)
        self.assertEqual(self.r.flag_codepoint(78), 0xE04E)


if __name__ == "__main__":
    unittest.main()
