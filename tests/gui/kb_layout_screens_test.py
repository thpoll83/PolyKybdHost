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

    def __init__(self, default_layer=0, buffer_ok=True):
        self._default, self._buffer_ok = default_layer, buffer_ok

    def keymap_layer_names(self):
        return True, list(LAYERS)

    def keymap_layer_count(self):
        return True, len(LAYERS)

    def keymap_buffer(self, *a, **k):
        if not self._buffer_ok:
            return False, None
        return True, [0] * (8 * 10 * len(LAYERS))

    def keymap_default_layer(self):
        return True, self._default

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

    def _which_layer(self, dlg, side="left"):
        """Which layer the `side` panel is drawing, by comparing it to each.

        Rendering the candidates rather than reading a label back: the panel is a
        picture, and the only claim worth making about it is that it is the picture
        that layer produces.
        """
        from polyhost.gui.layout_dialog import status_screen_render as ssr

        def lit(img):
            return {(x, y) for y in range(img.height()) for x in range(img.width())
                    if img.pixel(x, y) != ssr.GROUND.rgb()}

        for item in dlg._board_items:
            if item.data(bp.SCREEN_SIDE) != side:
                continue
            pm = item.pixmap()
            if pm.isNull():
                return "BLANK"
            got = lit(pm.toImage())
            r = ssr.StatusScreenRenderer(dlg._preview.status_faces())
            for n in range(len(LAYERS)):
                if lit(r.render(side, n, dlg._layer_name(n))) == got:
                    return n
            return "NONE"
        return "NO PANEL"

    def _dialog(self, **kw):
        dlg = kb.KbLayoutDialog(_Core(**kw), _Settings())
        if not dlg._board_items:
            self.skipTest("no board outline shipped")
        if not dlg._pixmaps_possible():
            self.skipTest("the status faces are unavailable")
        dlg.set_keycap_mode(kb.KEYCAP_PREVIEW)
        return dlg

    def test_the_panels_open_on_the_KEYBOARDS_default_layer(self):
        """Turning previews on shows the layer the KEYBOARD is on, not layer 0.

        ⚠️ It does NOT pin the startup paint, and saying so was the first draft's
        mistake. `_add_board` really does draw the panels before the default layer is
        read, but the default mode is Symbol -- so the panels are blank until the user
        picks Preview, and that pick repaints at `current_layer` anyway. Measured:
        deleting the startup `set_keycodes_for_layer` entirely leaves this green. What
        that mutation really breaks is the KEYS, which show layer 0's keycodes until
        something else refreshes them; that belongs to a keycap test, not here.
        """
        for default in (0, 2, 3):
            dlg = self._dialog(default_layer=default)
            for side in ("left", "right"):
                with self.subTest(default=default, side=side):
                    self.assertEqual(self._which_layer(dlg, side), default)

    def test_a_MODE_change_keeps_the_layer_rather_than_reverting_it(self):
        """The bug this pair exists for: `current_layer` was written ONLY by the
        button handler, so calling `set_keycodes_for_layer` directly left the two
        disagreeing -- and the next mode switch repainted `current_layer`, silently
        putting the board and both panels back on the last CLICKED layer.

        Driven through `set_keycodes_for_layer`, deliberately: going through the
        button would set `current_layer` on the way past and hide exactly this.
        """
        dlg = self._dialog()
        dlg.set_keycodes_for_layer(3)
        self.assertEqual(dlg.current_layer, 3, "the shown layer was not adopted")
        for mode in (kb.KEYCAP_SYMBOL, kb.KEYCAP_PREVIEW):
            dlg.set_keycap_mode(mode)
        for side in ("left", "right"):
            with self.subTest(side=side):
                self.assertEqual(self._which_layer(dlg, side), 3)

    def test_the_panels_follow_the_mode_with_NO_KEY_BUFFER(self):
        """A failed keymap read locks the keys down, and the panels used to go with
        them -- the mode switch's repaint sat inside that guard. They carry the
        LAYER, not the keymap, so a board that cannot be edited still says which
        layer is selected."""
        dlg = kb.KbLayoutDialog(_Core(buffer_ok=False), _Settings())
        if not dlg._board_items or not dlg._pixmaps_possible():
            self.skipTest("no board outline / status faces")
        self.assertIsNone(dlg.key_buffer)
        dlg.set_keycap_mode(kb.KEYCAP_PREVIEW)
        for side in ("left", "right"):
            with self.subTest(side=side):
                self.assertEqual(self._which_layer(dlg, side), 0)

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
