"""FontPackExtendDialog — drives the build→preview→splice→(save/flash) round-trip
under the offscreen Qt platform.  The build step needs freetype-py + a system TTF
+ the shipped bundles; those sub-tests skip otherwise, but the dialog must still
*construct* without the [fontgen] deps.
"""
import glob
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui import fontpack_extend_dialog as fed
    from polyhost.services import fontpack_reader as fpr
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e

try:
    import numpy  # noqa: F401
    import freetype  # noqa: F401
    _FONTGEN = True
except Exception:
    _FONTGEN = False

_FONT = next(iter(glob.glob("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
                  + glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)), None)
RES = os.path.join(os.path.dirname(__file__), "..", "..", "polyhost", "res", "fontpack")
_HAVE_BUNDLES = os.path.exists(os.path.join(RES, "bundles.json"))


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class ExtendDialogTest(unittest.TestCase):

    def test_constructs_without_flash_button(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        self.assertFalse(hasattr(dlg, "_flash_btn"))     # no callback -> no Flash

    def test_flash_button_present_with_callback(self):
        dlg = fed.FontPackExtendDialog(flash_cb=lambda i, d: None)
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(hasattr(dlg, "_flash_btn"))

    @unittest.skipUnless(os.path.exists(os.path.join(RES, "bundles.json")),
                         "shipped bundles required")
    def test_prefill_targets_glyph(self):
        dlg = fed.FontPackExtendDialog(
            prefill={"bundle": "symbol", "first": 0x2600, "last": 0x2600,
                     "global_index": 19})
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._bundle.currentText(), "symbol")
        self.assertEqual(dlg._mode.currentIndex(), 0)        # codepoint range
        self.assertEqual(int(dlg._first.text(), 16), 0x2600)
        self.assertEqual(int(dlg._last.text(), 16), 0x2600)
        self.assertEqual(dlg._gidx.value(), 19)

    def test_edit_prefills_saved_settings(self):
        settings = fed._render_settings()
        # an emoji-style record exercises every control (grayscale + invert + outline)
        gi = next((k for k, v in settings.items()
                   if v.get("grayscale") and v.get("invert") and v.get("outline")), None)
        if gi is None:
            self.skipTest("no shipped render settings")
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(dlg._apply_saved_settings(int(gi)))
        v = settings[gi]
        self.assertEqual(dlg._size.value(), int(v["size"]))
        self.assertTrue(dlg._gray.isChecked())
        self.assertTrue(dlg._inv.isChecked())
        self.assertEqual(dlg._outline.value(), int(v["outline"]))
        if "render_height" in v:
            self.assertEqual(dlg._rsize.value(), int(v["render_height"]))

    def test_edit_autofills_cached_source_font(self):
        import tempfile
        from unittest.mock import patch
        from polyhost.services import font_downloader as fdl
        settings = fed._render_settings()
        gi = next((k for k, v in settings.items() if v.get("source_file")), None)
        if gi is None:
            self.skipTest("no shipped render settings with source_file")
        sf = settings[gi]["source_file"]
        tmp = tempfile.mkdtemp()
        open(os.path.join(tmp, sf), "wb").close()       # pretend it's cached
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        with patch.object(fdl, "default_cache_dir", return_value=tmp):
            opts = dlg._apply_saved_settings(int(gi))
        self.assertIsNotNone(opts)
        self.assertEqual(dlg._src.text(), os.path.join(tmp, sf))

    def test_apply_saved_settings_missing_index(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        self.assertFalse(dlg._apply_saved_settings(999999))   # unknown -> no prefill

    def test_weight_prefilled(self):
        settings = fed._render_settings()
        gi = next((k for k, v in settings.items() if v.get("weight")), None)
        if gi is None:
            self.skipTest("no shipped settings with a weight")
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        dlg._apply_saved_settings(int(gi))
        self.assertEqual(dlg._weight.value(), int(settings[gi]["weight"]))
        # the value round-trips into RenderOptions (-w)
        self.assertEqual(dlg._options().weight, int(settings[gi]["weight"]))

    def test_tone_controls_flow_into_options(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        dlg._gamma.setValue(1.5)
        dlg._contrast.setValue(2.0)
        dlg._exposure.setValue(0.5)
        dlg._sharp.setValue(1.0)
        dlg._sat.setValue(0.3)
        ro = dlg._options()
        self.assertEqual((ro.gamma_val, ro.contrast, ro.exposure, ro.sharpness,
                          ro.saturation_boost), (1.5, 2.0, 0.5, 1.0, 0.3))

    def test_weight_zero_means_unset(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._weight.value(), 0)
        self.assertEqual(dlg._options().weight, -1)        # 0 in UI -> unset

    def test_auto_update_schedules_only_when_enabled(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        dlg._auto.setChecked(True)
        dlg._auto_timer.stop()
        dlg._size.setValue(dlg._size.value() + 1)      # change -> debounced schedule
        self.assertTrue(dlg._auto_timer.isActive())
        dlg._auto.setChecked(False)
        dlg._auto_timer.stop()
        dlg._size.setValue(dlg._size.value() + 1)
        self.assertFalse(dlg._auto_timer.isActive())   # off -> no auto rebuild

    def test_auto_build_noop_without_source(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        dlg._auto.setChecked(True)
        dlg._auto_build()                              # no source -> silently does nothing
        self.assertIsNone(dlg._built)

    @unittest.skipUnless(_FONTGEN and _FONT and _HAVE_BUNDLES,
                         "needs fontgen deps + a TTF + shipped bundles")
    def test_auto_build_renders_without_button(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        dlg._src.setText(_FONT)
        dlg._first.setText("0x41"); dlg._last.setText("0x42")
        dlg._auto_build()                              # no Build click
        self.assertIsNotNone(dlg._built)
        self.assertFalse(dlg._preview.pixmap().isNull())

    def test_download_panel_sets_source(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        self.assertTrue(dlg._dl_panel.isVisibleTo(dlg))    # always under the preview
        dlg._dl_panel.font_chosen.emit("/tmp/some-font.ttf")
        self.assertEqual(dlg._src.text(), "/tmp/some-font.ttf")

    @unittest.skipUnless(os.path.exists(os.path.join(RES, "bundles.json")),
                         "shipped bundles required")
    def test_prefill_selects_source_in_browser(self):
        # editing a glyph should default-select its generation font in the browser
        pack = fpr.decode_pack_file(os.path.join(RES, "symbol.plyf"), "symbol")
        font = pack.fonts[0]
        sf = fed._render_settings().get(str(font.global_index), {}).get("source_file")
        if not sf:
            self.skipTest("no source_file for this font")
        dlg = fed.FontPackExtendDialog(
            prefill={"bundle": "symbol", "first": font.first, "last": font.first,
                     "global_index": font.global_index})
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._dl_panel.current_filename(), sf)

    @unittest.skipUnless(os.path.exists(os.path.join(RES, "bundles.json")),
                         "shipped bundles required")
    def test_unknown_prefill_bundle_rejected(self):
        # an edit prefill for a bundle not in the source list must fail loudly
        # rather than silently retargeting another pack
        with self.assertRaises(ValueError):
            fed.FontPackExtendDialog(
                prefill={"bundle": "does-not-exist", "first": 0x2600,
                         "last": 0x2600, "global_index": 1})

    @unittest.skipUnless(_FONTGEN and _FONT and _HAVE_BUNDLES,
                         "needs fontgen deps + a TTF + shipped bundles")
    def test_build_splice_and_flash_callback(self):
        got = {}
        dlg = fed.FontPackExtendDialog(flash_cb=lambda i, d: got.update(idx=i, data=d))
        self.addCleanup(dlg.deleteLater)
        dlg._src.setText(_FONT)
        dlg._first.setText("0x2190"); dlg._last.setText("0x2193"); dlg._size.setValue(24)
        dlg._bundle.setCurrentIndex(0); dlg._default_index()
        gidx = dlg._gidx.value()
        dlg._build()

        self.assertIsNotNone(dlg._built)
        self.assertFalse(dlg._preview.pixmap().isNull())
        self.assertTrue(dlg._save_btn.isEnabled())

        data = dlg._spliced_bytes()
        pack = fpr.decode_pack(data)
        self.assertTrue(pack.crc_ok)
        target = dlg._bundle.currentData()
        self.assertEqual(pack.font_count, target.font_count + 1)
        self.assertTrue(any(f.global_index == gidx for f in pack.fonts))

        # auto-confirm the flash dialog, then verify the callback fires
        from unittest.mock import patch
        with patch.object(fed.QMessageBox, "question",
                          return_value=fed.QMessageBox.Yes):
            dlg._flash()
        self.assertEqual(got["idx"], 0)
        self.assertEqual(got["data"], data)


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class NotoDownloadDialogTest(unittest.TestCase):

    def test_lists_catalog(self):
        dlg = fed.NotoDownloadDialog()
        self.addCleanup(dlg.deleteLater)
        from polyhost.services import font_downloader as fdl
        self.assertEqual(dlg._list.count(), len(fdl.load_catalog()))

    def test_threaded_download_over_file_url(self):
        import tempfile, pathlib
        from unittest.mock import patch
        from polyhost.services import font_downloader as fdl
        tmp = tempfile.mkdtemp()
        src = os.path.join(tmp, "remote.ttf")
        with open(src, "wb") as f:
            f.write(b"FONTDATA" * 500)
        font = fdl.NotoFont("Fake", pathlib.Path(src).as_uri(), "Fake-Regular.ttf")
        cache = os.path.join(tmp, "cache")
        with patch.object(fdl, "load_catalog", return_value=[font]), \
             patch.object(fdl, "default_cache_dir", return_value=cache):
            dlg = fed.NotoDownloadDialog()
            self.addCleanup(dlg.deleteLater)
            dlg._list.setCurrentRow(0)
            dlg._download()                       # real worker thread + file:// fetch
        self.assertEqual(dlg.result_path, os.path.join(cache, "Fake-Regular.ttf"))
        self.assertTrue(os.path.exists(dlg.result_path))

    def test_cached_font_picked_without_network(self):
        import tempfile
        from unittest.mock import patch
        from polyhost.services import font_downloader as fdl
        tmp = tempfile.mkdtemp()
        fonts = fdl.load_catalog()
        # pre-seed the cache with the first font so it's "downloaded"
        cached = fonts[0]
        os.makedirs(os.path.join(tmp, "fonts"), exist_ok=True)
        path = os.path.join(tmp, "fonts", cached.filename)
        with open(path, "wb") as f:
            f.write(b"x")
        with patch.object(fdl, "default_cache_dir", return_value=os.path.join(tmp, "fonts")):
            dlg = fed.NotoDownloadDialog()
            self.addCleanup(dlg.deleteLater)
            dlg._list.setCurrentRow(0)
            # _download must take the cached branch (no urlopen) and accept
            with patch("urllib.request.urlopen", side_effect=AssertionError("network!")):
                dlg._download()
            self.assertEqual(dlg.result_path, path)


if __name__ == "__main__":
    unittest.main()
