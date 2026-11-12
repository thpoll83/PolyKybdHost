import unittest

from polyhost.services.lang_regions import home_country, layout_note, region_of


class HomeCountryTest(unittest.TestCase):
    def test_ja_us_belongs_to_japan(self):
        self.assertEqual(home_country("jaUS"), "JP")

    def test_an_ordinary_language_keeps_its_country(self):
        self.assertEqual(home_country("jaJP"), "JP")
        self.assertEqual(home_country("enUS"), "US")
        self.assertEqual(home_country("deAT"), "AT")


class LayoutNoteTest(unittest.TestCase):
    def test_ja_us_keeps_its_layout_code_in_the_label(self):
        self.assertEqual(layout_note("jaUS"), "US")

    def test_an_ordinary_language_has_no_note(self):
        self.assertEqual(layout_note("jaJP"), "")
        self.assertEqual(layout_note("enUS"), "")


class RegionTest(unittest.TestCase):
    def test_ja_us_is_listed_under_asia_beside_ja_jp(self):
        self.assertEqual(region_of("jaUS"), "Asia")
        self.assertEqual(region_of("jaJP"), "Asia")
        self.assertEqual(region_of("enUS"), "Americas")

    def test_the_hawaiian_override_still_wins(self):
        self.assertEqual(region_of("hwUS"), "Oceania")

    def test_ja_us_sorts_next_to_ja_jp(self):
        langs = ["enUS", "jaUS", "deDE", "jaJP", "koKR"]
        ordered = sorted(langs, key=home_country)
        self.assertEqual(abs(ordered.index("jaUS") - ordered.index("jaJP")), 1)


if __name__ == "__main__":
    unittest.main()
