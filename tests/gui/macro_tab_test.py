"""MacroTab — the label meter, the keycap preview and the save path.

Runs under the offscreen Qt platform, so it exercises the real widget rather than a
description of it. What matters here is that the tab's two working widgets agree with
the firmware: the meter reports PIXELS (not characters) and the preview draws through
the same font the keycap does, so what the user sees while typing is what will be
drawn.
"""
import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.layout_dialog.macro_tab import MacroTab, QK_MACRO
    from polyhost.services import macro_label as ml
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e

HAVE_FONT = os.path.isfile(os.path.join(ml.default_font_dir(), "nano_font.h")) \
    if _IMPORT_ERR is None else False


def _core(macros=None, ok=True, payload=None):
    """A stand-in core answering macro_list/macro_set/macro_clear."""
    core = MagicMock()
    macros = macros if macros is not None else [
        {"id": 0, "label": "push", "bytes": 5, "text": "push", "steps": []},
        {"id": 1, "label": "", "bytes": 0, "text": "", "steps": []},
        {"id": 2, "label": "chord", "bytes": 9, "text": None,
         "steps": [{"kind": "down", "code": 0xE0}, {"kind": "tap", "code": 6}]},
    ]
    core.macro_list.return_value = (ok, payload if payload is not None else {
        "count": len(macros), "label_len": 12, "capacity": 2267, "used": 14,
        "macros": macros,
    })
    core.macro_set.return_value = (True, "ok")
    core.macro_clear.return_value = (True, "ok")
    return core


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class MacroTabTest(unittest.TestCase):
    def test_the_list_is_labelled_by_label_not_by_index(self):
        """Picking `push` rather than `M0` is the whole point of having labels."""
        tab = MacroTab(_core())
        tab.reload()
        self.assertEqual(tab.list.item(0).text(), "push")
        self.assertEqual(tab.list.item(1).text(), "M1 (empty)")

    def test_storage_bar_reports_the_shared_buffer(self):
        tab = MacroTab(_core())
        tab.reload()
        self.assertEqual(tab.storage.maximum(), 2267)
        self.assertEqual(tab.storage.value(), 14)

    def test_a_macro_that_is_not_text_locks_the_text_field(self):
        """Editing it as text and saving would silently drop the chords and delays."""
        tab = MacroTab(_core())
        tab.reload()
        tab.list.setCurrentRow(2)
        self.assertFalse(tab.text_edit.isEnabled())
        self.assertIn("not plain text", tab.body_note.text())

    def test_a_text_macro_is_editable(self):
        tab = MacroTab(_core())
        tab.reload()
        tab.list.setCurrentRow(0)
        self.assertTrue(tab.text_edit.isEnabled())
        self.assertEqual(tab.text_edit.text(), "push")

    def test_save_sends_label_and_text(self):
        core = _core()
        tab = MacroTab(core)
        tab.reload()
        tab.list.setCurrentRow(0)
        tab.label_edit.setText("shove")
        tab.text_edit.setText("git push")
        tab._on_save()
        core.macro_set.assert_called_with(0, label="shove", text="git push")

    def test_save_omits_the_body_when_it_is_not_editable(self):
        """A label-only edit must not re-stream a body the tab could not show."""
        core = _core()
        tab = MacroTab(core)
        tab.reload()
        tab.list.setCurrentRow(2)
        tab.label_edit.setText("renamed")
        tab._on_save()
        core.macro_set.assert_called_with(2, label="renamed")

    def test_assign_emits_the_macro_keycode(self):
        core = _core()
        tab = MacroTab(core)
        tab.reload()
        tab.list.setCurrentRow(2)
        seen = []
        tab.keycodeSelected.connect(lambda *a: seen.append(a))
        tab._on_assign()
        self.assertEqual(len(seen), 1)
        caption, name, keycode, _hint = seen[0]
        self.assertEqual(keycode, QK_MACRO + 2)
        self.assertEqual(name, "QK_MACRO_2")
        self.assertEqual(caption, "chord")   # by label, again

    def test_old_firmware_disables_the_tab_and_says_why(self):
        """macro_list fails with the device layer's "firmware too old" message, and
        that is what the user should read -- not an empty list that looks like a
        keyboard with no macros."""
        core = _core(ok=False, payload="Firmware protocol too old for macros (need v14+).")
        tab = MacroTab(core)
        tab.reload()
        self.assertFalse(tab.isEnabled())
        self.assertIn("too old", tab.body_note.text())


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
@unittest.skipUnless(HAVE_FONT, "firmware fonts not available")
class MacroTabPreviewTest(unittest.TestCase):
    def _tab(self):
        tab = MacroTab(_core())
        tab.reload()
        return tab

    def test_the_meter_is_in_pixels(self):
        tab = self._tab()
        tab.label_edit.setText("work mail")
        tab._repaint_preview()
        self.assertEqual(tab.width_meter.maximum(), ml.PANEL_W)
        self.assertEqual(tab.width_meter.value(), 48)     # measured, see macro_label_test
        self.assertIn("48 / 72 px", tab.width_meter.format())

    def test_an_overlong_label_is_flagged_rather_than_refused(self):
        """The label is still accepted -- it is just cut -- so the meter goes amber
        instead of the field rejecting the keystroke."""
        tab = self._tab()
        tab.label_edit.setText("WWWWWWWWW")
        tab._repaint_preview()
        self.assertGreater(ml.measure("WWWWWWWWW", tab._font), ml.PANEL_W)
        self.assertEqual(tab.width_meter.value(), ml.PANEL_W)   # clamped to the bar
        self.assertNotEqual(tab.width_meter.styleSheet(), "")   # amber

    def test_the_preview_actually_draws_something(self):
        tab = self._tab()
        tab.label_edit.setText("push")
        tab._repaint_preview()
        pm = tab.preview.pixmap()
        self.assertIsNotNone(pm)
        img = pm.toImage()
        lit = sum(1 for y in range(img.height()) for x in range(img.width())
                  if img.pixelColor(x, y).lightness() > 100)
        self.assertGreater(lit, 0, "the label preview rendered no lit pixels")

    def test_an_empty_label_previews_blank_rather_than_stale(self):
        tab = self._tab()
        tab.label_edit.setText("push")
        tab._repaint_preview()
        tab.label_edit.setText("")
        tab._repaint_preview()
        img = tab.preview.pixmap().toImage()
        lit = sum(1 for y in range(img.height()) for x in range(img.width())
                  if img.pixelColor(x, y).lightness() > 100)
        self.assertEqual(lit, 0)


@unittest.skipIf(_IMPORT_ERR, f"PyQt5/offscreen unavailable: {_IMPORT_ERR}")
class BrowserIntegrationTest(unittest.TestCase):
    """The tab has to reach the keycode browser, or none of the above is reachable."""

    def _browser(self, core=None):
        from polyhost.gui.layout_dialog.keycode_browser import KeycodeBrowser
        return KeycodeBrowser(core=core) if core is not None else KeycodeBrowser()

    def _titles(self, b):
        return [b.tabs.tabText(i) for i in range(b.tabs.count())]

    def test_the_macros_tab_is_added_when_a_core_is_available(self):
        b = self._browser(_core())
        self.assertIn("Macros", self._titles(b))

    def test_without_a_core_the_tab_is_absent_rather_than_broken(self):
        b = self._browser()
        self.assertNotIn("Macros", self._titles(b))
        self.assertIsNone(b.macro_tab)

    def test_the_existing_tabs_are_unchanged(self):
        """Adding a tab must not reorder the ones people already know."""
        before = self._titles(self._browser())
        after = self._titles(self._browser(_core()))
        self.assertEqual(after[:len(before)], before)

    def test_switching_to_the_tab_loads_it(self):
        """Loaded on first show, not in __init__: the list is three device round
        trips and most sessions never open the tab."""
        core = _core()
        b = self._browser(core)
        self.assertFalse(core.macro_list.called)
        b.tabs.setCurrentIndex(self._titles(b).index("Macros"))
        self.assertTrue(core.macro_list.called)


if __name__ == "__main__":
    unittest.main()
