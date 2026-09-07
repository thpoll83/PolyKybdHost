"""The keycode browser's PolyKybd tab — the one route to assigning KC_AI.

Runs under the offscreen Qt platform so it builds the real widget. The bug pinned
here: QMK's header names `QK_KB_0`..`QK_KB_31`, the firmware uses 39 slots, so
`KC_AI` (0x7E26 = QK_KB_38) had no tile and could not be put on a key at all.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.layout_dialog.keycode_browser import KeycodeBrowser
    from polyhost.gui.layout_dialog.qmk_keycode_helper import (
        category_order, polykybd_category)
    from polyhost.services import custom_keycodes as ck
    # ⚠️ The BINDING is load-bearing, whatever a scanner says about the name never
    # being read: PyQt owns the C++ QApplication when it is constructed from Python,
    # so dropping the only reference collects it and the next QWidget ABORTS the
    # interpreter ("Must construct a QApplication before a QWidget", SIGABRT --
    # measured, not assumed). Nine sibling test files carry the same line.
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e

KC_AI = 0x7E26


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class PolyKybdTabTest(unittest.TestCase):
    def _tabs(self, b):
        return [b.tabs.tabText(i) for i in range(b.tabs.count())]

    def test_the_tab_exists(self):
        b = KeycodeBrowser()
        self.assertIn(polykybd_category(), self._tabs(b))

    def test_KC_AI_is_assignable(self):
        b = KeycodeBrowser()
        self.assertEqual(b.keycodes.get("KC_AI"), KC_AI)

    def test_the_slot_is_assignable_even_with_NO_names(self):
        """No export, no checkout: the tile is `QK_KB_38`, and it still places."""
        b = KeycodeBrowser(custom=ck.slots({}))
        self.assertEqual(b.keycodes.get("QK_KB_38"), KC_AI)

    def test_a_placed_key_reads_as_KC_AI_not_QK_KB_38(self):
        """`build_keycode_to_name` prefers a `KC_` name, which is what makes the
        editor label a placed key `AI` rather than `KB 38`."""
        b = KeycodeBrowser()
        self.assertEqual(b.codes_to_name.get(KC_AI), "KC_AI")
        self.assertEqual(b.codes_to_name.get(0x7E00), "KC_LANG")

    def test_the_block_appears_ONCE(self):
        """QMK's `QK_KB_0..31` must not survive beside PolyKybd's names for the
        same values -- that showed 96 tiles for 64 keys."""
        b = KeycodeBrowser()
        block = [v for v in b.keycodes.values()
                 if ck.QK_KB_FIRST <= v <= ck.QK_KB_LAST]
        self.assertEqual(len(block), len(set(block)))
        self.assertEqual(len(block), 64)

    def test_the_tab_is_APPENDED_and_reorders_nothing(self):
        """Tabs are muscle memory. Same invariant as the tray's developer submenu."""
        order = category_order()
        self.assertEqual(order[-1], polykybd_category())
        self.assertEqual(order[:-1], [
            "Standard", "Additional", "Modifiers", "Media / System", "RGB",
            "Unicode / International", "Mouse / Joystick", "Midi", "Haptic",
            "Magic", "User / Macro", "Programmable", "Space Cadet", "Quantum"])

    def test_the_keys_are_ON_the_polykybd_tab(self):
        """Asserted POSITIVELY, and that matters: an earlier version only checked
        they were absent from "User / Macro", which passes vacuously once QMK's
        placeholders are dropped -- so it could not catch routing them by NAME
        (`categorize` puts `KC_AI` in "Additional"), the bug it was written for."""
        b = KeycodeBrowser()
        tabs = self._tabs(b)
        lay = b.tabs.widget(tabs.index(polykybd_category())).widget().layout()
        labels = {lay.itemAt(n).widget().text() for n in range(lay.count())}
        self.assertIn("AI", labels)
        self.assertIn("LANG", labels)
        self.assertEqual(lay.count(), 64)


if __name__ == "__main__":
    unittest.main()
