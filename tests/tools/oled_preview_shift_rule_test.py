"""How `oled_preview.shift_preview_rule` resolves, per `Lang`, without raising.

The rule that decides whether a Shift preview is redundant lives in the FIRMWARE
tree (`lang/shift_preview.py`) -- it is what cog turns into the keycap's own
`shift_preview_redundant` bitmap. So the host can reach it three different ways
and MUST behave sanely in all three:

* a `Lang` built from the workbook  -- import the module beside it;
* a `Lang` from the SHIPPED export  -- use the decision baked in at export time;
* a bare `Lang` with neither        -- keep every preview.

The third one is not hypothetical: `preview_data.lang_reader()` and
`KeycapPreview._load_shipped` both build their `Lang` with `object.__new__`, so
the attribute the first path reads is simply absent. Reading it unguarded raised
`AttributeError` from inside `render_key`, the caller's handler dropped that
keycap, and -- because the resolver had already written its module-global cache
-- every LATER preview silently lost its suppression too. Greptile caught it on
host#210; these tests pin both halves.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "tools"))

import oled_preview as op                         # noqa: E402


def _bare_lang(**attrs):
    """A `Lang` built the way the shipped path builds one: no `__init__`."""
    L = object.__new__(op.Lang)
    L.named = {}
    L.langs = []
    L.grid = {}
    for k, v in attrs.items():
        setattr(L, k, v)
    return L


class ShiftPreviewRuleTest(unittest.TestCase):

    def test_a_lang_with_no_workbook_does_not_raise(self):
        """The shipped `Lang` has no `xlsx` -- that must read as "no rule", not blow up."""
        L = _bare_lang()
        self.assertFalse(op.shift_preview_rule(L))

    def test_an_unresolvable_lang_does_not_poison_a_resolvable_one(self):
        """THE regression. The cache is per-`Lang`, never a module global.

        Two `Lang` objects legitimately disagree here, so whichever is asked first
        must not answer for the other. The old code assigned its global BEFORE the
        lookup that could fail, so one bare `Lang` turned suppression off process
        -wide -- and silently, since the preview simply drew more than the keyboard.
        """
        op.shift_preview_rule(_bare_lang())          # ask the one that cannot resolve

        baked = _bare_lang(shift_suppressed=[("a", "A")])
        rule = op.shift_preview_rule(baked)
        self.assertTrue(rule, "a Lang carrying the baked decision must still resolve")
        self.assertTrue(rule("a", "A"))

    def test_the_baked_decision_answers_the_same_call_as_the_module(self):
        L = _bare_lang(shift_suppressed=[("a", "A"), ("ä", "Ä")])
        rule = op.shift_preview_rule(L)
        self.assertTrue(rule("a", "A"))
        self.assertTrue(rule("ä", "Ä"))
        self.assertFalse(rule("1", "!"), "a real preview is not suppressed")
        self.assertFalse(rule(None, "A"), "an absent base is not the empty string")

    def test_cell_keys_normalise_the_json_round_trip(self):
        """openpyxl hands back an int for a bare numeric cell; JSON makes it a string.

        Both sides must normalise identically or the baked set never matches --
        which would fail OPEN (every preview kept), i.e. invisibly.
        """
        L = _bare_lang(shift_suppressed=[("1", "!")])
        rule = op.shift_preview_rule(L)
        self.assertTrue(rule(1, "!"), "an int cell must match its exported string")
        self.assertTrue(rule(" 1 ", "!"), "and surrounding whitespace must not matter")

    def test_the_rule_is_cached_on_the_lang(self):
        L = _bare_lang(shift_suppressed=[("a", "A")])
        self.assertIs(op.shift_preview_rule(L), op.shift_preview_rule(L))


if __name__ == "__main__":
    unittest.main()
