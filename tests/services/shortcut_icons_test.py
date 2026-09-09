"""Tests for the label -> keycap glyph lexicon.

The load-bearing one is test_every_codepoint_resolves: a glyph the keyboard
cannot draw renders as a blank keycap with nothing to explain it, so the lexicon
is only trustworthy if every entry is checked against the fonts this host
actually ships.
"""

import unittest

from polyhost.services import shortcut_icons as si


def _fonts():
    """The union macro_look builds: resident headers where available, plus packs."""
    from polyhost.services import macro_look as ml
    return ml.load_render_fonts()


class NormalizeTest(unittest.TestCase):
    def test_strips_what_real_toolkits_emit(self):
        # Every one of these is a real label shape, not an invented one.
        self.assertEqual(si.normalize("New      "), "new")          # mousepad padding
        self.assertEqual(si.normalize("Save As..."), "save as")
        self.assertEqual(si.normalize("Find and Replace…"), "find and replace")
        self.assertEqual(si.normalize("_Open"), "open")             # GTK mnemonic
        self.assertEqual(si.normalize("&Save"), "save")             # Qt/Win32 mnemonic
        self.assertEqual(si.normalize("Zoom In (150%)"), "zoom in")

    def test_empty_label_is_empty(self):
        self.assertEqual(si.normalize("   ...  "), "")


class MatchTest(unittest.TestCase):
    def test_exact_phrase(self):
        m = si.match("Save")
        self.assertEqual((m.concept, m.rule, m.confidence), ("save", "exact", 1.0))

    def test_longer_phrase_beats_the_word_it_contains(self):
        # "Save As" must not resolve to the floppy for plain "save".
        self.assertEqual(si.match("Save As...").concept, "save as")
        self.assertEqual(si.match("Save").concept, "save")
        self.assertNotEqual(si.match("Save As...").codepoint,
                            si.match("Save").codepoint)

    def test_phrase_inside_a_longer_label(self):
        m = si.match("Find Next Occurrence")
        self.assertEqual(m.concept, "find next")
        self.assertEqual(m.rule, "phrase")

    def test_keyword_inside_a_label(self):
        m = si.match("Quick Save")
        self.assertEqual((m.concept, m.rule), ("save", "keyword"))

    def test_multi_word_labels_do_not_fuzzy_match(self):
        """The regression that motivated restricting fuzzy to single words.

        "Autosave Document" scored 0.774 against "close document" -- clearing any
        useful threshold and putting a door icon on a save shortcut.
        """
        self.assertIsNone(si.match("Autosave Document"))

    def test_fuzzy_covers_wording_drift_not_translation(self):
        # Morphology: fuzzy earns its keep here.
        self.assertIsNotNone(si.match("Preference"))
        # Translation: it cannot, and must not pretend to. A wrong icon is worse
        # than none, because the caller would draw it instead of the label text.
        for foreign in ("Speichern", "Enregistrer", "Guardar", "Salva"):
            self.assertIsNone(si.match(foreign), f"{foreign} should not match")

    def test_unknown_label_returns_none(self):
        self.assertIsNone(si.match("To Opposite Case"))
        self.assertIsNone(si.match(""))

    def test_confidence_is_ordered_by_rule(self):
        self.assertGreater(si.match("Save").confidence,
                           si.match("Quick Save").confidence)

    def test_the_fuzzy_floor_sits_in_a_measured_gap(self):
        """FUZZY_FLOOR must keep real morphology and reject near-miss words.

        Re-derives the separation rather than asserting the constant, so a new
        word landing inside the gap fails here instead of silently mis-icon-ing
        a keycap. Both false-friend pairs below were real mousepad menu labels.
        """
        import difflib
        ratio = lambda a, b: difflib.SequenceMatcher(None, a, b).ratio()
        morphology = [("preference", "preferences"), ("maximise", "maximize"),
                      ("favourite", "favorite"), ("setting", "settings")]
        false_friends = [("edit", "exit"), ("document", "documentation"),
                         ("save", "safe"), ("find", "fine")]
        for a, b in morphology:
            self.assertGreaterEqual(ratio(a, b), si.FUZZY_FLOOR, f"{a}~{b}")
        for a, b in false_friends:
            self.assertLess(ratio(a, b), si.FUZZY_FLOOR, f"{a}~{b}")

    def test_short_near_miss_words_do_not_match(self):
        # The two that shipped wrong at the old 0.72 floor.
        self.assertIsNone(si.match("Edit"))
        self.assertIsNone(si.match("Document"))

    def test_min_confidence_gates_the_fuzzy_rule(self):
        self.assertIsNone(si.match("Preference", min_confidence=0.99))


class GlyphAvailabilityTest(unittest.TestCase):
    def test_every_codepoint_resolves(self):
        """No lexicon entry may name a glyph the keyboard cannot draw."""
        from polyhost.services import macro_look as ml
        fonts, source = _fonts()
        if not fonts:
            self.skipTest("no fonts available")
        missing = []
        for concept, (cp, _) in sorted(si.LEXICON.items()):
            if ml.find_glyph(fonts, cp) is None:
                # The four navigation arrows live in the RESIDENT IconsFont, which
                # only the firmware headers carry -- the shipped .plyf bundles are
                # the pack half alone. Absent from a packs-only load is expected
                # and is not a broken entry.
                if source == "packs" and cp in (si.ICON_UP, si.ICON_DOWN,
                                                si.ICON_LEFT, si.ICON_RIGHT):
                    continue
                missing.append(f"{concept} U+{cp:04X}")
        self.assertEqual(missing, [], f"unrenderable glyphs ({source}): {missing}")


if __name__ == "__main__":
    unittest.main()
