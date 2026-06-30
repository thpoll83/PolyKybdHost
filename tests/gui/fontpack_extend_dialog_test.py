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

    def test_ok_disabled_until_built(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        self.assertFalse(dlg._ok_btn.isEnabled())        # nothing built yet
        self.assertIsNone(dlg.result_font)               # no result on construct
        # no save/flash/version/pending machinery in the editor anymore
        for attr in ("_save_btn", "_flash_btn", "_version", "_pending_list", "_apply_btn"):
            self.assertFalse(hasattr(dlg, attr), attr)

    def test_range_is_single_row_and_flags_grid(self):
        # both range boxes exist (laid out side by side) and the four flag checkboxes
        # are present (2x2 grid)
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        self.assertIsNotNone(dlg._first); self.assertIsNotNone(dlg._last)
        for cb in (dlg._gray, dlg._norm, dlg._inv, dlg._edge):
            self.assertIsNotNone(cb)

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

    def test_zoom_noop_until_built(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._scale, 3)
        self.assertFalse(dlg._zoom(1))             # nothing built -> no change
        self.assertEqual(dlg._scale, 3)

    @unittest.skipUnless(_FONTGEN and _FONT and _HAVE_BUNDLES,
                         "needs fontgen deps + a TTF + shipped bundles")
    def test_scroll_wheel_zoom_changes_scale(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        dlg._src.setText(_FONT)
        dlg._first.setText("0x41"); dlg._last.setText("0x41")
        dlg._build()
        self.assertEqual(dlg._scale, 3.0)
        w0 = dlg._preview.pixmap().width()
        self.assertTrue(dlg._zoom(0.5))            # wheel up -> +0.5
        self.assertEqual(dlg._scale, 3.5)
        self.assertGreater(dlg._preview.pixmap().width(), w0)
        for _ in range(40):
            dlg._zoom(-0.5)
        self.assertEqual(dlg._scale, 0.5)          # clamps at 0.5
        for _ in range(40):
            dlg._zoom(0.5)
        self.assertEqual(dlg._scale, 7.0)          # clamps at 7.0

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

    def test_lang_flags_record_loaded(self):
        rec = fed._lang_flags()
        if not rec:
            self.skipTest("no shipped lang_flags.json")
        self.assertEqual(rec.get("source_file"), "NotoColorEmoji-Regular.ttf")
        groups = [g for g in rec["sequence"].split(",") if g.strip()]
        self.assertEqual(len(groups), rec["count"])      # one group per flag

    def test_flags_record_for_range(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        rec = fed._lang_flags()
        if not rec:
            self.skipTest("no shipped lang_flags.json")
        base = int(rec["seq_first"])
        self.assertIsNotNone(dlg._flags_record_for(base))            # first flag cp
        self.assertIsNotNone(dlg._flags_record_for(base + rec["count"] - 1))  # last
        self.assertIsNone(dlg._flags_record_for(base + rec["count"]))         # past end
        self.assertIsNone(dlg._flags_record_for(0x41))               # not a flag cp

    def test_flag_edit_prefills_sequence_mode(self):
        rec = fed._lang_flags()
        if not rec:
            self.skipTest("no shipped lang_flags.json")
        base = int(rec["seq_first"])
        groups = [g.strip() for g in rec["sequence"].split(",") if g.strip()]
        cp = base + 2                                    # third flag
        dlg = fed.FontPackExtendDialog(
            prefill={"bundle": "flags", "first": cp, "last": cp,
                     "global_index": 144, "font_first": base, "font_last": base + rec["count"] - 1})
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._mode.currentIndex(), 1)    # HarfBuzz sequence
        self.assertEqual(dlg._seq.text(), groups[2])     # the per-flag regional pair
        self.assertEqual(int(dlg._seq_first.text(), 16), cp)
        # options came from lang_flags.json
        self.assertEqual(dlg._size.value(), 20)
        self.assertTrue(dlg._gray.isChecked())
        self.assertEqual(dlg._rsize.value(), 54)
        self.assertEqual(dlg._maxw.value(), 72)
        self.assertEqual(dlg._outline.value(), 1)
        self.assertFalse(dlg._composite.isChecked())     # flags are non-composite
        self.assertEqual(dlg._dl_panel.current_filename(), "NotoColorEmoji-Regular.ttf")

    def test_setup_sequence_edit_infers_composite_for_matra(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        opts = {"sequence": "25CC 0901, 25CC 0902, 25CC 0903"}   # dotted-circle base
        dlg._setup_sequence_edit(0xE101, 0xE100, opts)           # second group
        self.assertEqual(dlg._mode.currentIndex(), 1)            # sequence mode
        self.assertEqual(dlg._seq.text(), "25CC 0902")
        self.assertEqual(int(dlg._seq_first.text(), 16), 0xE101)
        self.assertTrue(dlg._composite.isChecked())              # inferred from U+25CC

    def test_setup_sequence_edit_flag_not_composite(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        opts = {"sequence": "1F1FA 1F1F8, 1F1E9 1F1EA", "composite": False}
        dlg._setup_sequence_edit(0xE000, 0xE000, opts)
        self.assertEqual(dlg._seq.text(), "1F1FA 1F1F8")
        self.assertFalse(dlg._composite.isChecked())

    def test_options_composite_only_in_sequence_mode(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        dlg._mode.setCurrentIndex(1); dlg._sync_mode()           # sequence
        dlg._composite.setChecked(True)
        self.assertTrue(dlg._options().composite)
        dlg._mode.setCurrentIndex(0); dlg._sync_mode()           # range
        self.assertFalse(dlg._options().composite)               # ignored outside sequence

    def test_reset_restores_opened_settings(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        base_size = dlg._size.value()
        dlg._size.setValue(base_size + 13)
        dlg._gamma.setValue(2.3); dlg._inv.setChecked(True)
        dlg._reset()
        self.assertEqual(dlg._size.value(), base_size)
        self.assertEqual(dlg._gamma.value(), 1.0)
        self.assertFalse(dlg._inv.isChecked())

    def test_float_spins_uniform_width_and_step(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        floats = (dlg._gamma, dlg._contrast, dlg._exposure, dlg._sharp, dlg._sat)
        widths = {s.width() for s in floats}
        self.assertEqual(len(widths), 1)                 # all the same fixed width
        for s in floats:
            self.assertEqual(s.singleStep(), 0.1)        # 0.1 increment

    def test_with_slider_two_way_sync(self):
        from PyQt5.QtWidgets import QSlider
        spin = fed.FontPackExtendDialog._dspin(0.0, 2.0, 1.0, 0.05)
        w = fed.FontPackExtendDialog._with_slider(spin)
        sl = w.findChild(QSlider)
        self.assertIsNotNone(sl)
        self.assertEqual(sl.value(), round(1.0 / 0.05))      # initial sync
        sl.setValue(round(0.5 / 0.05))                       # slider -> spin
        self.assertAlmostEqual(spin.value(), 0.5, places=2)
        spin.setValue(1.5)                                   # spin -> slider
        self.assertEqual(sl.value(), round(1.5 / 0.05))

    @unittest.skipUnless(_FONTGEN and _FONT and _HAVE_BUNDLES,
                         "needs fontgen deps + a TTF + shipped bundles")
    def test_build_then_ok_sets_result(self):
        dlg = fed.FontPackExtendDialog()
        self.addCleanup(dlg.deleteLater)
        dlg._src.setText(_FONT)
        dlg._bundle.setCurrentIndex(0); dlg._default_index()
        label = dlg._packs[0][0]
        gidx = dlg._gidx.value()
        dlg._first.setText("0x2190"); dlg._last.setText("0x2193"); dlg._size.setValue(24)

        dlg._build()
        self.assertIsNotNone(dlg._built)
        self.assertTrue(dlg._ok_btn.isEnabled())
        self.assertFalse(dlg._preview.pixmap().isNull())

        dlg._ok()                                  # keep it
        self.assertIsNotNone(dlg.result_font)
        self.assertEqual(dlg.result_label, label)
        self.assertIsNone(dlg.result_edit)         # whole-font add, not an edit
        self.assertEqual(dlg.result_font.global_index, gidx)

    @unittest.skipUnless(_FONTGEN and _FONT and _HAVE_BUNDLES,
                         "needs fontgen deps + a TTF + shipped bundles")
    def test_ok_in_edit_mode_returns_edit_target(self):
        pack = fpr.decode_pack_file(os.path.join(RES, "symbol.plyf"), "symbol")
        font = pack.fonts[0]
        cp = font.first
        dlg = fed.FontPackExtendDialog(
            prefill={"bundle": "symbol", "first": cp, "last": cp,
                     "global_index": font.global_index})
        self.addCleanup(dlg.deleteLater)
        dlg._src.setText(_FONT)
        dlg._build()
        dlg._ok()
        self.assertEqual(dlg.result_edit,
                         {"global_index": font.global_index, "cp": cp})
        self.assertEqual(dlg.result_label, "symbol")


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
        import struct
        body = b"PolyKybdTestFont" * 64
        sfnt = (struct.pack(">4sHHHH", b"\x00\x01\x00\x00", 1, 16, 0, 0)
                + struct.pack(">4sIII", b"glyf", 0, 28, len(body)) + body)
        with open(src, "wb") as f:
            f.write(sfnt)                          # a structurally-valid sfnt
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
        import struct
        body = b"PolyKybdTestFont" * 4
        with open(path, "wb") as f:                # a structurally-valid sfnt (passes is_downloaded)
            f.write(struct.pack(">4sHHHH", b"\x00\x01\x00\x00", 1, 16, 0, 0)
                    + struct.pack(">4sIII", b"glyf", 0, 28, len(body)) + body)
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
