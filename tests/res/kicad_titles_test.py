"""The generated KiCad block of overlay-mapping.poly.yaml and its generator.

No network: `fetch()` is the only step that reads KiCad's translations, and it
runs by hand. These tests check what is committed.
"""

import importlib.util
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "kicad_gen_titles",
    Path(__file__).resolve().parents[2] / "polyhost/res/overlay_sources/kicad/gen_titles.py")
gen_titles = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gen_titles)


class CommittedBlockTest(unittest.TestCase):

    def test_the_mapping_block_is_what_the_generator_writes(self):
        text = gen_titles.MAPPING_FILE.read_bytes().decode("utf-8")
        _head, block, _tail = gen_titles.split_mapping(text)
        self.assertEqual(block, gen_titles.render_block(gen_titles.load_titles()),
                         "run python polyhost/res/overlay_sources/kicad/gen_titles.py")

    def test_every_window_has_translations(self):
        names = gen_titles.load_titles()["names"]
        for key in gen_titles.WINDOWS:
            with self.subTest(window=key):
                self.assertGreater(len(names[key]), 30)


class TitleKeysTest(unittest.TestCase):

    def test_a_name_shared_by_two_windows_is_refused(self):
        data = {"names": {"pcb": {"xx": "Editor"}, "sch": {"yy": "Editor"}}}
        with self.assertRaises(ValueError):
            gen_titles.title_keys(data)

    def test_one_name_in_two_languages_is_listed_once(self):
        data = {"names": {"sym": {"da": "Symboleditor", "de": "Symboleditor"}}}
        self.assertEqual(gen_titles.title_keys(data)["sym"], ["Symbol Editor", "Symboleditor"])


class ParsePoTest(unittest.TestCase):

    PO = '''
msgid ""
msgstr ""
"Language: de\\n"

#: pcbnew/pcb_edit_frame.cpp:2146
msgid "PCB Editor"
msgstr "Leiterplatteneditor"

#, fuzzy
msgid "Symbol Editor"
msgstr "Symbol-Editor"

msgctxt "menu"
msgid "Footprint Editor"
msgstr "Kontext"

msgid "Gerber Viewer"
msgstr ""
"Gerber-"
"Betrachter"

msgid "3D Viewer"
msgstr ""
'''

    def test_translated_entries_are_read(self):
        table = gen_titles.parse_po(self.PO)
        self.assertEqual(table["PCB Editor"], "Leiterplatteneditor")
        self.assertEqual(table["Gerber Viewer"], "Gerber-Betrachter")

    def test_fuzzy_context_and_empty_entries_are_skipped(self):
        table = gen_titles.parse_po(self.PO)
        for msgid in ("Symbol Editor", "Footprint Editor", "3D Viewer", ""):
            self.assertNotIn(msgid, table)


if __name__ == "__main__":
    unittest.main()
