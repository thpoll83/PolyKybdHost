"""PolyKybd's own keycodes reaching the layout editor's browser.

The bug these pin: QMK's header names `QK_KB_0`..`QK_KB_31` and the firmware uses
39 slots, so `KC_AI` (0x7E26 = QK_KB_38) had no tile in the browser and could not
be assigned to a key at all.
"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from polyhost.services import custom_keycodes as ck   # noqa: E402

HEADER = """
// a comment mentioning KC_NOISE that must not be parsed
enum kb_keycodes {
    KC_LANG = QK_KB_0,
    KC_DMIN,
    /* block comment */
    KC_EDEN,
    KC_AI,
    KCL_ENUS = QK_USER_0,
};
"""


def _write(d, name, text):
    pathlib.Path(d, name).write_text(text, encoding="utf-8")


def _checkout(d, version, header=HEADER):
    _write(d, "keycode_helper.h", header)
    _write(d, "config.h", f'#define FW_VERSION "{version}"\n')
    return d


def _shipped(d, version, custom):
    _write(d, "legends.json", json.dumps(
        {"fw_version": version, "custom": {str(k): v for k, v in custom.items()}}))
    return d


class ParseTest(unittest.TestCase):
    def test_members_take_consecutive_values_from_the_anchor(self):
        got = ck.parse_custom_keycodes(HEADER)
        self.assertEqual(got[0x7E00], "KC_LANG")
        self.assertEqual(got[0x7E01], "KC_DMIN")
        self.assertEqual(got[0x7E02], "KC_EDEN")
        self.assertEqual(got[0x7E03], "KC_AI")

    def test_the_second_anchor_restarts_the_run(self):
        self.assertEqual(ck.parse_custom_keycodes(HEADER)[0x7E40], "KCL_ENUS")

    def test_an_unknown_initialiser_abandons_the_rest_rather_than_guessing(self):
        got = ck.parse_custom_keycodes(
            "enum e {\n    A = QK_KB_0,\n    B = SOMETHING_ELSE,\n    C,\n};\n")
        self.assertEqual(got.get(0x7E00), "A")
        self.assertNotIn("C", got.values())


class SlotsTest(unittest.TestCase):
    def test_every_value_in_qmks_kb_block_gets_an_entry(self):
        got = ck.slots()
        self.assertEqual(len(got), 64)
        self.assertEqual(min(got.values()), 0x7E00)
        self.assertEqual(max(got.values()), 0x7E3F)

    def test_the_block_is_assignable_with_NO_names_available(self):
        """The guarantee that does not depend on any data being current."""
        got = ck.slots({})
        self.assertEqual(got["QK_KB_38"], 0x7E26)

    def test_a_known_name_replaces_the_placeholder(self):
        got = ck.slots({0x7E26: "KC_AI"})
        self.assertEqual(got["KC_AI"], 0x7E26)
        self.assertNotIn("QK_KB_38", got)
        self.assertEqual(len(got), 64)   # still the whole block, one name each


class SourceTest(unittest.TestCase):
    def test_a_newer_checkout_wins(self):
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as c:
            _shipped(s, "0.17.2", {0x7E00: "OLD_NAME"})
            _checkout(c, "0.19.1")
            self.assertEqual(ck.names(s, c)[0x7E00], "KC_LANG")

    def test_an_OLDER_checkout_does_NOT_win(self):
        """A merely-old clone is the stale-clone failure, not a developer's tree."""
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as c:
            _shipped(s, "0.19.1", {0x7E00: "SHIPPED_NAME"})
            _checkout(c, "0.17.2")
            self.assertEqual(ck.names(s, c)[0x7E00], "SHIPPED_NAME")

    def test_equal_versions_take_the_shipped_copy(self):
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as c:
            _shipped(s, "0.19.1", {0x7E00: "SHIPPED_NAME"})
            _checkout(c, "0.19.1")
            self.assertEqual(ck.names(s, c)[0x7E00], "SHIPPED_NAME")

    def test_either_source_alone_still_names_the_block(self):
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as c:
            _checkout(c, "0.19.1")
            self.assertEqual(ck.names(s, c)[0x7E03], "KC_AI")     # no export
            _shipped(s, "0.19.2", {0x7E00: "SHIPPED_NAME"})
            self.assertEqual(ck.names(s, "")[0x7E00], "SHIPPED_NAME")   # no checkout

    def test_no_source_at_all_is_empty_rather_than_raising(self):
        with tempfile.TemporaryDirectory() as s:
            self.assertEqual(ck.names(s, ""), {})

    def test_browser_entries_cover_the_block_even_with_no_source(self):
        """The regression: KC_AI's slot must be clickable regardless."""
        with tempfile.TemporaryDirectory() as s:
            got = ck.browser_entries(s, "")
            self.assertEqual(len(got), 64)
            self.assertEqual(got["QK_KB_38"], 0x7E26)

    def test_browser_entries_name_the_slot_when_a_source_has_it(self):
        with tempfile.TemporaryDirectory() as s, tempfile.TemporaryDirectory() as c:
            _checkout(c, "0.19.1")
            self.assertEqual(ck.browser_entries(s, c)["KC_AI"], 0x7E03)


class LiveTest(unittest.TestCase):
    def test_the_real_repo_offers_KC_AI(self):
        entries = ck.browser_entries()
        self.assertEqual(entries.get("KC_AI", entries.get("QK_KB_38")), 0x7E26)


if __name__ == "__main__":
    unittest.main()
