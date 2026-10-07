"""The layout editor's preview-language picker.

The previews used to draw every layout in en-US whatever the keyboard was set to,
so no language-dependent legend could ever be seen in the editor. These drive the
real dialog: it must open on the keyboard's own language, fall back to en-US when
that is unknown, redraw on a change, and stay out of the way in Symbol mode.
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
    _APP = QApplication.instance() or QApplication([])


def setUpModule():
    # Pin the QApplication for the life of the module (see kb_layout_screens_test).
    if _IMPORT_ERR is None:
        assert _APP is not None


class _CoreWithLang(_Core if _IMPORT_ERR is None else object):
    def __init__(self, lang, **kw):
        super().__init__(**kw)
        self._lang = lang

    def get_status(self):
        return {"current_lang": self._lang}


@unittest.skipIf(_IMPORT_ERR is not None, "PyQt5 not installed")
class PreviewLanguageTest(unittest.TestCase):
    def _dialog(self, core):
        dlg = kb.KbLayoutDialog(core, _Settings())
        if dlg.preview_lang.count() == 0:
            self.skipTest("no language table loaded")
        return dlg

    def test_it_opens_on_the_keyboards_language(self):
        dlg = self._dialog(_CoreWithLang("ko-KR"))
        self.assertEqual(dlg.preview_lang.currentText(), "ko-KR")
        self.assertEqual(dlg._preview._lang, "ko-KR")

    def test_an_unknown_keyboard_language_falls_back_to_en_US(self):
        for core in (_Core(), _CoreWithLang(None), _CoreWithLang("xx-XX")):
            dlg = self._dialog(core)
            self.assertEqual(dlg.preview_lang.currentText(), kb.DEFAULT_LANG)

    def test_a_change_redraws_in_the_new_language(self):
        dlg = self._dialog(_CoreWithLang("en-US"))
        dlg._key_cache[0x04] = object()           # a pixmap drawn in en-US
        dlg.preview_lang.setCurrentText("de-DE")
        self.assertEqual(dlg._preview._lang, "de-DE")
        self.assertNotIn(0x04, dlg._key_cache)    # no stale en-US legend survives

    def test_symbol_mode_disables_it(self):
        dlg = self._dialog(_CoreWithLang("en-US"))
        dlg.set_keycap_mode(kb.KEYCAP_SYMBOL)
        self.assertFalse(dlg.preview_lang.isEnabled())
        dlg.set_keycap_mode(kb.KEYCAP_PREVIEW)
        self.assertTrue(dlg.preview_lang.isEnabled())


if __name__ == "__main__":
    unittest.main()
