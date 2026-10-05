"""polyhost.i18n: language resolution, the .po reader, the helpers, and the
shipped catalogs.

The catalogs are drafts until a native speaker has reviewed them, so these
tests do not judge wording. They check what breaks the app or misleads a
user regardless of wording: a placeholder a translation dropped or renamed
(``_f`` raises KeyError on the user's screen), a plural count wrong for the
language, and a catalog that cannot be read.
"""
import os
import re
import string
import sys
import unittest

from polyhost import i18n


class ResolveTest(unittest.TestCase):

    def test_regional_variants_use_the_base_language(self):
        for tag, code in (("de-AT", "de"), ("de_CH.UTF-8", "de"), ("fr-CA", "fr"),
                          ("es-MX", "es"), ("ar-EG", "ar"), ("fa-IR", "fa"),
                          ("en-GB", "en"), ("nl-BE", "nl")):
            with self.subTest(tag=tag):
                self.assertEqual(i18n.match_os_language(tag), code)

    def test_portuguese_from_anywhere_uses_brazilian(self):
        self.assertEqual(i18n.match_os_language("pt-PT"), "pt_BR")
        self.assertEqual(i18n.match_os_language("pt"), "pt_BR")

    def test_chinese_is_decided_by_script_then_region(self):
        for tag, code in (("zh-Hant-TW", "zh_TW"), ("zh-TW", "zh_TW"), ("zh-HK", "zh_TW"),
                          ("zh-MO", "zh_TW"), ("zh-Hans-CN", "zh_CN"), ("zh-CN", "zh_CN"),
                          ("zh", "zh_CN"), ("zh-Hans-HK", "zh_CN"), ("zh_TW.UTF-8", "zh_TW")):
            with self.subTest(tag=tag):
                self.assertEqual(i18n.match_os_language(tag), code)

    def test_unshipped_and_posix_locales_do_not_match(self):
        for tag in ("sv-SE", "C", "POSIX", "", None, "he-IL"):
            with self.subTest(tag=tag):
                self.assertIsNone(i18n.match_os_language(tag))

    def test_auto_takes_the_first_shipped_os_language(self):
        self.assertEqual(i18n.resolve("auto", ["sv-SE", "fr-CH", "de"]), "fr")

    def test_nothing_shipped_means_english(self):
        self.assertEqual(i18n.resolve("auto", ["sv-SE", "C"]), "en")
        self.assertEqual(i18n.resolve("auto", []), "en")

    def test_a_pinned_setting_wins_over_the_os(self):
        self.assertEqual(i18n.resolve("ja", ["de-DE"]), "ja")

    def test_the_environment_wins_over_the_setting(self):
        self.assertEqual(i18n.resolve("ja", ["de-DE"], env="pseudo"), "pseudo")
        self.assertEqual(i18n.resolve("ja", ["de-DE"], env="ko"), "ko")

    def test_an_unknown_setting_follows_the_os(self):
        with self.assertLogs("polyhost.i18n", "WARNING"):
            self.assertEqual(i18n.resolve("xx", ["de-DE"]), "de")


class HelpersTest(unittest.TestCase):

    def tearDown(self):
        i18n.install(i18n.SOURCE_LANGUAGE)

    def test_english_returns_the_source_text(self):
        i18n.install("en")
        self.assertEqual(i18n._("Settings…"), "Settings…")
        self.assertEqual(i18n._f("Version {version}", version="1.2"), "Version 1.2")
        self.assertEqual(i18n._nf("{n} file", "{n} files", 1), "1 file")
        self.assertEqual(i18n._nf("{n} file", "{n} files", 3), "3 files")

    def test_values_are_isolated_only_in_a_right_to_left_language(self):
        i18n.install("de")
        self.assertNotIn("⁨", i18n._f("Version {version}", version="1.2"))
        i18n.install("ar")
        self.assertIn("⁨1.2⁩", i18n._f("Version {version}", version="1.2"))

    def test_format_specs_apply_before_isolation(self):
        for code in ("en", "ar"):
            i18n.install(code)
            with self.subTest(code=code):
                out = i18n._f("{size:,} bytes, {pct:.0f} %, {sec:02d}", size=12345, pct=42.4, sec=7)
                self.assertEqual(out.replace("\u2068", "").replace("\u2069", ""),
                                 "12,345 bytes, 42 %, 07")
                self.assertEqual(i18n._nf("{n:,} glyph", "{n:,} glyphs", 1200)
                                 .replace("\u2068", "").replace("\u2069", ""), "1,200 glyphs")

    def test_rtl_flags(self):
        self.assertEqual({lang.code for lang in i18n.LANGUAGES if lang.rtl}, {"ar", "fa"})
        self.assertTrue(i18n.is_rtl("fa"))
        self.assertFalse(i18n.is_rtl("de"))

    def test_an_unknown_code_installs_english(self):
        self.assertEqual(i18n.install("xx"), "en")
        self.assertEqual(i18n._("Settings…"), "Settings…")

    def test_pseudo_keeps_placeholders_markup_and_entities(self):
        out = i18n.pseudo_translate("Flash {n} bundles to %s <b>now</b> &amp; quit")
        for kept in ("{n}", "%s", "<b>", "</b>", "&amp;"):
            self.assertIn(kept, out)
        self.assertTrue(out.startswith("[") and out.endswith("]"))
        self.assertNotIn("Flash", out)

    def test_pseudo_still_formats(self):
        i18n.install("pseudo")
        self.assertIn("1.2", i18n._f("Version {version}", version="1.2"))
        self.assertIn("3", i18n._nf("{n} file", "{n} files", 3))


PO_SAMPLE = r'''
msgid ""
msgstr ""
"Language: pl\n"
"Plural-Forms: nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);\n"

#: polyhost/host.py:1
msgid "Settings…"
msgstr "Ustawienia…"

msgid "Line one\n"
"continued \"quoted\""
msgstr "Linia\n"
"dalej \"cytat\""

msgid "{n} file"
msgid_plural "{n} files"
msgstr[0] "{n} plik"
msgstr[1] "{n} pliki"
msgstr[2] "{n} plików"

#, fuzzy
msgid "Draft"
msgstr "Szkic"

msgid "Untranslated"
msgstr ""

msgctxt "verb"
msgid "Flash"
msgstr "Wgraj"

#~ msgid "Old"
#~ msgstr "Stare"
'''


class PoReaderTest(unittest.TestCase):

    def setUp(self):
        self.t = i18n.PoTranslations(PO_SAMPLE)

    def test_singular_continuation_and_escapes(self):
        self.assertEqual(self.t.gettext("Settings…"), "Ustawienia…")
        self.assertEqual(self.t.gettext('Line one\ncontinued "quoted"'), 'Linia\ndalej "cytat"')

    def test_plural_forms_follow_the_header(self):
        self.assertEqual(self.t.ngettext("{n} file", "{n} files", 1), "{n} plik")
        self.assertEqual(self.t.ngettext("{n} file", "{n} files", 3), "{n} pliki")
        self.assertEqual(self.t.ngettext("{n} file", "{n} files", 5), "{n} plików")
        self.assertEqual(self.t.ngettext("{n} file", "{n} files", 22), "{n} pliki")

    def test_fuzzy_untranslated_and_obsolete_fall_back_to_english(self):
        self.assertEqual(self.t.gettext("Draft"), "Draft")
        self.assertEqual(self.t.gettext("Untranslated"), "Untranslated")
        self.assertEqual(self.t.gettext("Old"), "Old")

    def test_context(self):
        self.assertEqual(self.t.pgettext("verb", "Flash"), "Wgraj")
        self.assertEqual(self.t.gettext("Flash"), "Flash")


def _fields(text):
    try:
        return sorted({f for _lit, f, _spec, _conv in string.Formatter().parse(text) if f})
    except ValueError:
        # Not a format string (shown with _(), e.g. the VIA syntax help with
        # its literal "{KC_A}"): the brace tokens must survive verbatim.
        return sorted(re.findall(r"\{[^{}]*\}", text))


class ShippedCatalogsTest(unittest.TestCase):
    """Every shipped .po against the template, whatever its wording."""

    @classmethod
    def setUpClass(cls):
        cls.catalogs = {}
        for lang in i18n.LANGUAGES:
            if lang.code == i18n.SOURCE_LANGUAGE:
                continue
            with open(i18n.po_path(lang.code), encoding="utf-8") as fh:
                cls.catalogs[lang.code] = fh.read()

    def test_every_language_has_a_catalog_that_loads(self):
        for code, text in self.catalogs.items():
            with self.subTest(code=code):
                header, entries = i18n.parse_po(text)
                self.assertTrue(entries)
                self.assertTrue(header.get("Plural-Forms"), "no Plural-Forms header")

    def test_translations_keep_every_placeholder(self):
        """A dropped or renamed {field} makes _f raise on the user's screen."""
        for code, text in self.catalogs.items():
            _header, entries = i18n.parse_po(text)
            for e in entries:
                expected = _fields(e["msgid"])
                for form in e["msgstr"]:
                    if not form or e["fuzzy"]:
                        continue
                    with self.subTest(code=code, msgid=e["msgid"][:60]):
                        got = _fields(form)
                        if e["msgid_plural"] is not None:
                            # A singular form may drop {n} ("one file").
                            self.assertLessEqual(set(got) - {"n"}, set(_fields(e["msgid_plural"])))
                            self.assertLessEqual(set(_fields(e["msgid_plural"])) - {"n"}, set(got))
                        else:
                            self.assertEqual(got, expected)

    def test_translations_keep_markup_tags(self):
        tag = re.compile(r"</?[a-zA-Z][^>]*>")
        for code, text in self.catalogs.items():
            _header, entries = i18n.parse_po(text)
            for e in entries:
                if e["msgid_plural"] is not None or not e["msgstr"][0] or e["fuzzy"]:
                    continue
                with self.subTest(code=code, msgid=e["msgid"][:60]):
                    self.assertEqual(sorted(tag.findall(e["msgid"])),
                                     sorted(tag.findall(e["msgstr"][0])))

    def test_plural_entries_have_the_languages_form_count(self):
        for code, text in self.catalogs.items():
            header, entries = i18n.parse_po(text)
            nplurals = int(re.search(r"nplurals\s*=\s*(\d+)", header["Plural-Forms"]).group(1))
            for e in entries:
                if e["msgid_plural"] is None:
                    continue
                with self.subTest(code=code, msgid=e["msgid"][:60]):
                    self.assertEqual(len(e["msgstr"]), nplurals)

    def test_every_catalog_covers_the_template(self):
        with open(os.path.join(i18n.LOCALE_DIR, "polyhost.pot"), encoding="utf-8") as fh:
            _h, pot = i18n.parse_po(fh.read())
        wanted = {(e["msgctxt"], e["msgid"]) for e in pot}
        for code, text in self.catalogs.items():
            with self.subTest(code=code):
                _h, entries = i18n.parse_po(text)
                self.assertEqual(wanted - {(e["msgctxt"], e["msgid"]) for e in entries}, set())

    def test_mnemonic_count_is_kept(self):
        """'&Quit' loses its keyboard accelerator if a translation drops the &."""
        amp = re.compile(r"&(?![a-zA-Z#0-9]+;|&)")
        for code, text in self.catalogs.items():
            _header, entries = i18n.parse_po(text)
            for e in entries:
                if e["msgid_plural"] is not None or not e["msgstr"][0] or e["fuzzy"]:
                    continue
                with self.subTest(code=code, msgid=e["msgid"][:60]):
                    self.assertEqual(len(amp.findall(e["msgid"])) > 0,
                                     len(amp.findall(e["msgstr"][0])) > 0)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MarkingTest(unittest.TestCase):
    """The UI modules show no unmarked literal, and none shadows ``_``."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        try:
            import i18n_strings
        finally:
            sys.path.pop(0)
        cls.tool = i18n_strings

    def test_no_unmarked_ui_literals(self):
        found = self.tool.scan_unmarked()
        self.assertEqual(found, [], "\n".join(f"{r}:{n}: {t!r}" for r, n, t in found[:40]))

    def test_no_function_both_calls_and_assigns_underscore(self):
        self.assertEqual(self.tool.scan_shadowed(), [])

    def test_the_scanner_finds_what_it_should(self):
        src = (
            "def f(w):\n"
            "    w.setText('Hello there')\n"
            "    w.setToolTip(_('Fine'))\n"
            "    QLabel(f'Count {n}')\n"
            "    QMessageBox.warning(None, 'Oops', _('Fine'))\n"
            "    log.warning('a log line')\n"
            "    w.setText('PolyKybd')  # i18n: skip\n"
            "    w.setText('…')\n"
            "def g():\n"
            "    ok, _ = h()\n"
            "    return _('x')\n"
        )
        self.assertEqual([t for _n, t in self.tool.scan_source(src)],
                         ["Hello there", "f'Count '", "Oops"])
        self.assertEqual(self.tool.scan_shadowed_underscore(src), [(9, "g")])

    @unittest.skipUnless(__import__("importlib").util.find_spec("babel"),
                         "extracting needs Babel (tools/requirements.txt)")
    def test_the_template_is_current(self):
        self.assertTrue(self.tool.pot_is_current(),
                        "polyhost.pot is stale: run `python scripts/i18n_strings.py update`")


if __name__ == "__main__":
    unittest.main()
