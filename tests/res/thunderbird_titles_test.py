"""The generated Thunderbird block of overlay-mapping.poly.yaml and its generator.

No network: `fetch()` is the only step that reads Thunderbird's translations,
and it runs by hand. These tests check what is committed.
"""

import importlib.util
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "thunderbird_gen_titles",
    Path(__file__).resolve().parents[2] / "polyhost/res/overlay_sources/thunderbird/gen_titles.py")
gen_titles = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gen_titles)


class CommittedBlockTest(unittest.TestCase):

    def test_the_mapping_block_is_what_the_generator_writes(self):
        text = gen_titles.MAPPING_FILE.read_bytes().decode("utf-8")
        _head, block, _tail = gen_titles.split_mapping(text)
        self.assertEqual(block, gen_titles.render_block(gen_titles.load_titles()),
                         "run python polyhost/res/overlay_sources/thunderbird/gen_titles.py")

    def test_most_languages_have_a_prefix(self):
        data = gen_titles.load_titles()
        self.assertGreater(len(data["prefixes"]), 50)
        self.assertEqual(data["prefixes"]["de"], "Verfassen:")


class TitleKeysTest(unittest.TestCase):

    def test_english_first_and_each_prefix_once(self):
        data = {"prefixes": {"en-GB": "Write:", "da": "Skriv:", "sv-SE": "Skriv:"}}
        self.assertEqual(gen_titles.title_keys(data), ["Write:", "Skriv:"])


class ParseTest(unittest.TestCase):

    def test_ftl_prefix_is_the_text_before_the_subject(self):
        ftl = "compose-window-title = Rédaction : { $subject } - { $brand }\n"
        self.assertEqual(gen_titles.prefix_from_ftl(ftl), "Rédaction :")

    def test_properties_prefix_is_the_text_before_the_first_argument(self):
        props = "windowTitleWrite = Verfassen: %1$S - %2$S\n"
        self.assertEqual(gen_titles.prefix_from_properties(props), "Verfassen:")

    def test_a_missing_key_gives_none(self):
        self.assertIsNone(gen_titles.prefix_from_ftl("other = x\n"))
        self.assertIsNone(gen_titles.prefix_from_properties("other=x\n"))


if __name__ == "__main__":
    unittest.main()
