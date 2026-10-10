"""The layout editor's preview-language picker.

The previews used to draw every layout in en-US whatever the keyboard was set to,
so no language-dependent legend could ever be seen in the editor. These drive the
real dialog: it must open on the keyboard's own language, fall back to en-US when
that is unknown, redraw the keys on a change, and stay out of the way in Symbol mode.
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
    from polyhost.gui.layout_dialog import kb_layout_dialog as kb
    from tests.gui.kb_layout_screens_test import _Core, _Settings

KC_A = 0x04


class _CoreWithLang(_Core if _IMPORT_ERR is None else object):
    """A keyboard reporting `lang` the way the firmware does, with KC_A on every
    key of layer 0 so a redraw has a language-dependent legend to change."""

    def __init__(self, lang, **kw):
        super().__init__(**kw)
        self._lang = lang

    def get_status(self):
        return {"current_lang": self._lang}

    def keymap_buffer(self, *a, **k):
        ok, buf = super().keymap_buffer(*a, **k)
        cols, rows = _Settings.MATRIX_COLUMNS, _Settings.MATRIX_ROWS
        buf[:cols * rows] = [KC_A] * (cols * rows)
        return ok, buf


@unittest.skipIf(_IMPORT_ERR is not None, "PyQt5 not installed")
class PreviewLanguageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Held on the class for the life of the tests: Qt needs exactly one
        # QApplication, and it must outlive every widget built below.
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, core):
        dlg = kb.KbLayoutDialog(core, _Settings())
        # The language table SHIPS with the host (res/preview), so an empty picker
        # is a broken picker -- a failure, never a skip.
        langs = [dlg.preview_lang.itemText(i) for i in range(dlg.preview_lang.count())]
        for lang in ("en-US", "de-DE", "ko-KR", "ja-JP"):
            self.assertIn(lang, langs)
        return dlg

    def test_it_opens_on_the_keyboards_language(self):
        """`koKR` is what GET_LANG really answers; `ko-KR` covers a core that
        already spells it the table's way."""
        for reported in ("koKR", "ko-KR"):
            dlg = self._dialog(_CoreWithLang(reported))
            self.assertEqual(dlg.preview_lang.currentText(), "ko-KR", reported)
            self.assertEqual(dlg._preview._lang, "ko-KR", reported)

    def test_client_mode_reads_the_cached_snapshot_not_an_rpc(self):
        """RemoteCore.get_status() is an RPC to the daemon that waits for the
        reply, so the GUI thread must read status_snapshot() instead."""
        class _Client(_CoreWithLang):
            def status_snapshot(self):
                return {"current_lang": self._lang}

            def get_status(self):
                raise AssertionError("get_status() blocks on the daemon")

        dlg = self._dialog(_Client("jaJP"))
        self.assertEqual(dlg.preview_lang.currentText(), "ja-JP")

    def test_an_unknown_keyboard_language_falls_back_to_en_US(self):
        for core in (_Core(), _CoreWithLang(None), _CoreWithLang("xxXX")):
            dlg = self._dialog(core)
            self.assertEqual(dlg.preview_lang.currentText(), kb.DEFAULT_LANG)

    def test_a_change_redraws_the_keys_on_screen(self):
        dlg = self._dialog(_CoreWithLang("enUS"))
        dlg.set_keycap_mode(kb.KEYCAP_PREVIEW)
        item = next(k for i, k in sorted(dlg.keys.items()) if dlg._has_display(i))
        before = item._keycap
        self.assertIsNotNone(before, "the en-US `a` should have a keycap")
        dlg.preview_lang.setCurrentText("ko-KR")
        after = item._keycap
        self.assertIsNotNone(after)
        # ㅁ is not a: the picture ON the key changed, not just a cache
        self.assertNotEqual(before.toImage(), after.toImage())

    def test_symbol_mode_disables_it(self):
        dlg = self._dialog(_CoreWithLang("enUS"))
        dlg.set_keycap_mode(kb.KEYCAP_SYMBOL)
        self.assertFalse(dlg.preview_lang.isEnabled())
        dlg.set_keycap_mode(kb.KEYCAP_PREVIEW)
        self.assertTrue(dlg.preview_lang.isEnabled())


if __name__ == "__main__":
    unittest.main()
