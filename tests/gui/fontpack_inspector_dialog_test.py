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


def _two_font_pack():
    """Two fonts: A (gidx 0) empty at 0x41; B (gidx 1) present at 0x100 — for
    exercising peek falling back to another font's source in the same bundle."""
    a = fpr.PackFont("A", b"", [dict(bitmapOffset=0, width=0, height=0,
                                     xAdvance=0, xOffset=0, yOffset=0)],
                     0x41, 0x41, 12, global_index=0)
    b = fpr.PackFont("B", bytes([0xC0]), [dict(bitmapOffset=0, width=2, height=2,
                                               xAdvance=3, xOffset=0, yOffset=-2)],
                     0x100, 0x100, 12, global_index=1)
    return fpr.decode_pack(fpr.encode_pack([a, b], 1), name_hint="multi")


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
        # would block the test.
        tab = fid._BundleTab("tiny", _tiny_pack())
        self.addCleanup(tab.deleteLater)
        tab.set_mode("glyph")
        got = []
        tab.edit_requested.connect(lambda font, cp: got.append(cp))
        idx = tab._model.index(0, 0)
        tab._on_double(idx)                               # simulate double-click on item 0
        self.assertEqual(got, [idx.data(fid._CP_ROLE)])

    def test_peek_fallback_without_source(self):
        # Peek with no shipped settings / no cached source must not crash and must
        # render no previews — the empty cell stays a placeholder.
        tab = fid._BundleTab("emptytest", _pack_with_empty())
        self.addCleanup(tab.deleteLater)
        tab.set_mode("glyph")
        full = tab.cell_count()
        tab._peek.setChecked(True)
        tab._drain_peek()                               # run the lazy pass synchronously
        self.assertEqual(tab.cell_count(), full)        # same cells, no crash
        self.assertEqual(tab._last_peek_count, 0)       # nothing rendered from source

    def test_peek_pixmap_none_without_settings(self):
        tab = fid._BundleTab("emptytest", _pack_with_empty())
        self.addCleanup(tab.deleteLater)
        font = tab._pack.fonts[0]
        self.assertIsNone(tab._peek_pixmap(font, 0x42, 20, 20, 2))   # no settings entry

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
    def test_peek_falls_back_to_other_bundle_font(self):
        from unittest.mock import patch
        from polyhost.services import fontpack_extend as ext
        from polyhost.services import font_downloader as fdl
        pack = _two_font_pack()
        tab = fid._BundleTab("multi", pack)
        self.addCleanup(tab.deleteLater)
        tab.set_mode("glyph")
        # font A's own source is missing/uncached; B's source is the system font,
        # which has 'A' (0x41) — so peeking A's empty 0x41 should come from B's source.
        with patch.object(ext, "load_render_settings", return_value={
                "0": {"size": 24, "source_file": "missing-font.ttf"},
                "1": {"size": 24, "source_file": os.path.basename(_FONT)}}), \
             patch.object(fdl, "default_cache_dir", return_value=os.path.dirname(_FONT)):
            tab._settings_map = None
            res = tab._peek_pixmap(pack.fonts[0], 0x41, 20, 20, 2)
        self.assertIsNotNone(res)
        self.assertEqual(res[1], os.path.basename(_FONT))   # rendered from B's source

    def test_error_source_does_not_crash(self):
        # a decode failure becomes a labelled tab, never a dead window
        dlg = fid.FontPackInspectorDialog(sources=[("broken", ValueError("bad"))])
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg._tabs.count(), 1)

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
