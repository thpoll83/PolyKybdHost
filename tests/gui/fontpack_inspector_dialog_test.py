"""FontPackInspectorDialog — constructs over the shipped bundles and a synthetic
source.  Needs only PyQt5 (the dialog doesn't import host.py / pynput), so it runs
under the offscreen Qt platform with no X server.
"""
import os
import struct
import binascii
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui import fontpack_inspector_dialog as fid
    from polyhost.services import fontpack_reader as fpr
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e


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
        self.assertEqual(tab._rendered_mode, "glyph")     # rendered on show
        dlg._mode_combo.setCurrentIndex(1)                # keycap
        self.assertEqual(tab._rendered_mode, "keycap")
        self.assertIsNotNone(tab._base_pixmap)

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
