"""`oled_preview.load_named_glyphs` and the guard against drawing a macro NAME.

⚠️ A legend nobody can resolve draws its own name as text, and it shipped.
`resolve_token` falls back to parsing an unknown token as the body of an implicit
`U"..."` -- right for a bare LUT cell, wrong for a macro name. So the mute key drew
the literal word `ICON_MUTE` and the media-stop key drew `ICON_MEDIA_STOP`, on the
board's own preview, with nothing anywhere to say so: the legend resolves, the
renderer supports every op in it, and the picture is a line of capitals. Found
2026-09-01 while checking what the shipped preview export actually contained.

Two halves, and they are separate fixes: EXPAND the multi-token macros that can be
expanded (`#define A  B U"x" C`, which the single-literal pattern skipped entirely),
and REFUSE the ones that cannot (a body of function-like calls).
"""
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "tools"))
try:
    import oled_preview as op
    TOOLS_ERR = ""
except Exception as exc:                              # pragma: no cover - env gate
    op = None
    TOOLS_ERR = f"oled_preview unavailable: {type(exc).__name__}: {exc}"


@unittest.skipIf(TOOLS_ERR, TOOLS_ERR)
class UnresolvedMacroTest(unittest.TestCase):
    """See the module docstring: the two halves of the macro-name defect."""

    def _lang(self, named):
        L = object.__new__(op.Lang)
        L.named = named
        return L

    def test_a_multi_token_macro_is_expanded_not_drawn_as_its_name(self):
        """`#define A  B U"x" C` -- the single-literal pattern skips it entirely."""
        with tempfile.TemporaryDirectory() as tmp:
            h = pathlib.Path(tmp) / "named_glyphs.h"
            h.write_text('#define P_MUTE U"\\x1F568"\n'
                         '#define X_MARK U"\\x1F5D9"\n'
                         '#define I_MUTE  P_MUTE U"\\f" X_MARK\n', encoding="utf-8")
            named = op.load_named_glyphs(str(h))
        self.assertEqual(named.get("I_MUTE"), [0x1F568, 0x0C, 0x1F5D9])

    def test_a_forward_reference_still_resolves(self):
        """Order in the header must not decide it -- the pieces are collected first
        and expanded afterwards."""
        with tempfile.TemporaryDirectory() as tmp:
            h = pathlib.Path(tmp) / "named_glyphs.h"
            h.write_text('#define A_SEQ  B_ONE U"!" C_TWO\n'
                         '#define B_ONE U"\\x41"\n'
                         '#define C_TWO U"\\x42"\n', encoding="utf-8")
            named = op.load_named_glyphs(str(h))
        self.assertEqual(named.get("A_SEQ"), [0x41, ord("!"), 0x42])

    def test_a_macro_with_no_glyphs_is_REPORTED_not_silently_drawn(self):
        """The general guard: refusing is honest, drawing capitals is not."""
        L = self._lang({"ICON_LEFT": [0x8C]})
        self.assertEqual(L.unresolved_tokens("ICON_MEDIA_STOP"), ["ICON_MEDIA_STOP"])
        self.assertEqual(L.unresolved_tokens("ICON_LEFT"), [])

    def test_ordinary_legend_content_is_never_reported(self):
        """⚠️ A false positive here REFUSES a legend that draws perfectly, so the
        test that matters is the one that must stay silent: literals, lowercase
        text, digits and a single capital are all real legend content."""
        L = self._lang({})
        for val in ('U"abc"', 'u"\\f\\f"', "a", "Q", "42", None, "", 7,
                    'U"A" U"B"'):
            self.assertEqual(L.unresolved_tokens(val), [], repr(val))

    def test_a_setting_cell_is_NOT_asked(self):
        """`HIDE` is a legitimate setting value and looks exactly like an
        unresolved macro. Setting cells go through `get_setting`, which never
        consults this -- pinned so nobody wires it into the LUT path."""
        L = self._lang({})
        self.assertEqual(L.unresolved_tokens("HIDE"), ["HIDE"])
        self.assertEqual(op.get_setting(self._grid_lang("HIDE"), 1, 0, 0), op.HIDE)

    def _grid_lang(self, value):
        L = object.__new__(op.Lang)
        L.named, L.langs, L.grid = {}, ["en-US"], {(1, 2): value}
        return L
