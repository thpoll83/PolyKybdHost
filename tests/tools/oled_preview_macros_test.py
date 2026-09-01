"""`oled_preview`'s C-macro reader — the legend text before anything renders it.

⚠️ These moved here from `tests/gui/` with the functions themselves: they expand the
macros `named_glyphs.h` defines, so they belong beside the glyph loader that reads
that file — which needs them too, to resolve an object macro whose body calls one.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "tools"))
from oled_preview import (                                       # noqa: E402
    expand_function_macros,
    parse_function_macros,
)


class ParseFunctionMacrosTest(unittest.TestCase):
    def test_a_line_continuation_is_stripped_from_the_body(self):
        """⚠️ A C continuation is ONE backslash.

        The pattern here asked for two, so it never matched: every multi-line legend
        macro kept a literal `\\` at the front of its body, and that resolves to a
        real glyph -- the five settings keycaps drew a backslash before their label.
        """
        m = parse_function_macros('#define LBL(l, v) \\\n    MID(l, v)\n')
        self.assertEqual(m["LBL"], (["l", "v"], "MID(l, v)"))

    def test_several_continuations_leave_no_backslash_behind(self):
        # Whitespace around the join is incidental (a C preprocessor leaves some too);
        # what matters is that no continuation survives into the display list.
        m = parse_function_macros('#define A(x) \\\n  U"a" \\\n  x\n')
        self.assertNotIn("\\", m["A"][1])
        self.assertEqual(m["A"][1].split(), ['U"a"', "x"])

    def test_escapes_inside_a_literal_survive(self):
        """The sibling trap: a blanket backslash strip turns `U"\\f\\f"` into `U" f f"`,
        and the legend renders the letter f instead of nudging the cursor."""
        m = parse_function_macros('#define A(x) \\\n    U"\\f\\f\\f" x\n')
        self.assertEqual(m["A"][1], 'U"\\f\\f\\f" x')

    def test_a_single_line_macro_is_unchanged(self):
        m = parse_function_macros('#define A(x) U"z" x\n')
        self.assertEqual(m["A"], (["x"], 'U"z" x'))

    def test_expansion_reaches_the_literals_through_a_wrapper(self):
        macros = parse_function_macros(
            '#define OUTER(l, v) \\\n    INNER(l, v)\n'
            '#define INNER(top, bottom) \\\n    U"\\x16" U"\\f" U##top U"\\r" U##bottom\n')
        got = expand_function_macros('OUTER("IDLE:", "Pulse")', macros)
        self.assertNotIn("\\\n", got)
        self.assertFalse(got.lstrip().startswith("\\"))
        self.assertIn('U"IDLE:"', got)
        self.assertIn('U"Pulse"', got)


if __name__ == "__main__":
    unittest.main()
