"""The composer must write back exactly what it loaded.

Loading a key into the composer and pressing Apply without touching a control
is the one interaction that must be a no-op. It was not: `load_from_keycode`
tested the decoded inner key for truthiness, so an inner key of **KC_NO (0)**
left the combo on its `KC_A` default and Apply wrote a different keycode to the
editor buffer and the device.

That is not an exotic input -- QMK's `Hyper` is `LCTL|LSFT|LALT|LGUI` over
KC_NO and `Meh` is the same without GUI, so both are mod-combos whose inner key
is legitimately zero, as is a bare held modifier like `LCTL(KC_NO)`.

Needs a display: skipped without one (see CLAUDE.md on running the GUI tests
under xvfb with QT_QPA_PLATFORM=offscreen).
"""
import os
import unittest

if not os.environ.get("DISPLAY"):
    raise unittest.SkipTest("GUI test needs an X display")

from PyQt5.QtWidgets import QApplication

from polyhost.gui.layout_dialog.keycode_composer import KeycodeComposer, BEHAVIORS
from polyhost.gui.layout_dialog.qmk_keycode_helper import (
    HEADER_FILE, parse_qmk_keycodes, decode_for_composer)

_app = QApplication.instance() or QApplication([])


def _composer():
    return KeycodeComposer(parse_qmk_keycodes(HEADER_FILE))


class TestComposerRoundTrip(unittest.TestCase):
    def setUp(self):
        self.c = _composer()

    def _round_trip(self, value):
        self.assertTrue(self.c.load_from_keycode(value), f"{value:#06x} not composable")
        return self.c._encode()

    def test_hyper_and_meh_survive_a_load_and_apply(self):
        for value, name in ((0x0F00, "Hyper"), (0x0700, "Meh")):
            with self.subTest(name):
                self.assertEqual(self._round_trip(value), value)

    def test_a_bare_held_modifier_survives_too(self):
        # The same defect, and NOT limited to the two named stacks: any mod combo
        # over KC_NO was rewritten with KC_A as its inner key.
        self.assertEqual(self._round_trip(0x0100), 0x0100)

    def test_a_mod_combo_WITH_an_inner_key_is_unaffected(self):
        self.assertEqual(self._round_trip(0x0104), 0x0104)

    def test_every_zero_inner_mod_mask_round_trips(self):
        """Sweep the class rather than the three cases found by hand.

        Masks whose low nibble is 0 are skipped: bit 4 only selects the RIGHT
        hand, so 0x10 is "right side of no modifier". `encode_mods` collapses
        that to 0 and `_encode` then correctly refuses to build a keycode, so it
        is not a representable value to round-trip.
        """
        for mods in range(1, 0x20):
            if not mods & 0x0F:
                continue
            value = (mods << 8)
            with self.subTest(mods=f"{mods:#04x}"):
                self.assertEqual(self._round_trip(value), value)

    def test_loading_a_layer_behaviour_does_not_disturb_the_inner_combo(self):
        """MO/TO/TG decode inner as 0 but ignore it -- the combo must not be
        yanked to NO, or switching to MT afterwards starts from the wrong key."""
        c = self.c
        before = c.inner_combo.currentData()
        c.load_from_keycode(0x5221)          # MO(1)
        self.assertEqual(c.inner_combo.currentData(), before)

    def test_the_other_composable_behaviours_still_round_trip(self):
        for value, name in ((0x2304, "MT"), (0x4104, "LT"), (0x5221, "MO"),
                            (0x5241, "DF"), (0x52A2, "OSM")):
            with self.subTest(name):
                self.assertEqual(self._round_trip(value), value)

    def test_decode_reports_the_zero_inner_key_it_always_did(self):
        """The decode side was already correct -- the loss was in the widget."""
        self.assertEqual(decode_for_composer(0x0F00), ("MOD", 0, 0x0F, 0x00))


if __name__ == "__main__":
    unittest.main()
