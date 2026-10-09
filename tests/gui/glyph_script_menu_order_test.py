"""The Keycap Script submenu is built from GLYPH_SCRIPT_LABELS, in its order.

The enum is append-only (its values are on the wire and in the keyboard's
EEPROM), so a script added later sits at the end of GlyphScript. The menu
follows the label dict instead, which lets related scripts sit together. Because
the menu iterates the dict, an enum value missing from it would silently have no
menu entry; these tests catch that.
"""
import unittest

from polyhost.device.command_ids import GlyphScript


class GlyphScriptMenuOrderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from polyhost.host import GLYPH_SCRIPT_LABELS
        cls.labels = GLYPH_SCRIPT_LABELS

    def test_every_script_has_exactly_one_entry(self):
        self.assertEqual(set(self.labels), set(GlyphScript))
        self.assertEqual(len(self.labels), len(GlyphScript))

    def test_standard_comes_first(self):
        # The menu draws a separator after it.
        self.assertIs(next(iter(self.labels)), GlyphScript.STANDARD)

    def test_the_two_commodore_faces_are_adjacent(self):
        order = list(self.labels)
        self.assertEqual(order.index(GlyphScript.C64KEYS),
                         order.index(GlyphScript.C64) + 1)


if __name__ == "__main__":
    unittest.main()
