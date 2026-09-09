"""The editor actually PAINTS the status panels, in the mode the header asks for.

⚠️ The reason this is a dialog-level test and not another renderer one: the renderer
was fine and the wiring was not. `_refresh_screens` swallows its exceptions (the board
is decoration and must never take the editor down), so a plain `AttributeError` in the
Real branch left the panels flat with nothing but a `log.debug` to say so. A test one
level down cannot see that; this one drives the real dialog.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
except ImportError as e:                      # pragma: no cover - PyQt5 not installed
    _IMPORT_ERR = e
else:
    _IMPORT_ERR = None
    from polyhost.gui.layout_dialog import board_plate as bp
    from polyhost.gui.layout_dialog import kb_layout_dialog as kb

_APP = None
LAYERS = ["Qwerty", "Fn", "Numpad", "Utility"]


def setUpModule():
    global _APP
    if _IMPORT_ERR is None:
        _APP = QApplication.instance() or QApplication([])


class _Core:
    """Enough of PolyCore for the dialog to build a board and four layers."""

    def keymap_layer_names(self):
        return True, list(LAYERS)

    def keymap_layer_count(self):
        return True, len(LAYERS)

    def keymap_buffer(self, *a, **k):
        return True, [0] * (8 * 10 * len(LAYERS))

    def keymap_default_layer(self):
        return True, 0

    def macro_list(self):
        return True, {"macros": [], "count": 0}

    def macro_set(self, *a, **k):
        return True, ""

    def macro_clear(self, *a, **k):
        return True, ""

    def keymap_set(self, *a, **k):
        return True, ""

    def subscribe(self, cb):
        return lambda: None


class _Settings:
    MATRIX_COLUMNS = 8
    MATRIX_ROWS = 10


@unittest.skipIf(_IMPORT_ERR is not None, "PyQt5 not installed")
class ScreenPaintingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dlg = kb.KbLayoutDialog(_Core(), _Settings())
        if not cls.dlg._board_items:
            raise unittest.SkipTest("no board outline shipped")
        if not cls.dlg._pixmaps_possible():
            raise unittest.SkipTest("the status faces are unavailable")

    def pixmaps(self):
        return [i.pixmap() for i in self.dlg._board_items
                if i.data(bp.SCREEN_SIDE) is not None]

    def test_SYMBOL_leaves_the_panels_flat(self):
        """Symbol means "no pictures"; a screen left over from the last mode is the
        stale-cache defect the keycaps drop their caches for."""
        self.dlg.set_keycap_mode(kb.KEYCAP_SYMBOL)
        self.dlg._refresh_screens(0)
        shots = self.pixmaps()
        self.assertTrue(shots)
        self.assertTrue(all(p.isNull() for p in shots))

    def test_PREVIEW_paints_a_panel_on_every_screen(self):
        self.dlg.set_keycap_mode(kb.KEYCAP_PREVIEW)
        self.dlg._refresh_screens(0)
        shots = self.pixmaps()
        self.assertTrue(shots)
        for p in shots:
            self.assertFalse(p.isNull(), "a status panel was not painted")
            self.assertEqual(p.width(), 128)

    def test_REAL_paints_the_SIMULATED_panel_not_the_flat_one(self):
        """The bug this file was written for. Width is what separates the two
        branches: Real renders at REAL_SCALE output pixels per OLED pixel, and the
        fail-soft `except` turns a broken Real branch back into the Preview image."""
        from polyhost.gui import oled_look
        if not oled_look.available():
            self.skipTest("Pillow unavailable")
        self.dlg.set_keycap_mode(kb.KEYCAP_REAL)
        self.dlg._refresh_screens(0)
        for p in self.pixmaps():
            self.assertFalse(p.isNull())
            self.assertEqual(p.width(), 128 * kb.ssr.REAL_SCALE)

    def test_the_panel_FOLLOWS_the_layer(self):
        """It names the layer being edited, so switching has to repaint it.

        ⚠️ Driven through `set_keycodes_for_layer`, which is what a layer change and
        a mode change both call -- NOT through `_refresh_screens` directly. Calling
        the repaint itself tests the renderer twice and says nothing about whether
        anything invokes it: deleting the call from `set_keycodes_for_layer` escaped
        that way before this test was rewritten.
        """
        self.dlg.set_keycap_mode(kb.KEYCAP_PREVIEW)
        self.dlg.set_keycodes_for_layer(0)
        first = [p.toImage() for p in self.pixmaps()]
        self.dlg.set_keycodes_for_layer(2)
        second = [p.toImage() for p in self.pixmaps()]
        self.assertTrue(any(a != b for a, b in zip(first, second)),
                        "the panels did not follow the layer")


if __name__ == "__main__":
    unittest.main()
