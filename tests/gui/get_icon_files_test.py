"""get_icon() builds a multi-size QIcon from the brand mark's size ladder.

Qt-free: only the filename arithmetic is under test, because that is the half
that fails silently -- QIcon on a path that does not exist yields an EMPTY icon,
so a wrong stem renders a menu entry with no picture and raises nothing.
"""
import pathlib
import unittest

from polyhost.gui.get_icon import icon_files

REPO = pathlib.Path(__file__).resolve().parents[2]
ICON_DIR = REPO / "polyhost" / "res" / "icons"


class IconFilesTest(unittest.TestCase):
    def test_the_brand_mark_resolves_to_its_ladder(self):
        files = icon_files("pcolor.png")
        self.assertGreater(len(files), 1, "expected the sized ladder, not one file")
        self.assertTrue(all(p.exists() for p in files))
        self.assertEqual(
            [p.name for p in files],
            [f"pcolor_{n}.png" for n in (16, 24, 32, 48, 64, 128, 256)],
        )

    def test_a_menu_glyph_resolves_to_itself(self):
        """The Material Symbols are single .svg files with no ladder beside them."""
        self.assertEqual(icon_files("power.svg"), [ICON_DIR / "power.svg"])

    def test_a_png_without_a_ladder_falls_back_to_the_file(self):
        self.assertEqual(
            icon_files("nosuchmark.png"), [ICON_DIR / "nosuchmark.png"]
        )


if __name__ == "__main__":
    unittest.main()
