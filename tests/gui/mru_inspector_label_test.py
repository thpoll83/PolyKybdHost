"""The MRU inspector's modifier namer, and the one input that can wrap it.

Split out from the dialog because it is a pure function and the hazard it guards
is arithmetic, not visual: a NEGATIVE modifier slot indexes a Python list from
the END, so the wrong name is returned silently and looks entirely plausible.
"""
import unittest

from polyhost.device.keys import Modifier, MODIFIER_ANY
from polyhost.gui.mru_inspector_dialog import _MODIFIER_NAMES, _modifier_label


class ModifierLabelTest(unittest.TestCase):

    def test_a_real_variant_is_named(self):
        self.assertEqual(_modifier_label(Modifier.NO_MOD.value), "NO")
        self.assertEqual(_modifier_label(Modifier.CTRL.value), "CTRL")

    def test_MODIFIER_ANY_is_named_any_and_does_NOT_wrap(self):
        # ⚠️ The whole reason this function exists. `_MODIFIER_NAMES[-1]` is
        # GUI+CTRL+ALT+SHIFT, so the old `value < len(...)` check would label the
        # program mark — an image that is on EVERY variant — as the single most
        # specific chord on the board, with nothing failing anywhere.
        self.assertEqual(_modifier_label(MODIFIER_ANY), "any")
        self.assertNotEqual(_modifier_label(MODIFIER_ANY), _MODIFIER_NAMES[-1])

    def test_an_out_of_range_value_falls_back_to_its_number(self):
        self.assertEqual(_modifier_label(len(_MODIFIER_NAMES)),
                         str(len(_MODIFIER_NAMES)))

    def test_no_negative_value_can_ever_return_a_modifier_name(self):
        # A sweep rather than the one sentinel: any future negative marker gets
        # the same protection, and a `0 <=` that is deleted fails here.
        for value in range(-len(_MODIFIER_NAMES) - 2, 0):
            label = _modifier_label(value)
            if value == MODIFIER_ANY:
                self.assertEqual(label, "any")
            else:
                self.assertNotIn(label, _MODIFIER_NAMES, f"{value} wrapped")


if __name__ == "__main__":
    unittest.main()
