"""MacroTab — the label meter, the keycap preview and the save path.

Runs under the offscreen Qt platform, so it exercises the real widget rather than a
description of it. What matters here is that the tab's two working widgets agree with
the firmware: the meter reports PIXELS (not characters) and the preview draws through
the same font the keycap does, so what the user sees while typing is what will be
drawn.
"""
import os
import unittest
from unittest import mock
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QScrollArea
    from PyQt5.QtGui import QImage
    from polyhost.gui.layout_dialog.macro_tab import MacroTab, QK_MACRO
    from polyhost.services import macro_body
    from polyhost.services import macro_label as ml
    from polyhost.services import macro_look as mk
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e

HAVE_FONT = os.path.isfile(os.path.join(ml.default_font_dir(), "nano_font.h")) \
    if _IMPORT_ERR is None else False


def setUpModule():
    """Pin the QApplication reference for the life of the module.

    `_APP` looks unused -- it is not. Qt requires exactly one QApplication and it
    must outlive every widget; letting it be garbage-collected takes the Qt runtime
    with it and the next widget construction segfaults. Asserting it here is what
    says so, to a reader and to a static analyser alike.
    """
    if _IMPORT_ERR is None:
        assert _APP is not None


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

    def test_the_body_note_carries_the_size_and_the_caveat_on_one_line(self):
        """They describe the same thing and the caveat wrapped to two rows on its own,
        in a column the browser already under-allocates. One label, one row."""
        tab = MacroTab(_core())
        tab.reload()
        note = tab.body_note.text()
        self.assertIn("5 bytes", note)
        self.assertIn("unencrypted", note)

    def test_a_macro_that_is_not_text_summarises_rather_than_lying(self):
        """Editing a chord as text and saving would silently drop the chords and
        delays, so the field turns into a read-only summary and the step editor is the
        way in.

        Read-only rather than DISABLED: a disabled field reads as "this macro cannot be
        edited", when the truth is "not here". It said exactly that until the step
        editor existed, and the note used to admit that nothing could write one.
        """
        tab = MacroTab(_core())
        tab.reload()
        tab.list.setCurrentRow(2)
        self.assertTrue(tab.text_edit.isReadOnly())
        self.assertTrue(tab.text_edit.isEnabled())
        self.assertTrue(tab.steps_btn.isEnabled())
        self.assertEqual(tab.text_edit.text(), "Ctrl+C")   # the summary, not the bytes
        self.assertIn("Steps", tab.body_note.text())

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
        core.macro_set.assert_called_with(0, label="shove", text="git push",
                                          style=0, icon=0)

    def test_a_label_only_edit_sends_no_body_at_all(self):
        """`macro_set` rewrites the whole shared buffer to place one body, so re-sending
        an unchanged one costs every other macro a rewrite for nothing.

        Asserted for BOTH modes: the step macro is the case that used to be impossible
        to send, and the text macro is the case that used to be sent every single time
        -- which quietly defeated the core's own look-only fast path.
        """
        core = _core()
        tab = MacroTab(core)
        tab.reload()

        tab.list.setCurrentRow(2)              # a chord: body is steps
        tab.label_edit.setText("renamed")
        tab._on_save()
        core.macro_set.assert_called_with(2, label="renamed", style=0, icon=0)

        tab.list.setCurrentRow(0)              # plain text, left alone
        tab.label_edit.setText("shove")
        tab._on_save()
        core.macro_set.assert_called_with(0, label="shove", style=0, icon=0)

    def test_an_edited_body_is_still_sent(self):
        """The other half of the same rule -- skipping an unchanged body must not turn
        into skipping a changed one."""
        core = _core()
        tab = MacroTab(core)
        tab.reload()
        tab.list.setCurrentRow(0)
        tab.text_edit.setText("git push --force-with-lease")
        tab._on_save()
        core.macro_set.assert_called_with(
            0, label="push", text="git push --force-with-lease", style=0, icon=0)

    def test_the_step_editor_opens_on_the_current_body(self):
        """Plain text opens as one Type row per character, not as an empty list.

        A macro is usually *extended* into a chord -- you have the text and you want a
        Ctrl+A in front of it -- so starting from nothing would throw away what the
        field already holds.
        """
        seen = {}

        class FakeDialog:
            def __init__(self, steps, parent=None):
                seen["steps"] = steps
                self.result_steps = list(steps)

            def exec_(self):
                return 0        # cancelled

        tab = MacroTab(_core())
        tab.reload()
        tab.list.setCurrentRow(0)               # "push"
        with mock.patch(
                "polyhost.gui.layout_dialog.macro_steps_dialog.MacroStepsDialog",
                FakeDialog):
            tab._on_edit_steps()
        self.assertEqual([s.kind for s in seen["steps"]], ["char"] * 4)
        self.assertEqual("".join(chr(s.code) for s in seen["steps"]), "push")

    def test_a_step_edit_that_is_a_chord_switches_the_tab_to_steps(self):
        core = _core()
        tab = MacroTab(core)
        tab.reload()
        tab.list.setCurrentRow(0)
        self._edit_steps(tab, [macro_body.Step("down", code=0xE0),
                               macro_body.Step("tap", code=0x04),
                               macro_body.Step("up", code=0xE0)])
        self.assertTrue(tab.text_edit.isReadOnly())
        self.assertEqual(tab.text_edit.text(), "Ctrl+A")
        tab._on_save()
        core.macro_set.assert_called_with(
            0, label="push", style=0, icon=0,
            steps=[{"kind": "down", "code": 0xE0, "ms": 0},
                   {"kind": "tap", "code": 0x04, "ms": 0},
                   {"kind": "up", "code": 0xE0, "ms": 0}])

    def test_a_step_edit_back_to_plain_text_hands_the_field_back(self):
        """Removing the last chord must return the ordinary editable field rather than
        leaving the macro in a mode it no longer needs."""
        core = _core()
        tab = MacroTab(core)
        tab.reload()
        tab.list.setCurrentRow(2)               # starts as a chord
        self.assertTrue(tab.text_edit.isReadOnly())
        self._edit_steps(tab, [macro_body.Step("char", code=ord(c)) for c in "hi"])
        self.assertFalse(tab.text_edit.isReadOnly())
        self.assertEqual(tab.text_edit.text(), "hi")
        tab._on_save()
        core.macro_set.assert_called_with(2, label="chord", text="hi", style=0, icon=0)

    @staticmethod
    def _edit_steps(tab, result):
        """Drive `_on_edit_steps` with a dialog that returns `result` and was accepted."""
        class FakeDialog:
            def __init__(self, steps, parent=None):
                self.result_steps = result

            def exec_(self):
                return 1

        with mock.patch(
                "polyhost.gui.layout_dialog.macro_steps_dialog.MacroStepsDialog",
                FakeDialog):
            tab._on_edit_steps()

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
        core = _core(ok=False, payload="Firmware protocol too old for macros (need v15+).")
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

    @staticmethod
    def _lit(tab):
        img = tab.preview.pixmap().toImage()
        return sum(1 for y in range(img.height()) for x in range(img.width())
                   if img.pixelColor(x, y).lightness() > 100)

    def test_clearing_the_label_does_not_leave_a_stale_render(self):
        """A macro with no caption is NOT a blank keycap -- render_macro_key() centres
        the mark in the whole cell -- so the check is that the render CHANGED, not that
        it went dark. Asserting blank pinned the old preview's own omission."""
        tab = self._tab()
        tab.label_edit.setText("push")
        tab._repaint_preview()
        with_label = self._lit(tab)
        tab.label_edit.setText("")
        tab._repaint_preview()
        without = self._lit(tab)
        self.assertGreater(with_label, 0)
        self.assertGreater(without, 0, "an unlabelled macro still shows its index")
        self.assertNotEqual(with_label, without)

    def test_the_label_only_style_draws_bigger_than_the_captioned_one(self):
        """The whole point of STYLE_TEXT: the caption gets the entire cell instead of
        the bottom band, so it lands on a larger face. Measured as ink, because the
        face is chosen by a ladder rather than named."""
        tab = self._tab()
        tab.label_edit.setText("mail")
        tab.style_box.setCurrentIndex(0)
        tab._repaint_preview()
        captioned = self._lit(tab)
        tab.style_box.setCurrentIndex(2)
        tab._repaint_preview()
        big = self._lit(tab)
        self.assertGreater(big, captioned)

    def test_an_icon_the_keyboard_cannot_draw_says_so(self):
        """The firmware falls back to the index for an unknown glyph, so a keycap that
        looks unchanged would read as a bug. The button has to name the case.

        The font source is set EXPLICITLY rather than taken from the environment: it
        decides the wording, so a test that inherited it would pass or fail depending
        on whether a qmk_firmware checkout happens to sit beside this repo.
        """
        tab = self._tab()
        tab.style_box.setCurrentIndex(1)
        tab._icon = 0x10FFFD
        tab._font_source = "headers"
        tab._refresh_icon_button()
        self.assertIn("no glyph", tab.icon_btn.text())

    def test_it_does_not_claim_a_missing_glyph_it_could_not_have_seen(self):
        """Falling back to the shipped packs leaves the RESIDENT fonts out, so a
        resident-only glyph reads as absent when the keyboard draws it fine. A
        confident wrong warning is worse than none."""
        tab = self._tab()
        tab.style_box.setCurrentIndex(1)
        tab._icon = 0x10FFFD
        tab._font_source = "packs"
        tab._refresh_icon_button()
        self.assertNotIn("no glyph", tab.icon_btn.text())
        self.assertIn("unverified", tab.icon_btn.text())

    def test_a_tall_icon_is_drawn_rather_than_skipped(self):
        """The icon has to appear above the caption -- at half size if that is what it
        takes.

        This is the bug the halving exists for, and it was silent on both ends because
        the preview mirrors the firmware's placement: a pack emoji renders at 26-39 px
        of ink while a captioned keycap leaves ~29 rows, so drawing only at native size
        showed NOTHING for four of five picker icons (field, 2026-08-27 -- "after
        selecting the icon I cannot see it in the preview and also not on the keyboard").

        Measured as ink against two references, because the failure has two shapes: it
        must beat the caption alone (something was drawn) and differ from the index
        (what was drawn is the icon, not the fallback).
        """
        tab = self._tab()
        tab.label_edit.setText("push")

        # Caption alone: no mark of any kind. `_mid` is what draws the index, so
        # dropping it is how the reference is taken without touching the render path.
        mid, tab._mid = tab._mid, None
        tab._icon = 0
        tab.style_box.setCurrentIndex(0)
        tab._repaint_preview()
        caption_only = self._lit(tab)
        tab._mid = mid

        tab._repaint_preview()
        with_index = self._lit(tab)

        tab.style_box.setCurrentIndex(1)
        for cp in (0x1F511, 0x2699, 0x1F4E7, 0x1F4BB):   # 33-39 px of ink apiece
            with self.subTest(codepoint=hex(cp)):
                if mk.find_glyph(tab._fonts, cp) is None:
                    self.skipTest(f"no glyph for U+{cp:04X} in the fonts available here")
                tab._icon = cp
                tab._repaint_preview()
                ink = self._lit(tab)
                self.assertGreater(ink, caption_only,
                                   "the icon drew nothing above the caption")
                self.assertNotEqual(ink, with_index,
                                    "the keycap fell back to the index")

    def test_the_icon_only_style_draws_the_icon_and_not_the_caption(self):
        """ICON_ONLY gives the icon the whole cell: the caption is kept in storage —
        so switching back does not lose it — but not drawn.

        Pinned as an EQUALITY against the same icon with the label cleared, which is
        precisely the claim. Ink alone would not distinguish "the caption is not
        drawn" from "the icon moved".
        """
        tab = self._tab()
        if mk.find_glyph(tab._fonts, 0x1F511) is None:
            self.skipTest("no glyph to draw")
        tab._icon = 0x1F511
        tab.style_box.setCurrentIndex(1)          # icon above the label
        tab.label_edit.setText("")
        tab._repaint_preview()
        icon_alone = tab.preview.pixmap().toImage()

        tab.label_edit.setText("work mail")
        tab.style_box.setCurrentIndex(3)          # icon only
        tab._repaint_preview()
        self.assertEqual(tab.preview.pixmap().toImage(), icon_alone)

        tab.style_box.setCurrentIndex(1)
        tab._repaint_preview()
        self.assertNotEqual(tab.preview.pixmap().toImage(), icon_alone,
                            "the captioned style must still draw its caption")

    def test_the_icon_only_style_still_lets_you_choose_an_icon(self):
        """It is one of the two styles that uses the icon, so the picker must be
        reachable from it -- gating on the captioned style alone left the setting
        selectable and unconfigurable."""
        tab = self._tab()
        tab.style_box.setCurrentIndex(3)
        self.assertTrue(tab.icon_btn.isEnabled())

    def test_an_icon_that_fits_at_no_size_is_reported_as_not_drawn(self):
        """`_draw_mark` returns False rather than clipping, so `_render` can fall back
        to the index. Defensive in practice -- half of even the tallest pack glyph is
        ~20 px and a single-line caption leaves ~29 rows -- but the fallback is only
        correct if this half of it is honest.
        """
        tab = self._tab()
        hit = mk.find_glyph(tab._fonts, 0x1F511)
        if hit is None:
            self.skipTest("no glyph to measure")
        font, glyph = hit
        img = QImage(ml.PANEL_W, ml.PANEL_H, QImage.Format_RGB32)
        img.fill(0)
        self.assertFalse(
            tab._draw_mark(img, 0xFFFFFF, chr(0x1F511), [font], 0,
                           free_rows=4, glyph=glyph))

    def test_the_icon_controls_are_dead_unless_the_style_uses_them(self):
        tab = self._tab()
        tab.style_box.setCurrentIndex(0)
        self.assertFalse(tab.icon_btn.isEnabled())
        tab.style_box.setCurrentIndex(1)
        self.assertTrue(tab.icon_btn.isEnabled())


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

    def test_the_page_fits_the_height_the_browser_will_give_it(self):
        """The label meter must not be drawn over the keycap preview.

        Measured, not reasoned: the browser caps itself at 400 px, so this page is
        handed ~350 px on EVERY open -- always short, never occasionally. The preview
        is a fixed size and cannot give the deficit back, so a full-width meter row
        below it landed on top of the preview's bottom rows, which is exactly where
        the label renders (field, 2026-08-27).

        The WIDTH matters and 900 is not arbitrary: the two notes below are
        word-wrapped labels, which report a ONE-LINE minimum to the layout, so the
        deficit only appears once they wrap -- at 1200 px the pre-fix layout does not
        overlap and this test would pass against the bug. The dialog clamps itself to
        the screen, so a 1024/1280-wide display lands squarely here.

        A height assertion would not pin this either, for the same reason: the wrapped
        labels make minimumSizeHint() understate what the page needs.
        """
        core = _core()
        b = self._browser(core)
        b.resize(900, b.maximumHeight())
        b.tabs.setCurrentIndex(self._titles(b).index("Macros"))
        b.show()
        _APP.processEvents()
        tab = b.macro_tab
        meter = tab.width_meter.geometry().translated(
            tab.width_meter.parentWidget().mapTo(tab, tab.width_meter.pos()) -
            tab.width_meter.pos())
        preview = tab.preview.geometry().translated(
            tab.preview.parentWidget().mapTo(tab, tab.preview.pos()) -
            tab.preview.pos())
        b.hide()
        self.assertFalse(
            meter.intersects(preview),
            f"the label meter {meter} overlaps the keycap preview {preview}")

    def test_the_icon_controls_sit_under_the_preview(self):
        """The button reads the chosen codepoint back, so it is a readout as much as a
        control -- it belongs with the picture it changes, not in the field column."""
        core = _core()
        b = self._browser(core)
        b.resize(900, b.maximumHeight())
        b.tabs.setCurrentIndex(self._titles(b).index("Macros"))
        b.show()
        _APP.processEvents()
        tab = b.macro_tab
        prev = tab.preview.parentWidget().mapTo(tab, tab.preview.pos())
        btn = tab.icon_btn.parentWidget().mapTo(tab, tab.icon_btn.pos())
        b.hide()
        self.assertGreaterEqual(btn.y(), prev.y() + tab.preview.height(),
                                "the icon button is not below the preview")
        self.assertGreaterEqual(btn.x(), prev.x(),
                                "the icon button is not in the preview's column")

    def test_the_body_field_sits_beside_the_preview_not_under_it(self):
        """The preview is three keycaps tall and the fields beside it are one row each,
        so the column had a hole in it and the body field sat below the whole top row --
        further from the fields it belongs with than from the buttons.

        Pinned as geometry rather than as layout structure: what the reader sees is
        where it lands, and the two are only the same while nothing else grows.
        """
        core = _core()
        b = self._browser(core)
        b.resize(900, b.maximumHeight())
        b.tabs.setCurrentIndex(self._titles(b).index("Macros"))
        b.show()
        _APP.processEvents()
        tab = b.macro_tab
        prev = tab.preview.parentWidget().mapTo(tab, tab.preview.pos())
        body = tab.text_edit.parentWidget().mapTo(tab, tab.text_edit.pos())
        name = tab.label_edit.parentWidget().mapTo(tab, tab.label_edit.pos())
        style = tab.style_box.parentWidget().mapTo(tab, tab.style_box.pos())
        b.hide()
        self.assertLess(body.y(), prev.y() + tab.preview.height(),
                        "the body field is below the preview, not beside it")
        self.assertLessEqual(body.x() + tab.text_edit.width(), prev.x(),
                             "the body field runs under the preview")
        # All three rows are named, so all three start on one x. The style box was
        # the last unnamed control in the column and read as a stray one because of
        # it -- it began at the labels' margin while its neighbours began after them.
        self.assertEqual({body.x(), name.x(), style.x()}, {name.x()},
                         "the three fields no longer start on one x")

    def test_the_editing_column_needs_no_vertical_scrolling(self):
        """Everything that composes the keycap sits beside the preview, so the column
        fits the height the browser gives it and the scrollbar stays a safety net
        rather than the normal state.

        Asserted on the scroll area's own arithmetic -- widget height against viewport
        height -- because that IS what decides whether the bar appears.
        """
        core = _core()
        b = self._browser(core)
        b.resize(900, b.maximumHeight())
        b.tabs.setCurrentIndex(self._titles(b).index("Macros"))
        b.show()
        _APP.processEvents()
        tab = b.macro_tab
        area = tab.preview.parentWidget().parentWidget()   # the QScrollArea's viewport owner
        while area is not None and not isinstance(area, QScrollArea):
            area = area.parentWidget()
        self.assertIsNotNone(area, "the editing column is no longer in a scroll area")
        needed = area.widget().sizeHint().height()
        have = area.viewport().height()
        b.hide()
        self.assertLessEqual(needed, have,
                             f"the editing column needs {needed} px of the {have} it is "
                             "given -- it will scroll")

    def test_the_actions_stay_reachable_at_the_height_it_is_given(self):
        """Save / Clear / Use-on-key sit in a fixed footer, not in the scrolled column.

        The column can need more height than the browser's 400 px cap ever gives it, so
        anything inside it can end up below the fold -- and a tab whose Save button is
        the part you cannot see reads as one that does not work.
        """
        core = _core()
        b = self._browser(core)
        b.resize(900, b.maximumHeight())
        b.tabs.setCurrentIndex(self._titles(b).index("Macros"))
        b.show()
        _APP.processEvents()
        tab = b.macro_tab
        btn = tab.save_btn
        top_left = btn.parentWidget().mapTo(tab, btn.pos())
        b.hide()
        self.assertLessEqual(top_left.y() + btn.height(), tab.height(),
                             "the Save button is below the fold")


if __name__ == "__main__":
    unittest.main()
