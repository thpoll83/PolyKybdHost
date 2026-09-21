"""Tests for the label -> keycap glyph lexicon.

The load-bearing one is test_every_codepoint_resolves: a glyph the keyboard
cannot draw renders as a blank keycap with nothing to explain it, so the lexicon
is only trustworthy if every entry is checked against the fonts this host
actually ships.
"""

import unittest

from polyhost.services import icon_catalog
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
        #
        # `hints={}` on purpose: this pins the RULES, and "Edit" is now answered
        # by the shipped hints file as a menu-bar title. Reading the default
        # hints here would make the test pass for a reason that has nothing to do
        # with the fuzzy floor it exists to guard -- and would stop failing the
        # day somebody lowered that floor back to 0.72.
        for label in ("Edit", "Document", "News"):
            self.assertIsNone(si.match(label, hints={}), label)
            self.assertIsNone(si.match(label, hints={}, allow_fuzzy=True), label)

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
        self.assertIsNone(si.match("System"))
        self.assertTrue(si.suppressed("System"))
        self.assertIsNone(si.match("Transpose"))
        self.assertFalse(si.suppressed("Transpose"))

    def test_hint_accepts_a_literal_codepoint(self):
        m = si.match("Whatever", hints={"whatever": "U+1F4BE"})
        self.assertEqual(m.codepoint, 0x1F4BE)

    def test_hints_are_matched_on_the_normalized_label(self):
        for spelling in ("System", "&System", "  system  ", "System..."):
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
            self.assertTrue(
                si.hint_is_valid(value),
                f"hint {key!r} -> {value!r} is not 'text', a known concept, a "
                f"parseable U+XXXX codepoint, or an icon:<name>")

    def test_every_menu_bar_TITLE_draws_something(self):
        """A desktop menu bar arrives as six shortcuts, and every one must draw.

        This is the set a user sees first -- Alt+F/E/V/T/H and Favorites are one
        keycap row -- so a single refusal in it is the most visible gap the
        feature has. The hints file previously claimed Edit "already resolves on
        its own"; it did not, and a field log on 7-Zip is what caught it. Pin the
        whole bar rather than the two labels that happened to be added last.
        """
        for label in ("File", "Edit", "View", "Favorites", "Tools", "Help"):
            with self.subTest(label=label):
                self.assertIsNotNone(si.match(label),
                                     f"{label} is a menu-bar title with no icon")

    def test_a_menu_TITLE_hint_does_not_reach_a_longer_label(self):
        """A hint answers one label exactly, which is what makes it safe here.

        "Tools" is the menu; "Developer Tools" and "Tool" are not it, and a
        keyword rule would have taken all three. The mnemonic marker and the
        trailing ellipsis normalise away, so only the real spellings hit.
        """
        self.assertIsNotNone(si.match("&Tools..."))
        for label in ("Developer Tools", "Tool", "Editor", "Edit Mode"):
            with self.subTest(label=label):
                self.assertIsNone(si.match(label), label)


class CatalogIconTest(unittest.TestCase):
    def test_every_concept_names_a_catalog_icon(self):
        """A concept without an icon name can only ever draw from a bundle.

        The catalog is what makes the feature generic -- 4277 icons, no reship --
        so an entry that names none is a concept the on-demand path cannot serve.
        """
        for concept, (_, icon, _) in si.LEXICON.items():
            self.assertTrue(icon, f"{concept} has no catalog icon name")
            self.assertRegex(icon, r"^[a-z0-9_]+$", concept)

    def test_the_formerly_impossible_concepts_are_catalog_only(self):
        """Bold and friends have no bundle glyph, and need none.

        Each was `text` while the font pack was the only route: the shipped fonts
        carry no bold, italic or paintbrush glyph among their 7242 codepoints,
        and adding one meant fontconvert plus a bundle reship. This pins that
        they now resolve, and that they resolve WITHOUT a codepoint -- so a
        regression that quietly gave them one would be visible.
        """
        for label, icon in (("Bold", "format_bold"), ("Italic", "format_italic"),
                            ("Underline", "format_underlined"),
                            ("Superscript", "superscript"),
                            ("Subscript", "subscript"),
                            ("Format Painter", "format_paint")):
            m = si.match(label)
            self.assertIsNotNone(m, label)
            self.assertEqual(m.icon, icon, label)
            self.assertIsNone(m.codepoint, label)

    def test_a_hint_can_name_a_catalog_icon(self):
        m = si.match("Whatever", hints={"whatever": "icon:rocket_launch"})
        self.assertEqual(m.icon, "rocket_launch")
        self.assertIsNone(m.codepoint)

    def test_the_lint_accepts_icon_values_and_rejects_typos(self):
        """`icon:` is explicit so a misspelled CONCEPT still fails the lint.

        Treating any unrecognised bare word as a catalog name would make the lint
        accept everything, and a typo would then fail as a missing icon -- the
        shape nobody investigates.
        """
        self.assertTrue(si.hint_is_valid("icon:rocket_launch"))
        self.assertTrue(si.hint_is_valid("save"))
        self.assertTrue(si.hint_is_valid("U+1F4BE"))
        self.assertTrue(si.hint_is_valid("text"))
        self.assertFalse(si.hint_is_valid("saev"))

    def test_char_is_empty_without_a_codepoint(self):
        self.assertEqual(si.match("Bold").char, "")
        self.assertEqual(si.match("Save").char, chr(0x1F4BE))


class GlyphAvailabilityTest(unittest.TestCase):
    def test_every_codepoint_resolves(self):
        """No lexicon entry may name a glyph the keyboard cannot draw."""
        from polyhost.services import macro_look as ml
        fonts, source = _fonts()
        if not fonts:
            self.skipTest("no fonts available")
        if source != "headers":
            # The shipped .plyf bundles are the PACK half only, so every resident
            # glyph reads as absent and this cannot distinguish a bad entry from a
            # missing font source. Hand-listing the resident ones as exemptions was
            # tried and is the guard shape that goes stale: it covered the four
            # arrows, passed on an interpreter that could load the headers, and
            # failed on one that could not. Needs a qmk_firmware checkout and
            # Pillow (tools/gfx_font parses the committed headers with it).
            self.skipTest("headers unavailable (need a qmk_firmware checkout + "
                          "Pillow); a packs-only load cannot see resident glyphs")
        missing = []
        # A catalog-only concept has no bundle glyph by design; nothing to check.
        targets = [(c, cp) for c, (cp, _, _) in si.LEXICON.items() if cp is not None]
        for key, value in si.load_hints().items():
            cp = si.resolve_hint(value)
            if cp is not None:
                targets.append((f"hint:{key}", cp))
        for concept, cp in sorted(targets):
            if ml.find_glyph(fonts, cp) is None:
                missing.append(f"{concept} U+{cp:04X}")
        self.assertEqual(missing, [], f"unrenderable glyphs ({source}): {missing}")


class FluentPreferenceTest(unittest.TestCase):
    """Which catalog draws a concept, and why absence is the mechanism."""

    def test_a_concept_WITH_a_fluent_name_resolves_to_FACES_zero(self):
        # ⚠️ Tied to FACES rather than the literal "fluent", or that constant
        # is decorative: it declares the preference order and nothing reads it.
        for concept in ("save", "undo", "close"):
            with self.subTest(concept):
                face, _ = icon_catalog.split_face(si.icon_for(concept))
                self.assertEqual(face, icon_catalog.FACES[0])

    def test_a_concept_WITHOUT_one_falls_back_to_material(self):
        """Absence from FLUENT_ICONS IS the fall-back, so there is no second
        rule to keep in step with the first."""
        for concept in ("copy", "paste", "select all"):
            with self.subTest(concept):
                self.assertTrue(si.icon_for(concept).startswith(
                    icon_catalog.MATERIAL + ":"))

    def test_the_material_fallback_names_the_LEXICON_spelling(self):
        self.assertEqual(si.icon_for("copy"),
                         f"{icon_catalog.MATERIAL}:{si.LEXICON['copy'][1]}")

    def test_an_unknown_concept_resolves_to_NOTHING_not_a_bare_face(self):
        # `plan_report` tests this for falsiness; "fluent:" would be truthy and
        # would render `.notdef`, a filled box that wipes the legend.
        self.assertEqual(si.icon_for("no-such-concept"), "")

    def test_every_fluent_name_belongs_to_a_REAL_concept(self):
        """A typo'd key is silently inert — the concept keeps drawing Material
        and nothing reports it."""
        self.assertEqual(sorted(set(si.FLUENT_ICONS) - set(si.LEXICON)), [])

    def test_the_five_MATERIAL_OVERRIDES_are_deliberate_and_named(self):
        """⚠️ Pinned so a later bulk edit cannot quietly hand them to Fluent.

        Each lost the render at 36 px 1-bit, which is a judgement made by
        looking — see the reasons on FLUENT_ICONS. Changing this set is fine;
        changing it without re-rendering is not.
        """
        self.assertEqual(sorted(set(si.LEXICON) - set(si.FLUENT_ICONS)),
                         ["copy", "paste", "select all", "subscript",
                          "superscript"])




class CloseFamilyTest(unittest.TestCase):
    """⚠️ Found by READING THE LOG on a real harvest, not by reading the table.

    "Close Window" resolved to the `window` concept — a window frame on Ctrl+W,
    where the action is CLOSE and the object is incidental. Its two siblings
    "Close Tab" and "Close Document" already drew an X, so one entry made three
    identically-shaped labels disagree, and the keycap could not be told from
    "New Window".

    This is the shortcut-icon report earning its keep: the defect is invisible
    from the lexicon (both entries read fine on their own) and obvious the moment
    one line prints `Ctrl+W=window` beside `Ctrl+N=new`.
    """

    def test_every_CLOSE_something_label_draws_the_close_icon(self):
        for label in ("Close", "Close Tab", "Close Document", "Close Window"):
            with self.subTest(label=label):
                hit = si.match(label, allow_fuzzy=True)
                self.assertIsNotNone(hit, label)
                self.assertEqual(hit.concept, "close", label)

    def test_a_window_label_that_is_NOT_a_close_still_draws_a_window(self):
        for label in ("Window", "New Window"):
            with self.subTest(label=label):
                self.assertEqual(si.match(label, allow_fuzzy=True).concept, "window")

    def test_word_wrap_is_a_CATALOG_ONLY_concept(self):
        """No font-pack glyph exists for it and none will without a bundle
        reship — which is the wall the catalog route was added to remove."""
        hit = si.match("Word Wrap", allow_fuzzy=True)
        self.assertEqual(hit.concept, "wrap text")
        self.assertIsNone(hit.codepoint)
        self.assertEqual(hit.icon, "wrap_text")


class HideIsTheVerbNotTheApp(unittest.TestCase):
    """⚠️ Field, 2026-09-21. Every macOS app puts "Hide <AppName>" on Cmd+H.

    With no `hide` concept the LEXICON missed, `derive_names` fell through to
    the TAIL word, and the app's own name is very often a catalog icon -- so
    Terminal drew a terminal, Notes a note and Chess a chess piece on a key
    whose entire meaning is the verb. A WRONG keycap rather than a missing one,
    and it repeated the program mark already sitting on ESC.
    """

    def test_hide_APPNAME_resolves_to_hide_on_every_app_that_regressed(self):
        for label in ("Hide Terminal", "Hide Notes", "Hide Chess",
                      "Hide Maps", "Hide Photos", "Hide Finder",
                      "Hide Freeform", "Hide Safari"):
            hit = si.match(label, allow_fuzzy=True)
            self.assertIsNotNone(hit, label)
            self.assertEqual(hit.concept, "hide", label)

    def test_the_TAIL_WORD_no_longer_answers_for_these_labels(self):
        """The regression itself, stated as the derivation that caused it.

        `derive_names` is unchanged -- it still offers the tail -- so this
        pins that the LEXICON answers first, which is the whole fix."""
        known = {"terminal", "notes", "chess"}
        for label, wrong in (("Hide Terminal", "terminal"),
                             ("Hide Notes", "notes"),
                             ("Hide Chess", "chess")):
            derived = next((n for n in si.derive_names(label) if n in known), None)
            self.assertEqual(derived, wrong,
                             "the derivation that caused it has changed; "
                             "re-read whether this test still pins anything")
            self.assertEqual(si.match(label, allow_fuzzy=True).concept, "hide")

    def test_it_also_rescues_the_ones_that_drew_NOTHING(self):
        """Hide Others and friends matched no concept at all before."""
        for label in ("Hide Others", "Hide Folders", "Hide Downloads",
                      "Hide Alternative Screen"):
            hit = si.match(label, allow_fuzzy=True)
            self.assertIsNotNone(hit, label)
            self.assertEqual(hit.concept, "hide", label)

    def test_HIDDEN_is_not_hide(self):
        """⚠️ The phrase is the word "hide". "Show Hidden Files" REVEALS, so a
        substring rule would put an eye-with-a-slash on its exact opposite."""
        self.assertNotEqual(
            getattr(si.match("Show Hidden Files", allow_fuzzy=True), "concept", None),
            "hide")

    def test_both_faces_carry_the_icon(self):
        face, name = icon_catalog.split_face(si.icon_for("hide"))
        self.assertEqual(face, icon_catalog.FLUENT)
        self.assertEqual(name, "eye_off")
        self.assertEqual(si.LEXICON["hide"][1], "visibility_off")


class TheKeywordRuleTakesTheLEADINGWord(unittest.TestCase):
    """⚠️ Among several one-word phrases in one label, the EARLIEST wins.

    A menu label is imperative -- the verb leads and the rest is its object --
    so the leading word is the one carrying the command. The table is sorted
    longest-phrase-first, and that made "Hide App Store" match `store` -> SAVE,
    because "store" is one character longer than "hide". That is exactly as
    arbitrary a decider as the table order the sort comment exists to remove.
    """

    def test_hide_app_store_is_a_HIDE_and_not_a_SAVE(self):
        self.assertEqual(si.match("Hide App Store", allow_fuzzy=True).concept,
                         "hide")

    def test_both_words_really_are_phrases_so_the_test_pins_a_CHOICE(self):
        """⚠️ Without this the test above passes for the wrong reason -- if
        "store" ever stops being a phrase there is nothing left to choose
        between and the rule is no longer under test."""
        singles = {phrase: concept for phrase, concept in si._PHRASES
                   if " " not in phrase}
        self.assertEqual(singles.get("store"), "save")
        self.assertEqual(singles.get("hide"), "hide")

    def test_the_trailing_word_still_answers_when_it_is_the_ONLY_match(self):
        """The rule reorders; it does not narrow. A label whose only lexicon
        word is at the end resolves exactly as before."""
        self.assertEqual(si.match("Page Down", allow_fuzzy=True).concept,
                         si.match("Down", allow_fuzzy=True).concept)


if __name__ == "__main__":
    unittest.main()
