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

    def test_spelling_folds_are_exact_not_fuzzy(self):
        """The small orthographic variants resolve by RULE, with no scoring.

        Plural s, British -our/-ise, and the singular/plural mismatch between a
        label and the lexicon. Each returns the "spelling" rule, which means a
        deterministic fold landed on a real entry -- not a similarity score that
        happened to clear a threshold.
        """
        for label, concept in (("Saves", "save"), ("Bookmarks", "bookmark"),
                               ("Favourites", "bookmark"), ("Option", "settings"),
                               ("Setting", "settings"), ("Preference", "settings")):
            m = si.match(label)
            self.assertIsNotNone(m, label)
            self.assertEqual(m.concept, concept, label)
            self.assertIn(m.rule, ("exact", "spelling"), label)

    def test_folding_is_symmetric(self):
        """Both sides are folded, or the rules only work in one direction.

        The lexicon stores "preferences"; a label reading "Preference" folds to
        itself, so without folding the TABLE too the two never meet and only a
        similarity score could join them.
        """
        self.assertEqual(si.fold_spelling("preferences"),
                         si.fold_spelling("preference"))
        self.assertIsNotNone(si.match("Preference"))

    def test_folds_do_not_collide_two_concepts(self):
        """No two lexicon phrases may fold to the same string."""
        seen: dict[str, str] = {}
        for phrase, concept in si._FOLDED_PHRASES:
            if phrase in seen:
                self.assertEqual(seen[phrase], concept,
                                 f"{phrase!r} folds from two concepts")
            seen[phrase] = concept

    def test_short_words_keep_their_trailing_s(self):
        """"News" must not fold to "new" and take the new-document icon."""
        self.assertEqual(si.fold_spelling("news"), "news")
        self.assertIsNone(si.match("News"))

    def test_translation_is_not_reachable_by_any_rule(self):
        # A wrong icon is worse than none: the caller would draw it INSTEAD of
        # the label text, which is the correct fallback on a non-English UI.
        for foreign in ("Speichern", "Enregistrer", "Guardar", "Salva"):
            self.assertIsNone(si.match(foreign), f"{foreign} should not match")

    def test_unknown_label_returns_none(self):
        # "To Opposite Case" used to live here; the change-case concept closed it.
        self.assertIsNone(si.match("Transpose"))
        self.assertIsNone(si.match("Sensitivity"))
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
        # The two that shipped wrong at the old 0.72 floor, plus News, which the
        # fuzzy rule still caught at 0.857 after the plural guard stopped the fold.
        for label in ("Edit", "Document", "News"):
            self.assertIsNone(si.match(label), label)
            self.assertIsNone(si.match(label, allow_fuzzy=True), label)

    def test_fuzzy_is_opt_in(self):
        """Off by default: measured, it produced 0 correct and 3 wrong matches.

        The cases it was carrying -- plural s, -our/-ise -- are handled by the
        spelling folds now, exactly and without a threshold. What is left is a
        typo net, which the caller can switch on if it wants one.
        """
        self.assertIsNone(si.match("Maximiz", allow_fuzzy=False))
        self.assertIsNotNone(si.match("Maximiz", allow_fuzzy=True))
        self.assertIsNone(si.match("Maximiz", min_confidence=0.99, allow_fuzzy=True))


class HintTest(unittest.TestCase):
    def test_a_hint_beats_every_rule(self):
        hints = {"save": "quit"}
        self.assertEqual(si.match("Save").concept, "save")          # rule
        m = si.match("Save", hints=hints)
        self.assertEqual((m.concept, m.rule, m.confidence), ("quit", "hint", 1.0))

    def test_text_hint_suppresses_without_looking_like_a_miss(self):
        """match() returns None either way, so suppressed() is what separates them.

        Only an unknown label belongs in the review queue. A label somebody has
        already decided is text must leave the queue, or it resurfaces every run
        and the queue stops being read.
        """
        self.assertIsNone(si.match("Bold"))
        self.assertTrue(si.suppressed("Bold"))
        self.assertIsNone(si.match("Transpose"))
        self.assertFalse(si.suppressed("Transpose"))

    def test_hint_accepts_a_literal_codepoint(self):
        m = si.match("Whatever", hints={"whatever": "U+1F4BE"})
        self.assertEqual(m.codepoint, 0x1F4BE)

    def test_hints_are_matched_on_the_normalized_label(self):
        for spelling in ("Bold", "&Bold", "  bold  ", "Bold..."):
            self.assertTrue(si.suppressed(spelling), spelling)

    def test_a_missing_hints_file_is_not_fatal(self):
        self.assertEqual(si.load_hints("/nonexistent/shortcut_hints.yaml"), {})

    def test_the_shipped_hints_file_is_valid(self):
        """Lint the data file -- a typo there fails silently, as a wrong icon.

        `resolve_hint` returns None for an unknown concept name exactly as it does
        for `text`, so a misspelled concept would quietly suppress the label
        instead of mapping it. This is the only thing that would catch that.
        """
        hints = si.load_hints()
        self.assertTrue(hints, "shipped hints file failed to load")
        for key, value in hints.items():
            self.assertEqual(key, si.normalize(key),
                             f"hint key {key!r} is not in normalized form")
            if value == si.SUPPRESS:
                continue
            self.assertIsNotNone(
                si.resolve_hint(value),
                f"hint {key!r} -> {value!r} is neither 'text', a known concept, "
                f"nor a parseable U+XXXX codepoint")


class GlyphAvailabilityTest(unittest.TestCase):
    def test_every_codepoint_resolves(self):
        """No lexicon entry may name a glyph the keyboard cannot draw."""
        from polyhost.services import macro_look as ml
        fonts, source = _fonts()
        if not fonts:
            self.skipTest("no fonts available")
        missing = []
        targets = [(c, cp) for c, (cp, _) in si.LEXICON.items()]
        for key, value in si.load_hints().items():
            if value != si.SUPPRESS:
                cp = si.resolve_hint(value)
                if cp is not None:
                    targets.append((f"hint:{key}", cp))
        for concept, cp in sorted(targets):
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
