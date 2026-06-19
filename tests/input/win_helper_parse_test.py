"""Regression test for WindowsInputHelper._parse_current_culture.

The get_current_language query once let PowerShell default-format the
InputLanguage object, which renders as a TABLE ("Culture  Handle  LayoutName"
header + data row). The parser matched the *header* line and returned the
literal "Culture   Handle LayoutName" as the current language, so no comparison
in set_language ever matched and OS language switching always failed
(field log 2026-06-19). The query now emits an explicit "Culture: <name>" line;
this pins the parse so the header can never be mistaken for the value again.

Importing win_helper pulls pynput (an X server), so this skips without a
display — like the other GUI-adjacent tests.
"""
import os
import unittest

if not os.environ.get("DISPLAY"):
    raise unittest.SkipTest("win_helper import needs pynput/X (no DISPLAY)")

from polyhost.input.win_helper import WindowsInputHelper

_parse = WindowsInputHelper._parse_current_culture
_parse_tags = WindowsInputHelper._parse_language_tags


class ParseCurrentCultureTest(unittest.TestCase):
    def test_value_line_is_parsed(self):
        self.assertEqual(_parse("Culture: en-US"), (True, "en-US"))

    def test_value_line_as_bytes(self):
        self.assertEqual(_parse(b"Culture: de-DE"), (True, "de-DE"))

    def test_tolerates_space_before_colon(self):
        # The legacy Start-Job list format ("Culture : en-US") must still parse.
        self.assertEqual(_parse("Culture : en-US"), (True, "en-US"))

    def test_table_header_is_not_mistaken_for_value(self):
        # The exact shape that broke switching: a header row (no colon) followed
        # by a data row. Must NOT return the header text.
        table = ("Culture   Handle LayoutName\n"
                 "-------   ------ ----------\n"
                 "en-US        123 US")
        ok, value = _parse(table)
        self.assertFalse(ok)
        self.assertNotIn("LayoutName", str(value) if ok else "")

    def test_value_line_among_other_output(self):
        out = b"\n\nCulture: en-GB\n"
        self.assertEqual(_parse(out), (True, "en-GB"))

    def test_no_culture_line_returns_false(self):
        ok, _ = _parse("nothing useful here")
        self.assertFalse(ok)


class ParseLanguageTagsTest(unittest.TestCase):
    def test_single_tag(self):
        self.assertEqual(_parse_tags("LanguageTag: en-US"), ["en-US"])

    def test_multiple_tags_as_bytes(self):
        out = b"LanguageTag: en-US\nLanguageTag: de-DE\n"
        self.assertEqual(_parse_tags(out), ["en-US", "de-DE"])

    def test_table_header_is_ignored(self):
        # Multi-language default formatting would put a value-less header first.
        table = ("LanguageTag Autonym  EnglishName\n"
                 "----------- -------  -----------\n"
                 "en-US       English  English")
        # The header has no colon -> not collected; the (mangled) data row also
        # lacks our 'LanguageTag:' shape, so nothing bogus is returned.
        self.assertEqual(_parse_tags(table), [])

    def test_empty_output(self):
        self.assertEqual(_parse_tags(""), [])


if __name__ == "__main__":
    unittest.main()
