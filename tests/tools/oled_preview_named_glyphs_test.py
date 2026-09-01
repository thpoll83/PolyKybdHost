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


@unittest.skipIf(TOOLS_ERR, TOOLS_ERR)
class TruncatedBodyTest(unittest.TestCase):
    """⚠️ The loader kept only the FIRST literal of a multi-token `#define`.

    Worse than not matching at all: a truncated legend still renders, so it reads
    as correct-but-incomplete rather than as missing, and nothing anywhere says a
    body was dropped. Three keycaps shipped that way and two were reported from the
    field (2026-09-01) — the Context-menu key drew NOTHING because
    `ICON_CONTEXT_MENU` collapsed to `U" "`, and Scroll Lock drew "Scr" with its
    lock badge gone. `ICON_PAUSE_TEXT` was truncated to a bare cursor op and nobody
    had noticed yet.
    """

    def _named(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            h = pathlib.Path(tmp) / "named_glyphs.h"
            h.write_text(text, encoding="utf-8")
            return op.load_named_glyphs(str(h))

    def test_every_literal_of_a_body_survives_not_just_the_first(self):
        n = self._named('#define A_TWO  U"\\x41" U"\\x42"\n')
        self.assertEqual(n.get("A_TWO"), [0x41, 0x42])

    def test_a_position_constant_keeps_BOTH_coordinates(self):
        """⚠️ The quiet half of the same bug: six `HINT_POS_*` / `HINT_SZ_*`
        constants are a coordinate PAIR, and truncation dropped the y. Anything
        MOVE'ing by one would have landed at a wrong place rather than not at all."""
        n = self._named('#define HINT_POS_X  U"\\x48" U"\\x06"\n')
        self.assertEqual(n.get("HINT_POS_X"), [0x48, 0x06])

    def test_a_line_continuation_does_not_end_the_body(self):
        """Most of the interesting legends are multi-line, so a body that stopped
        at the backslash would be truncated for exactly the macros that matter."""
        n = self._named('#define B_ONE U"\\x41"\n'
                        '#define A_SEQ  U"\\x42" \\\n'
                        '               B_ONE\n')
        self.assertEqual(n.get("A_SEQ"), [0x42, 0x41])

    def test_a_function_like_call_inside_a_body_is_expanded(self):
        """`ICON_CONTEXT_MENU` is literals + `HINT_MOVE(...)` + `HINT_ROT(...)`, so
        a loader that could not expand a call could not resolve it at all."""
        n = self._named('#define HINT_MOVE(p) U"\\x0E" p\n'
                        '#define POS_A U"\\x42" U"\\x0C"\n'
                        '#define ICON_X  U"\\x41" HINT_MOVE(POS_A)\n')
        self.assertEqual(n.get("ICON_X"), [0x41, 0x0E, 0x42, 0x0C])

    def test_an_argument_carrying_a_C_ESCAPE_does_not_crash_the_load(self):
        """⚠️ `re.sub` reads a string replacement as a TEMPLATE, so expanding
        `HINT_MOVE(HINT_POS_CTXPTR)` -> `U"\\x42" U"\\x0C"` raised `bad escape \\x`
        and took the ENTIRE glyph table down with it. Harmless while this only
        expanded the settings labels ("IDLE:", "Pulse"), which is why it surfaced
        only when the glyph macros started coming through the same expander."""
        n = self._named('#define M(p) U"\\x0E" p\n'
                        '#define P U"\\x42" U"\\x0C"\n'
                        '#define ICON_Y  M(P)\n')
        self.assertEqual(n.get("ICON_Y"), [0x0E, 0x42, 0x0C])
