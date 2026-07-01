"""FontPackInspectorDialog — constructs over the shipped bundles and a synthetic
source.  Needs only PyQt5 (the dialog doesn't import host.py / pynput), so it runs
under the offscreen Qt platform with no X server.
"""
import glob
import os
import struct
import binascii
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import numpy  # noqa: F401
    import freetype  # noqa: F401
    _FONTGEN = True
except Exception:
    _FONTGEN = False
_FONT = next(iter(glob.glob("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
                  + glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)), None)

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui import fontpack_inspector_dialog as fid
    from polyhost.services import fontpack_reader as fpr
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e


def _pack_with_empty():
    """One 2-glyph font: A present (3x4), B empty — for exercising peek fallback."""
    glyphs = struct.pack("<Hbbbbbx", 0, 3, 4, 5, -1, -7) + struct.pack("<Hbbbbbx", 0, 0, 0, 0, 0, 0)
    bitmap = bytes([0x12, 0x34])
    table_off = 32
    glyph_off = table_off + 20
    bitmap_off = (glyph_off + len(glyphs) + 3) & ~3
    total = (bitmap_off + len(bitmap) + 3) & ~3
    body = bytearray(total - 32)
    body[table_off - 32:table_off - 32 + 20] = struct.pack("<IIIIhH", bitmap_off, glyph_off, 0x41, 0x42, 12, 0)
    body[glyph_off - 32:glyph_off - 32 + len(glyphs)] = glyphs
    body[bitmap_off - 32:bitmap_off - 32 + len(bitmap)] = bitmap
    crc = binascii.crc32(bytes(body)) & 0xFFFFFFFF
    header = struct.pack("<4sHHIIIIII", b"PlyF", 1, 0, 7, 1, table_off, total, crc, 0)
    return fpr.decode_pack(header + bytes(body), name_hint="emptytest")


def _tiny_pack():
    """One 2-glyph font, valid PlyF, decoded to a Pack for a deterministic tab."""
    # glyph A: 3x4 = 12 bits -> 2 bytes @0; glyph B: 6x8 = 48 bits -> 6 bytes @2
    glyphs = struct.pack("<Hbbbbbx", 0, 3, 4, 5, -1, -7) + struct.pack("<Hbbbbbx", 2, 6, 8, 9, 0, -3)
    bitmap = bytes([0x12, 0x34, 0xFF, 0x00, 0xAA, 0x55, 0x0F, 0xF0])
    table_off = 32
    glyph_off = table_off + 20
    bitmap_off = (glyph_off + len(glyphs) + 3) & ~3
    total = (bitmap_off + len(bitmap) + 3) & ~3
    body = bytearray(total - 32)
    body[table_off - 32:table_off - 32 + 20] = struct.pack("<IIIIhH", bitmap_off, glyph_off, 0x41, 0x42, 12, 0)
    body[glyph_off - 32:glyph_off - 32 + len(glyphs)] = glyphs
    body[bitmap_off - 32:bitmap_off - 32 + len(bitmap)] = bitmap
    crc = binascii.crc32(bytes(body)) & 0xFFFFFFFF
    header = struct.pack("<4sHHIIIIII", b"PlyF", 1, 0, 7, 1, table_off, total, crc, 0)
    return fpr.decode_pack(header + bytes(body), name_hint="tiny")


def _g(off, w, h):
    return dict(bitmapOffset=off, width=w, height=h, xAdvance=w + 1, xOffset=0, yOffset=0)


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class FontPackInspectorDialogTest(unittest.TestCase):

    def test_synthetic_source(self):
        dlg = fid.FontPackInspectorDialog(sources=[("tiny", _tiny_pack())])
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._tabs.count(), 1)
        self.assertEqual(dlg._tabs.tabText(0), "tiny")

    def test_mode_switch_rerenders(self):
        dlg = fid.FontPackInspectorDialog(sources=[("tiny", _tiny_pack())])
        self.addCleanup(dlg.deleteLater)
        tab = dlg._tabs.currentWidget()
        self.assertEqual(tab._built_key[0], "glyph")      # built on show
        n_cells = tab.cell_count()
        self.assertGreater(n_cells, 0)
        dlg._mode_combo.setCurrentIndex(1)                # keycap
        self.assertEqual(tab._built_key[0], "keycap")
        self.assertEqual(tab.cell_count(), n_cells)       # same glyphs, re-rendered

    def test_hide_empty_reduces_cells(self):
        dlg = fid.FontPackInspectorDialog(sources=[("tiny", _tiny_pack())])
        self.addCleanup(dlg.deleteLater)
        tab = dlg._tabs.currentWidget()
        full = tab.cell_count()
        tab._hide_empty.setChecked(True)
        self.assertLessEqual(tab.cell_count(), full)

    def test_double_click_edit_signal(self):
        # Test the tab's signal in isolation — going through the dialog would also
        # fire its real handler, which opens a *modal* extend dialog (exec_) and
        # would block the test.  A plain cell (no stack) edits the winner wherever
        # clicked.
        from PyQt5.QtCore import QPoint
        tab = fid._BundleTab("tiny", _tiny_pack())
        self.addCleanup(tab.deleteLater)
        tab.set_mode("glyph")
        got = []
        tab.edit_requested.connect(lambda font, cp: got.append((font.global_index, cp)))
        idx = tab._model.index(0, 0)
        r = tab._view.visualRect(idx)
        tab._edit_at(idx, r.center())                    # simulate double-click on item 0
        self.assertEqual(got, [(idx.data(fid._FONT_ROLE).global_index,
                                idx.data(fid._CP_ROLE))])

    def test_stack_corner_edits_overdrawn(self):
        # a stacked cell: clicking the centre edits the winner; the bottom-right
        # stack corner edits the overdrawn glyph.
        def g(off, w, h):
            return dict(bitmapOffset=off, width=w, height=h, xAdvance=w + 1,
                        xOffset=0, yOffset=0)
        a = fpr.PackFont("A", b"\x80", [g(0, 1, 1)], 0x41, 0x41, 12, global_index=2)
        b = fpr.PackFont("B", b"\x80", [g(0, 1, 1)], 0x41, 0x41, 12, global_index=5)
        tab = fid._BundleTab("B", fpr.Pack(1, 0, 1, 0, 0, True, [b]), all_fonts=[a, b])
        self.addCleanup(tab.deleteLater)
        tab.set_mode("glyph")
        got = []
        tab.edit_requested.connect(lambda font, cp: got.append(font.global_index))
        idx = tab._model.index(0, 0)                     # the 0x41 cell
        r = tab._view.visualRect(idx)
        from PyQt5.QtCore import QPoint
        tab._edit_at(idx, r.center())                    # winner (A, g2)
        tab._edit_at(idx, QPoint(r.right() - 1, r.bottom() - 1))   # stack corner (B, g5)
        self.assertEqual(got, [2, 5])

    def test_peek_fallback_without_source(self):
        # Peek with no shipped settings / no cached source must not crash and must
        # render no previews — the empty cell stays a placeholder.  Isolate the font
        # cache so a font cached on this machine can't satisfy the catalog fallback.
        import tempfile
        from unittest.mock import patch
        from polyhost.services import font_downloader as fdl
        tab = fid._BundleTab("emptytest", _pack_with_empty())
        self.addCleanup(tab.deleteLater)
        tab.set_mode("glyph")
        full = tab.cell_count()
        with patch.object(fdl, "default_cache_dir", return_value=tempfile.mkdtemp()):
            tab._peek.setChecked(True)
            tab._drain_peek()                           # run the lazy pass synchronously
        self.assertEqual(tab.cell_count(), full)        # same cells, no crash
        self.assertEqual(tab._last_peek_count, 0)       # nothing rendered from source

    def test_peek_pixmap_none_without_settings(self):
        import tempfile
        from unittest.mock import patch
        from polyhost.services import font_downloader as fdl
        tab = fid._BundleTab("emptytest", _pack_with_empty())
        self.addCleanup(tab.deleteLater)
        font = tab._pack.fonts[0]
        with patch.object(fdl, "default_cache_dir", return_value=tempfile.mkdtemp()):
            self.assertIsNone(tab._peek_pixmap(font, 0x42, 20, 20, 2))   # no source cached

    @unittest.skipUnless(_FONTGEN and _FONT, "needs fontgen deps + a system TTF")
    def test_peek_renders_preview_with_source(self):
        from unittest.mock import patch
        from polyhost.services import fontpack_extend as ext
        from polyhost.services import font_downloader as fdl
        tab = fid._BundleTab("emptytest", _pack_with_empty())
        self.addCleanup(tab.deleteLater)
        tab.set_mode("glyph")
        gi = str(tab._pack.fonts[0].global_index)
        # point the empty font's settings at the system font (cp 0x42 'B' exists there)
        with patch.object(ext, "load_render_settings",
                          return_value={gi: {"size": 24, "source_file": os.path.basename(_FONT)}}), \
             patch.object(fdl, "default_cache_dir", return_value=os.path.dirname(_FONT)):
            tab._settings_map = None                 # force reload via patched loader
            tab._peek.setChecked(True)
            tab._drain_peek()
        self.assertGreaterEqual(tab._last_peek_count, 1)

    @unittest.skipUnless(_FONTGEN and _FONT, "needs fontgen deps + a system TTF")
    def test_peek_falls_back_to_other_pack_font(self):
        from unittest.mock import patch
        from polyhost.services import fontpack_extend as ext
        from polyhost.services import font_downloader as fdl
        pack = _pack_with_empty()                       # one font, gidx 0, 0x42 empty
        # a font from another bundle (gidx 99) whose source has 'B' (0x42)
        other = fpr.PackFont("X", b"", [dict(bitmapOffset=0, width=0, height=0,
                                             xAdvance=0, xOffset=0, yOffset=0)],
                             0x42, 0x42, 12, global_index=99)
        tab = fid._BundleTab("multi", pack, all_fonts=[pack.fonts[0], other])
        self.addCleanup(tab.deleteLater)
        tab.set_mode("glyph")
        with patch.object(ext, "load_render_settings", return_value={
                "0": {"size": 24, "source_file": "missing-font.ttf"},
                "99": {"size": 24, "source_file": os.path.basename(_FONT)}}), \
             patch.object(fdl, "default_cache_dir", return_value=os.path.dirname(_FONT)):
            tab._settings_map = None
            res = tab._peek_pixmap(pack.fonts[0], 0x42, 20, 20, 2)
        self.assertIsNotNone(res)
        self.assertEqual(res[1], os.path.basename(_FONT))   # rendered from gidx-99 source

    def test_peek_candidates_defer_colour_sources(self):
        # cross-bundle fallback (sources not in-range for the cp) should try
        # monochrome before colour, so a symbol that also exists in NotoColorEmoji
        # isn't previewed as a dithered colour emoji.  (Ordering only — file existence.)
        import tempfile
        from unittest.mock import patch
        from polyhost.services import fontpack_extend as ext
        from polyhost.services import font_downloader as fdl
        tmp = tempfile.mkdtemp()
        for fn in ("mono-a.ttf", "mono-b.ttf", "color.ttf"):
            open(os.path.join(tmp, fn), "wb").close()

        def _f(gi, first, last):
            return fpr.PackFont(f"f{gi}", b"", [dict(bitmapOffset=0, width=0, height=0,
                                                     xAdvance=0, xOffset=0, yOffset=0)],
                                first, last, 12, global_index=gi)
        # own slot owns 0x41; the others are elsewhere (not in-range for 0x41)
        all_fonts = [_f(0, 0x41, 0x41), _f(3, 0x100, 0x100),
                     _f(5, 0x101, 0x101), _f(9, 0x102, 0x102)]
        smap = {
            "0": {"source_file": "own-missing.ttf"},                 # own slot, uncached
            "5": {"source_file": "color.ttf", "bits": 32, "grayscale": True},  # colour, low gidx
            "9": {"source_file": "mono-b.ttf"},                      # mono, higher gidx
            "3": {"source_file": "mono-a.ttf"},                      # mono, lower gidx
        }
        tab = fid._BundleTab("multi", _pack_with_empty(), all_fonts=all_fonts)
        self.addCleanup(tab.deleteLater)
        with patch.object(ext, "load_render_settings", return_value=smap), \
             patch.object(fdl, "default_cache_dir", return_value=tmp):
            tab._settings_map = None
            files = [c[2] for c in tab._peek_candidates(tab._pack.fonts[0], 0x41)]
        self.assertEqual(files, ["mono-a.ttf", "mono-b.ttf", "color.ttf"])

    def test_peek_candidates_defer_emoji_for_symbol_slot(self):
        # a non-emoji (symbol) slot must prefer a symbol source over an emoji source —
        # even a low-gidx, in-bundle, in-range b/w NotoEmoji.  (Field report: a symbol
        # cp that also exists in NotoEmoji previewed as the emoji, not the symbol.)
        import tempfile
        from unittest.mock import patch
        from polyhost.services import fontpack_extend as ext
        from polyhost.services import font_downloader as fdl
        tmp = tempfile.mkdtemp()
        for fn in ("NotoEmoji-Medium.ttf", "NotoSansSymbols-Regular.ttf"):
            open(os.path.join(tmp, fn), "wb").close()

        def _f(gi, first, last):
            return fpr.PackFont(f"f{gi}", b"", [dict(bitmapOffset=0, width=0, height=0,
                                                     xAdvance=0, xOffset=0, yOffset=0)],
                                first, last, 12, global_index=gi)
        # own slot (symbol, gidx0) owns 0x41; a b/w emoji at low gidx2 is in this
        # bundle AND in-range for 0x41; the symbol source is resident-only + out-of-range.
        all_fonts = [_f(0, 0x41, 0x41), _f(2, 0x41, 0x41)]
        smap = {
            "0": {"source_file": "own-missing.ttf"},                 # own slot, uncached
            "2": {"source_file": "NotoEmoji-Medium.ttf"},            # b/w emoji, low gidx, in-range
            "7": {"source_file": "NotoSansSymbols-Regular.ttf"},     # symbol, resident-only
        }
        pack = fpr.Pack(1, 0, 1, 0, 0, True, [all_fonts[0], all_fonts[1]])
        tab = fid._BundleTab("symbol", pack, all_fonts=all_fonts)
        self.addCleanup(tab.deleteLater)
        with patch.object(ext, "load_render_settings", return_value=smap), \
             patch.object(fdl, "default_cache_dir", return_value=tmp):
            tab._settings_map = None
            files = [c[2] for c in tab._peek_candidates(pack.fonts[0], 0x41)]
        # symbol source first, emoji last — despite the emoji's lower gidx / in-range
        self.assertEqual(files, ["NotoSansSymbols-Regular.ttf", "NotoEmoji-Medium.ttf"])

    def test_peek_candidates_keep_emoji_for_emoji_slot(self):
        # for an emoji slot the deferral is a no-op: the in-range/lower-gidx order
        # stands (own emoji font keeps previewing emoji, not a stray symbol source).
        import tempfile
        from unittest.mock import patch
        from polyhost.services import fontpack_extend as ext
        from polyhost.services import font_downloader as fdl
        tmp = tempfile.mkdtemp()
        for fn in ("NotoColorEmoji-Regular.ttf", "NotoSansSymbols-Regular.ttf"):
            open(os.path.join(tmp, fn), "wb").close()

        def _f(gi, first, last):
            return fpr.PackFont(f"f{gi}", b"", [dict(bitmapOffset=0, width=0, height=0,
                                                     xAdvance=0, xOffset=0, yOffset=0)],
                                first, last, 12, global_index=gi)
        all_fonts = [_f(0, 0x1F600, 0x1F600), _f(4, 0x1F600, 0x1F600)]
        smap = {
            "0": {"source_file": "NotoEmoji-own.ttf", "bits": 32, "grayscale": True},  # own emoji slot, uncached
            "4": {"source_file": "NotoColorEmoji-Regular.ttf", "bits": 32, "grayscale": True},
            "7": {"source_file": "NotoSansSymbols-Regular.ttf"},     # symbol, resident-only
        }
        pack = fpr.Pack(1, 0, 1, 0, 0, True, [all_fonts[0], all_fonts[1]])
        tab = fid._BundleTab("emoji", pack, all_fonts=all_fonts)
        self.addCleanup(tab.deleteLater)
        with patch.object(ext, "load_render_settings", return_value=smap), \
             patch.object(fdl, "default_cache_dir", return_value=tmp):
            tab._settings_map = None
            files = [c[2] for c in tab._peek_candidates(pack.fonts[0], 0x1F600)]
        # emoji (in-range, in-bundle) ahead of the symbol fallback — not deferred
        self.assertEqual(files, ["NotoColorEmoji-Regular.ttf", "NotoSansSymbols-Regular.ttf"])

    def test_peek_candidates_include_catalog_fallback(self):
        # a downloaded catalog font that no bundle uses (e.g. NotoSansMath) must still
        # be a peek candidate (ranked last), so it's usable with no code change.
        import tempfile
        from unittest.mock import patch
        from polyhost.services import fontpack_extend as ext
        from polyhost.services import font_downloader as fdl
        tmp = tempfile.mkdtemp()
        open(os.path.join(tmp, "NotoSansMath-Regular.ttf"), "wb").close()
        smap = {"0": {"source_file": "own-missing.ttf"}}     # own slot, uncached
        math = fdl.NotoFont("Noto Sans Math", "file:///x", "NotoSansMath-Regular.ttf")
        tab = fid._BundleTab("symbol", _pack_with_empty())
        self.addCleanup(tab.deleteLater)
        with patch.object(ext, "load_render_settings", return_value=smap), \
             patch.object(fdl, "load_catalog", return_value=[math]), \
             patch.object(fdl, "default_cache_dir", return_value=tmp):
            tab._settings_map = None
            tab._catalog_files = None
            files = [c[2] for c in tab._peek_candidates(tab._pack.fonts[0], 0x2200)]
        self.assertIn("NotoSansMath-Regular.ttf", files)     # offered though in no bundle

    def test_peek_candidates_prefer_in_range(self):
        # a source whose font range owns the cp beats a lower-gidx out-of-range one
        import tempfile
        from unittest.mock import patch
        from polyhost.services import fontpack_extend as ext
        from polyhost.services import font_downloader as fdl
        tmp = tempfile.mkdtemp()
        for fn in ("low.ttf", "inrange.ttf"):
            open(os.path.join(tmp, fn), "wb").close()

        def _f(gi, first, last):
            return fpr.PackFont(f"f{gi}", b"", [dict(bitmapOffset=0, width=0, height=0,
                                                     xAdvance=0, xOffset=0, yOffset=0)],
                                first, last, 12, global_index=gi)
        all_fonts = [_f(2, 0x100, 0x100), _f(8, 0x41, 0x41)]   # gidx8 owns 0x41
        smap = {"2": {"source_file": "low.ttf"}, "8": {"source_file": "inrange.ttf"}}
        tab = fid._BundleTab("multi", _pack_with_empty(), all_fonts=all_fonts)
        self.addCleanup(tab.deleteLater)
        with patch.object(ext, "load_render_settings", return_value=smap), \
             patch.object(fdl, "default_cache_dir", return_value=tmp):
            tab._settings_map = None
            files = [c[2] for c in tab._peek_candidates(tab._pack.fonts[0], 0x41)]
        self.assertEqual(files, ["inrange.ttf", "low.ttf"])

    def test_stack_and_covered_representation(self):
        # one cell per cp (deduped). 0x41: both A and B have it → winner A (lower gidx)
        # with B overdrawn beneath (stack). 0x42: only B. 0x43: only A (another bundle).
        def g(off, w, h):
            return dict(bitmapOffset=off, width=w, height=h, xAdvance=w + 1,
                        xOffset=0, yOffset=0)
        empty = dict(bitmapOffset=0, width=0, height=0, xAdvance=0, xOffset=0, yOffset=0)
        fontA = fpr.PackFont("A", b"\x80\x80", [g(0, 1, 1), empty, g(1, 1, 1)],
                             0x41, 0x43, 12, global_index=2)
        fontB = fpr.PackFont("B", b"\x80\x80", [g(0, 1, 1), g(1, 1, 1), empty],
                             0x41, 0x43, 12, global_index=5)
        packB = fpr.Pack(1, 0, 1, 0, 0, True, [fontB])
        tab = fid._BundleTab("B", packB, all_fonts=[fontA, fontB])
        self.addCleanup(tab.deleteLater)
        tab.set_mode("glyph")
        items = {tab._model.item(i).data(fid._CP_ROLE): tab._model.item(i)
                 for i in range(tab._model.rowCount())}
        self.assertEqual(set(items), {0x41, 0x42, 0x43})            # deduped, continuous
        # 0x41 — winner A, B overdrawn (stack corner edits B)
        self.assertEqual(items[0x41].data(fid._FONT_ROLE).global_index, 2)
        self.assertEqual(items[0x41].data(fid._SHADOW_ROLE).global_index, 5)
        self.assertIn("overdrawn", items[0x41].toolTip())
        # 0x42 — only B, no stack
        self.assertEqual(items[0x42].data(fid._FONT_ROLE).global_index, 5)
        self.assertIsNone(items[0x42].data(fid._SHADOW_ROLE))
        self.assertNotIn("overdrawn", items[0x42].toolTip())
        # 0x43 — only A, borrowed from another bundle, no stack
        self.assertEqual(items[0x43].data(fid._FONT_ROLE).global_index, 2)
        self.assertIsNone(items[0x43].data(fid._SHADOW_ROLE))
        self.assertIn("another bundle", items[0x43].toolTip())

    def test_peek_candidates_include_resident_only_source(self):
        # a source used only by a resident (non-bundle) font — present in the
        # manifest but with no font object — must still be a peek candidate
        # (regression: NotoSansSymbols fills symbol gaps but is resident-only).
        import tempfile
        from unittest.mock import patch
        from polyhost.services import fontpack_extend as ext
        from polyhost.services import font_downloader as fdl
        tmp = tempfile.mkdtemp()
        open(os.path.join(tmp, "resident.ttf"), "wb").close()
        smap = {"0": {"source_file": "own-missing.ttf"},        # own slot, uncached
                "1": {"source_file": "resident.ttf"}}           # resident-only, no font obj
        tab = fid._BundleTab("b", _pack_with_empty())           # all_fonts = [gidx0] only
        self.addCleanup(tab.deleteLater)
        with patch.object(ext, "load_render_settings", return_value=smap), \
             patch.object(fdl, "default_cache_dir", return_value=tmp):
            tab._settings_map = None
            files = [c[2] for c in tab._peek_candidates(tab._pack.fonts[0], 0x42)]
        self.assertIn("resident.ttf", files)

    def test_error_source_does_not_crash(self):
        # a decode failure becomes a labelled tab, never a dead window
        dlg = fid.FontPackInspectorDialog(sources=[("broken", ValueError("bad"))])
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._tabs.count(), 1)

    def test_open_plyf_adds_tab(self):
        # loading a saved .plyf adds a tab named after the file, and folds it into
        # the Extend sources + the merged all_fonts (so it's investigable).
        import tempfile
        from unittest.mock import patch
        from PyQt5.QtWidgets import QFileDialog, QMessageBox

        def g(off, w, h):
            return dict(bitmapOffset=off, width=w, height=h, xAdvance=w + 1,
                        xOffset=0, yOffset=0)
        font = fpr.PackFont("x", b"\x80", [g(0, 1, 1)], 0x41, 0x41, 12, global_index=200)
        data = fpr.encode_pack([font], content_version=7)
        path = os.path.join(tempfile.mkdtemp(), "my-symbols.plyf")
        with open(path, "wb") as f:
            f.write(data)

        dlg = fid.FontPackInspectorDialog(sources=[("tiny", _tiny_pack())])
        self.addCleanup(dlg.deleteLater)
        before = dlg._tabs.count()
        with patch.object(QFileDialog, "getOpenFileName", return_value=(path, "")), \
             patch.object(QMessageBox, "information", return_value=None):
            dlg._open_file()
        self.assertEqual(dlg._tabs.count(), before + 1)
        self.assertEqual(dlg._tabs.tabText(before), "my-symbols")   # named after the file
        self.assertIn("my-symbols", [l for l, _ in dlg._sources])   # now an Extend source
        self.assertTrue(any(f.global_index == 200 for f in dlg._all_fonts))

    def test_open_plyf_from_empty_start(self):
        # with no shipped bundles, the window still opens; Open populates it
        import tempfile
        from unittest.mock import patch
        from PyQt5.QtWidgets import QFileDialog, QMessageBox

        def g(off, w, h):
            return dict(bitmapOffset=off, width=w, height=h, xAdvance=w + 1,
                        xOffset=0, yOffset=0)
        font = fpr.PackFont("x", b"\x80", [g(0, 1, 1)], 0x41, 0x41, 12, global_index=1)
        path = os.path.join(tempfile.mkdtemp(), "saved.plyf")
        with open(path, "wb") as f:
            f.write(fpr.encode_pack([font], content_version=3))

        dlg = fid.FontPackInspectorDialog(sources=[])
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._tabs.count(), 0)
        self.assertTrue(dlg._empty_note.isVisibleTo(dlg))
        self.assertFalse(dlg._edit_btn.isEnabled())
        with patch.object(QFileDialog, "getOpenFileName", return_value=(path, "")), \
             patch.object(QMessageBox, "information", return_value=None):
            dlg._open_file()
        self.assertEqual(dlg._tabs.count(), 1)
        self.assertTrue(dlg._edit_btn.isEnabled())
        self.assertFalse(dlg._empty_note.isVisibleTo(dlg))

    def test_open_plyf_bad_file_reports(self):
        import tempfile
        from unittest.mock import patch
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        path = os.path.join(tempfile.mkdtemp(), "junk.plyf")
        with open(path, "wb") as f:
            f.write(b"not a font pack")
        dlg = fid.FontPackInspectorDialog(sources=[("tiny", _tiny_pack())])
        self.addCleanup(dlg.deleteLater)
        before = dlg._tabs.count()
        seen = {}
        with patch.object(QFileDialog, "getOpenFileName", return_value=(path, "")), \
             patch.object(QMessageBox, "critical",
                          side_effect=lambda *a, **k: seen.update(msg=a)):
            dlg._open_file()
        self.assertEqual(dlg._tabs.count(), before)      # no tab added on failure
        self.assertIn("msg", seen)                        # error surfaced

    def test_commit_edit_accumulates_and_marks_tab(self):
        # an editor result (whole-font add) accumulates into the inspector working copy
        base = fpr.PackFont("b", b"\x80", [_g(0, 1, 1)], 0x41, 0x41, 12, global_index=5)
        pack = fpr.Pack(1, 3, 1, 0, 0, True, [base])
        dlg = fid.FontPackInspectorDialog(sources=[("sym", pack)])
        self.addCleanup(dlg.deleteLater)
        self.assertFalse(dlg._saveas_btn.isEnabled())
        newf = fpr.PackFont("n", b"\x80", [_g(0, 1, 1)], 0x2600, 0x2600, 12, global_index=9)
        dlg._commit_edit("sym", newf, None)
        self.assertEqual(len(dlg._pending[0]), 1)
        self.assertEqual(len(dlg._work[0]), 2)                 # font added
        self.assertTrue(dlg._saveas_btn.isEnabled())
        self.assertTrue(dlg._tabs.tabText(0).startswith("●")) # pending marker

    def test_commit_edit_shows_in_tab_with_border(self):
        # after an edit commits, the tab re-renders from the working copy and marks
        # the edited cp as modified (border) — so the new version is visible
        base = fpr.PackFont("b", b"\x80\x80", [_g(0, 1, 1), _g(1, 1, 1)],
                            0x41, 0x42, 12, global_index=5)
        pack = fpr.Pack(1, 0, 1, 0, 0, True, [base])
        dlg = fid.FontPackInspectorDialog(sources=[("sym", pack)])
        self.addCleanup(dlg.deleteLater)
        tab = dlg._tabs.widget(0)
        newf = fpr.PackFont("n", b"\xC0", [_g(0, 2, 1)], 0x41, 0x41, 12, global_index=5)
        dlg._commit_edit("sym", newf, {"global_index": 5, "cp": 0x41})
        self.assertIn(0x41, tab._modified)                      # edited cp marked
        self.assertEqual(tab._pack.fonts[0].glyphs[0]["width"], 2)   # working copy shown
        # the modified cell carries a tooltip note
        tips = {tab._model.item(i).data(fid._CP_ROLE): tab._model.item(i).toolTip()
                for i in range(tab._model.rowCount())}
        self.assertIn("edited", tips[0x41])

    def test_edit_propagates_to_other_tabs(self):
        # bundle A draws U+0041; bundle B is empty there (so B's tab shows it cyan,
        # "covered by A"). Editing A's glyph must update B's merged view so its
        # covered cell reflects the new glyph — cross-tab propagation.
        a = fpr.PackFont("a", b"\x80", [_g(0, 1, 1)], 0x41, 0x41, 12, global_index=5)
        b = fpr.PackFont("b", b"\x00", [_g(0, 0, 0)], 0x41, 0x41, 12, global_index=9)
        dlg = fid.FontPackInspectorDialog(sources=[("A", fpr.Pack(1, 0, 1, 0, 0, True, [a])),
                                                   ("B", fpr.Pack(1, 0, 1, 0, 0, True, [b]))])
        self.addCleanup(dlg.deleteLater)
        tabB = dlg._tabs.widget(1)
        self.assertEqual(tabB._winners().get(0x41).global_index, 5)   # A wins for B
        newf = fpr.PackFont("a2", b"\xC0", [_g(0, 2, 1)], 0x41, 0x41, 12, global_index=5)
        dlg._commit_edit("A", newf, {"global_index": 5, "cp": 0x41})
        win = tabB._winners().get(0x41)                # B's merged view recomputed
        self.assertEqual(win.global_index, 5)
        self.assertEqual(win.glyphs[0]["width"], 2)    # the edited bitmap propagated to B

    def test_commit_edit_replaces_glyph_in_edit_mode(self):
        base = fpr.PackFont("b", b"\x80\x80", [_g(0, 1, 1), _g(1, 1, 1)],
                            0x41, 0x42, 12, global_index=5)
        pack = fpr.Pack(1, 0, 1, 0, 0, True, [base])
        dlg = fid.FontPackInspectorDialog(sources=[("sym", pack)])
        self.addCleanup(dlg.deleteLater)
        newf = fpr.PackFont("n", b"\xC0", [_g(0, 2, 1)], 0x41, 0x41, 12, global_index=5)
        dlg._commit_edit("sym", newf, {"global_index": 5, "cp": 0x41})
        self.assertEqual(len(dlg._work[0]), 1)                 # replaced in place, not added
        self.assertEqual(dlg._work[0][0].glyphs[0]["width"], 2)

    def test_save_dialog_bytes_version_and_discard(self):
        from unittest.mock import patch
        from PyQt5.QtWidgets import QMessageBox
        f = fpr.PackFont("n", b"\x80", [_g(0, 1, 1)], 0x41, 0x41, 12, global_index=9)
        base = fpr.Pack(1, 4, 0, 0, 0, True, [])               # current content v4
        dlg = fid.FontPackSaveDialog("sym", base, [f], ["edit U+0041 (g9)"])
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._version.value(), 5)              # default base+1
        pk = fpr.decode_pack(dlg._bytes())
        self.assertTrue(pk.crc_ok)
        self.assertEqual(pk.content_version, 5)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            dlg._discard()
        self.assertTrue(dlg.discarded)

    def test_save_dialog_flash_callback(self):
        from unittest.mock import patch
        from PyQt5.QtWidgets import QMessageBox
        f = fpr.PackFont("n", b"\x80", [_g(0, 1, 1)], 0x41, 0x41, 12, global_index=9)
        base = fpr.Pack(1, 2, 0, 0, 0, True, [])
        got = {}
        dlg = fid.FontPackSaveDialog("sym", base, [f], ["x"],
                                     flash_cb=lambda i, d: got.update(i=i, d=d),
                                     bundle_index=3)
        self.addCleanup(dlg.deleteLater)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
             patch.object(QMessageBox, "information", return_value=None):
            dlg._flash()
        self.assertEqual(got["i"], 3)
        self.assertEqual(got["d"], dlg._bytes())

    def test_shipped_bundles_load(self):
        srcs = fid.load_shipped_packs()
        if not srcs:
            self.skipTest("no shipped bundles present")
        dlg = fid.FontPackInspectorDialog(sources=srcs)
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._tabs.count(), len(srcs))
        # every shipped bundle decodes to a real Pack (no error tabs)
        self.assertTrue(all(isinstance(p, fpr.Pack) for _, p in srcs))


if __name__ == "__main__":
    unittest.main()
