"""A macro key in the keymap editor draws its real keycap.

Without this a row of macro keys reads `MACRO(0)`, `MACRO(1)`, `MACRO(2)` -- sixteen
tiles that say "this is a macro" and nothing about WHICH one, which is the exact
problem the on-keycap caption exists to solve. The editor now paints the same 72x40
picture the Macros tab previews and the firmware draws.

The invariant worth pinning is that the two surfaces AGREE: they compose through one
renderer (`macro_keycap_render`), extracted from the tab so a second caller exists at
all, and a divergence would mean the editor promising a keycap the keyboard will not
draw.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.device.device_settings import DeviceSettings
    from polyhost.gui.layout_dialog.kb_layout_dialog import KbLayoutDialog
    from polyhost.gui.layout_dialog.macro_tab import MacroTab, QK_MACRO
    from polyhost.services import macro_label as ml
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e

HAVE_FONT = os.path.isfile(os.path.join(ml.default_font_dir(), "nano_font.h")) \
    if _IMPORT_ERR is None else False

MACROS = [
    {"id": 0, "label": "push", "style": 0, "icon": 0, "steps": [], "text": "", "bytes": 9},
    {"id": 1, "label": "work mail", "style": 1, "icon": 0x1F4E7, "steps": [], "text": "",
     "bytes": 20},
]


def setUpModule():
    """Pin the QApplication for the life of the module -- see macro_tab_test."""
    if _IMPORT_ERR is None:
        assert _APP is not None


class FakeCore:
    """Only what KbLayoutDialog reads. `macros` is mutable so a test can edit one."""

    def __init__(self, macros=None):
        self.macros = [dict(m) for m in (macros if macros is not None else MACROS)]
        self.writes = []

    def keymap_layer_names(self):
        return True, ["Qwerty", "Fn"]

    def keymap_layer_count(self):
        return True, 2

    def keymap_default_layer(self):
        return True, 0

    def macro_list(self):
        return True, {"macros": self.macros, "capacity": 2000, "used": 63,
                      "label_len": 12}

    def keymap_set(self, layer, row, col, keycode):
        self.writes.append((layer, row, col, keycode))
        return True, ""

    def keymap_buffer(self):
        s = DeviceSettings()
        return True, [0x0004] * (12 * s.MATRIX_ROWS * s.MATRIX_COLUMNS)


def _editor(core=None):
    return KbLayoutDialog(core or FakeCore(), DeviceSettings())


class EightLayerCore(FakeCore):
    """A realistic layer count -- the default fake has two, which is few enough to
    fit any header width and would hide the wrapping bug below."""

    def keymap_layer_count(self):
        return True, 8

    def keymap_layer_names(self):
        return True, ["Qwerty", "Stag!", "ColemkDH", "Neo", "Wkmn", "Fn", "Numpad",
                      "Utility"]


def _assign(dlg, idx, keycode):
    """Put a keycode on one key the way the editor's own load path does."""
    dlg.key_buffer[idx] = keycode
    dlg.set_keycodes_for_layer(0)


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
@unittest.skipUnless(HAVE_FONT, "keycap fonts not present")
class MacroKeycapInEditorTest(unittest.TestCase):

    def test_a_macro_key_draws_a_keycap_and_an_ordinary_key_does_not(self):
        dlg = _editor()
        first = sorted(dlg.keys)[0]
        _assign(dlg, first, QK_MACRO + 0)
        self.assertIsNotNone(dlg.keys[first]._keycap)
        second = sorted(dlg.keys)[1]
        self.assertIsNone(dlg.keys[second]._keycap)

    def test_the_keycap_hides_the_keycode_text(self):
        """The caption is already IN the picture; `MACRO(0)` drawn over it is both
        redundant and unreadable at tile size."""
        dlg = _editor()
        first = sorted(dlg.keys)[0]
        _assign(dlg, first, QK_MACRO + 0)
        self.assertFalse(dlg.keys[first].text.isVisible())

    def test_reassigning_away_from_a_macro_CLEARS_the_keycap(self):
        """The failure this guards: a key that stops being a macro keeps the old
        picture, so the tile shows a macro that is no longer on it."""
        dlg = _editor()
        first = sorted(dlg.keys)[0]
        _assign(dlg, first, QK_MACRO + 0)
        self.assertIsNotNone(dlg.keys[first]._keycap)
        _assign(dlg, first, 0x0004)                  # KC_A
        self.assertIsNone(dlg.keys[first]._keycap)
        self.assertTrue(dlg.keys[first].text.isVisible())

    def test_a_macro_id_the_keyboard_does_not_have_draws_nothing(self):
        """QMK's range is 0x7700..0x777F but the firmware ships 16 and this fake has
        two -- an id past the end has no macro to draw, and must not index off it."""
        dlg = _editor()
        self.assertIsNone(dlg._macro_index(QK_MACRO + 9))
        first = sorted(dlg.keys)[0]
        _assign(dlg, first, QK_MACRO + 9)
        self.assertIsNone(dlg.keys[first]._keycap)

    def test_the_keycap_is_cached_per_macro(self):
        """`set_keycodes_for_layer` runs over every key on every layer switch, so
        re-composing a keycap glyph-by-glyph per key per switch is real work for a
        picture that only changes when the macro does."""
        dlg = _editor()
        one = dlg._keycap_for(QK_MACRO + 0)
        two = dlg._keycap_for(QK_MACRO + 0)
        self.assertIs(one, two)

    def test_editing_a_macro_repaints_the_key(self):
        """The editor renders from its OWN copy of the list, so without the refresh a
        caption edit shows on the tab's preview and on the keyboard while the tile
        keeps the picture it drew when the dialog opened."""
        core = FakeCore()
        dlg = _editor(core)
        first = sorted(dlg.keys)[0]
        _assign(dlg, first, QK_MACRO + 0)
        before = dlg.keys[first]._keycap.toImage()
        core.macros[0]["label"] = "deploy"
        dlg.refresh_macro_keycaps()
        after = dlg.keys[first]._keycap.toImage()
        self.assertNotEqual(before, after)

    def test_the_editor_and_the_macros_tab_draw_the_SAME_keycap(self):
        """One renderer, two surfaces. A divergence would have the editor promise a
        keycap the keyboard will not draw -- and it would be invisible in review,
        since both sides look plausible on their own.
        """
        core = FakeCore()
        dlg = _editor(core)
        tab = MacroTab(core)
        tab.reload()
        for i, m in enumerate(core.macros):
            with self.subTest(macro=i):
                tab._current = i
                tab._icon = m["icon"]
                box = tab.style_box
                box.setCurrentIndex([box.itemData(n) for n in range(box.count())]
                                    .index(m["style"]))
                from_tab = tab._keycap.render(m["label"], m["style"],
                                              icon=m["icon"], index=m["id"])
                from_editor = dlg._keycap_render.render(m["label"], m["style"],
                                                        icon=m["icon"], index=m["id"])
                self.assertEqual(from_tab, from_editor)

    def test_the_toggle_turns_the_keycaps_off_and_back_on(self):
        """Off is not "blank": the key falls back to the keycode text it had before
        keycaps existed, so the editor is never less usable with the box unticked."""
        dlg = _editor()
        first = sorted(dlg.keys)[0]
        _assign(dlg, first, QK_MACRO + 0)
        self.assertIsNotNone(dlg.keys[first]._keycap)

        # Nothing else redraws here: the toggle has to repaint the CURRENT layer
        # itself, or it reads as a dead switch until the next layer change.
        dlg.keycap_toggle.setChecked(False)
        self.assertIsNone(dlg.keys[first]._keycap)
        self.assertTrue(dlg.keys[first].text.isVisible())

        dlg.keycap_toggle.setChecked(True)
        self.assertIsNotNone(dlg.keys[first]._keycap)

    def test_a_macro_tile_falls_back_to_M0_not_to_MACRO_0(self):
        """`MACRO(0)` is the right name in the browser and too long for a tile: the
        label is centred and unclipped, so it overflows and the neighbouring keys
        paint over its head -- what you actually read is a bare `0`, i.e. a digit.
        `M0` is what the keyboard draws as its own fallback mark, and it fits.
        """
        dlg = _editor()
        first = sorted(dlg.keys)[0]
        dlg.keycap_toggle.setChecked(False)
        _assign(dlg, first, QK_MACRO + 0)
        self.assertEqual(dlg.keys[first].text.document().toPlainText(), "M0")

    def test_a_macro_id_past_the_end_is_still_named_as_a_macro(self):
        """It has no keycap to draw, but it is not a digit key either -- and the
        overflow that makes the short name necessary does not care whether the
        keyboard has that macro."""
        dlg = _editor()
        first = sorted(dlg.keys)[0]
        _assign(dlg, first, QK_MACRO + 9)
        self.assertEqual(dlg.keys[first].text.document().toPlainText(), "M9")

    def test_every_layer_button_stays_VISIBLE_beside_the_toggle(self):
        """The toggle shares the header with the layer buttons, and squeezing them is
        SILENT: `ButtonArray` holds a FlowLayout and is capped at 40 px high, so a
        header that takes its width wraps each layer onto its own row and the cap
        hides all but the first. Eight layers then render as one, with nothing
        clipped-looking to give it away (field, 2026-08-28 -- "I can only see one
        layer ... there should be 8").

        Asserted on geometry rather than on the widget tree: every button exists and
        reports `isVisible()` either way, which is exactly why this was invisible to
        the rest of the suite.
        """
        dlg = KbLayoutDialog(EightLayerCore(), DeviceSettings())
        dlg.resize(1800, 1000)
        dlg.show()
        _APP.processEvents()

        buttons = dlg.layers.group.buttons()
        self.assertEqual(len(buttons), 8)
        height = dlg.layers.height()
        hidden = [b.text() for b in buttons if b.geometry().bottom() >= height]
        self.assertEqual(hidden, [], f"layer buttons pushed out of the header: {hidden}")

        rows = {b.geometry().y() for b in buttons}
        self.assertEqual(len(rows), 1, "the layer buttons wrapped onto several rows")

    def test_the_toggle_still_sits_to_the_RIGHT_of_the_layers(self):
        """The fix is a stretch FACTOR on the ButtonArray, not a spacer between the
        two -- so this pins the placement the spacer was there for."""
        dlg = KbLayoutDialog(EightLayerCore(), DeviceSettings())
        dlg.resize(1800, 1000)
        dlg.show()
        _APP.processEvents()
        last = max(b.mapTo(dlg, b.rect().topRight()).x() for b in dlg.layers.group.buttons())
        toggle_x = dlg.keycap_toggle.mapTo(dlg, dlg.keycap_toggle.rect().topLeft()).x()
        self.assertGreater(toggle_x, last)

    def test_the_toggle_is_ON_by_default_when_the_fonts_are_there(self):
        self.assertTrue(_editor().keycap_toggle.isChecked())


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class NoFontTest(unittest.TestCase):
    def test_a_missing_font_pack_costs_only_the_picture(self):
        """The editor must still edit keymaps on a machine with no font headers --
        `usable` goes False and every key falls back to its keycode text."""
        dlg = _editor()
        dlg._keycap_render = None
        self.assertIsNone(dlg._keycap_for(QK_MACRO + 0))

    def test_the_toggle_is_DISABLED_rather_than_silently_inert(self):
        """A tickable box that draws nothing is worse than a greyed-out one: the
        tooltip is the only place that can say the fonts are missing."""
        dlg = KbLayoutDialog.__new__(KbLayoutDialog)
        dlg._keycap_render = None
        dlg._show_keycaps = True
        box = KbLayoutDialog._build_keycap_toggle(dlg)
        self.assertFalse(box.isEnabled())
        self.assertFalse(box.isChecked())
        self.assertIn("MACRO(n)", box.toolTip())


if __name__ == "__main__":
    unittest.main()
