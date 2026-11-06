"""Tests for the localized shortcut-label phrases (res/shortcut_lexicon/*.yaml).

Every language file is tried for every label, because nothing in a harvest says
which language a label is in. So the data tests below are what keeps one
language's word from drawing the wrong icon on another language's label.
"""

import os
import re
import unittest

import yaml

from polyhost.services import shortcut_icons as si

LEXICON_DIR = si.default_lexicon_dir()


def _files():
    return sorted(f for f in os.listdir(LEXICON_DIR) if f.endswith(".yaml"))


def _table(*rows):
    """A localized table in load order, for the rule tests."""
    out = [(si.normalize(p), c, lang) for p, c, lang in rows]
    out.sort(key=lambda pcl: (-len(pcl[0].split()), -len(pcl[0]), pcl[0], pcl[2]))
    return out


class LexiconDataTest(unittest.TestCase):
    """The shipped files."""

    def test_the_files_exist_and_parse(self):
        files = _files()
        self.assertGreaterEqual(len(files), 19, files)
        for name in files:
            with open(os.path.join(LEXICON_DIR, name), encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
            self.assertIsInstance(raw, dict, name)
            self.assertIsInstance(raw.get("concepts"), dict, name)

    def test_every_concept_is_a_lexicon_concept(self):
        for name in _files():
            with open(os.path.join(LEXICON_DIR, name), encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
            for concept, phrases in raw["concepts"].items():
                self.assertIn(concept, si.LEXICON, f"{name}: unknown concept {concept!r}")
                self.assertIsInstance(phrases, list, f"{name}: {concept}")
                self.assertTrue(phrases, f"{name}: {concept} has an empty list")

    def test_no_phrase_names_two_concepts(self):
        """One phrase, one concept, across ALL files and the English lexicon."""
        owner = {}
        for phrase, concept in si._PHRASES:
            owner[phrase] = (concept, "en")
        clashes = []
        for phrase, concept, lang in si.load_localized_lexicon(LEXICON_DIR):
            seen = owner.setdefault(phrase, (concept, lang))
            if seen[0] != concept:
                clashes.append(f"{phrase!r}: {seen[1]}={seen[0]}, {lang}={concept}")
        self.assertEqual(clashes, [])

    def test_no_phrase_is_too_short_to_trust(self):
        latin = re.compile(r"^[a-zÀ-ɏḀ-ỿ̀-ͯ ]+$")
        short = []
        for phrase, concept, lang in si.load_localized_lexicon(LEXICON_DIR):
            if len(phrase) < 2 or (latin.match(phrase) and len(phrase) < 3):
                short.append(f"{lang}: {phrase!r} ({concept})")
        self.assertEqual(short, [])

    def test_a_compact_phrase_never_hides_a_longer_one(self):
        """A Chinese/Japanese phrase inside a longer phrase of ANOTHER concept is
        only safe because the longer one is tried first; check that ordering
        holds for every such pair in the shipped data."""
        table = si.load_localized_lexicon(LEXICON_DIR)
        compact = [(p, c) for p, c, _ in table if si._is_compact(p)]
        for longer, longer_concept in compact:
            hit = si._localized_rules(longer, table)
            self.assertIsNotNone(hit, longer)
            self.assertEqual(hit.concept, longer_concept,
                             f"{longer!r} matched {hit.concept} via a shorter phrase")

    def test_some_real_labels(self):
        """Spot checks against labels real applications show."""
        si._LEXICON_CACHE = None
        cases = {
            "Speichern": "save", "Speichern unter...": "save as",
            "&Enregistrer": "save", "Guardar como…": "save as",
            "保存(&S)": "save", "名前を付けて保存": "save as",
            "复制(&C)": "copy", "Копировать": "copy",
        }
        for label, concept in cases.items():
            hit = si.match(label)
            self.assertIsNotNone(hit, label)
            self.assertEqual(hit.concept, concept, label)


class LocalizedRulesTest(unittest.TestCase):
    """The four rules, on a small table so each case is about one rule."""

    TABLE = _table(
        ("speichern", "save", "de"), ("speichern unter", "save as", "de"),
        ("in", "print", "vi"), ("rückgängig machen", "undo", "de"),
        ("保存", "save", "ja"), ("名前を付けて保存", "save as", "ja"),
        ("kopieren", "copy", "de"),
    )

    def rule(self, label):
        return si._localized_rules(si.normalize(label), self.TABLE)

    def test_exact(self):
        hit = self.rule("Speichern")
        self.assertEqual((hit.concept, hit.rule), ("save", "localized exact"))

    def test_longer_exact_phrase_wins(self):
        self.assertEqual(self.rule("Speichern unter...").concept, "save as")

    def test_phrase_inside_a_longer_label(self):
        hit = self.rule("Letzte Aktion rückgängig machen")
        self.assertEqual((hit.concept, hit.rule), ("undo", "localized phrase"))

    def test_keyword(self):
        hit = self.rule("Datei speichern")
        self.assertEqual((hit.concept, hit.rule), ("save", "localized keyword"))

    def test_earliest_keyword_wins(self):
        self.assertEqual(self.rule("Kopieren und speichern").concept, "copy")

    def test_a_short_latin_word_is_no_keyword(self):
        """Vietnamese "in" (print) must not reach an English "Log In"."""
        self.assertIsNone(self.rule("Log In"))
        self.assertEqual(self.rule("In").concept, "print")   # the whole label still does

    def test_compact_substring_longest_first(self):
        hit = self.rule("ファイルを保存")
        self.assertEqual((hit.concept, hit.rule), ("save", "localized compact"))
        self.assertEqual(self.rule("名前を付けて保存").concept, "save as")

    def test_compact_rule_needs_a_compact_label(self):
        self.assertIsNone(self.rule("Nothing to see"))

    def test_full_width_parentheses_are_stripped(self):
        self.assertEqual(si.normalize("保存（S）"), "保存")
        self.assertEqual(si.normalize("保存(S)"), "保存")


class EnglishTakesPriorityTest(unittest.TestCase):
    def test_an_english_label_keeps_its_icon(self):
        """The localized rules run only after every English rule failed."""
        saved = si._LEXICON_CACHE
        si._LEXICON_CACHE = _table(("open", "quit", "xx"), ("close", "save", "xx"))
        try:
            self.assertEqual(si.match("Open").concept, "open")
            self.assertEqual(si.match("Close").concept, "close")
        finally:
            si._LEXICON_CACHE = saved

    def test_no_files_no_change(self):
        self.assertEqual(si.load_localized_lexicon("/nonexistent/dir"), [])


if __name__ == "__main__":
    unittest.main()
