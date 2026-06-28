"""Tests for polyhost.services.fontpack_reader — the offline PlyF body decoder.

Two layers: a synthetic round-trip (build a pack with the same struct layout the
firmware serializer uses, decode it back, assert glyphs/bitmaps survive), and a
smoke test over the *shipped* res/fontpack/*.plyf bundles (decode cleanly, CRCs
pass, sizes reconcile with bundles.json).  Pure stdlib — no hardware, no PIL.
"""
import binascii
import json
import os
import struct
import unittest

from polyhost.services import fontpack_reader as fr

RES = os.path.join(os.path.dirname(__file__), "..", "..", "polyhost", "res", "fontpack")


def _load_bundles():
    with open(os.path.join(RES, "bundles.json")) as f:
        return json.load(f)["bundles"]


def _build_pack(fonts, content_version=0):
    """Serialize fonts the way fonts/fontpack.py does (header, table, glyph
    arrays, bitmap blobs; 4-aligned).  `fonts` = list of dicts with
    first/last/yadv/glyphs(list of 6-tuples)/bitmap(bytes)/gidx."""
    n = len(fonts)
    table_off = fr.HEADER_SIZE
    cur = table_off + n * fr.FONT_REC_SIZE
    glyph_offs, glyph_blocks = [], []
    for f in fonts:
        glyph_offs.append(cur)
        blob = b"".join(struct.pack(fr._GLYPH_FMT, *g) for g in f["glyphs"])
        glyph_blocks.append(blob)
        cur = (cur + len(blob) + 3) & ~3
    bitmap_offs, bitmap_blocks = [], []
    for f in fonts:
        bitmap_offs.append(cur)
        bitmap_blocks.append(f["bitmap"])
        cur = (cur + len(f["bitmap"]) + 3) & ~3
    total = cur
    table = b"".join(struct.pack(fr._FONT_FMT, bitmap_offs[i], glyph_offs[i],
                                 f["first"], f["last"], f["yadv"], f.get("gidx", 0))
                     for i, f in enumerate(fonts))
    body = bytearray(total - fr.HEADER_SIZE)

    def place(off, blob):
        body[off - fr.HEADER_SIZE:off - fr.HEADER_SIZE + len(blob)] = blob
    place(table_off, table)
    for off, blob in zip(glyph_offs, glyph_blocks):
        place(off, blob)
    for off, blob in zip(bitmap_offs, bitmap_blocks):
        place(off, blob)
    crc = binascii.crc32(bytes(body)) & 0xFFFFFFFF
    header = struct.pack(fr._HEADER_FMT, fr.MAGIC, fr.ABI_VERSION, 0, content_version,
                         n, table_off, total, crc, 0)
    return header + bytes(body)


class RoundTripTest(unittest.TestCase):
    def test_two_font_pack(self):
        data = _build_pack([
            {"first": 0x41, "last": 0x42, "yadv": 12, "gidx": 7,
             "glyphs": [(0, 3, 4, 5, -1, -7), (2, 6, 8, 9, 0, -3)],
             "bitmap": bytes([0x12, 0x34, 0xFF, 0x00])},
            {"first": 0x4E2D, "last": 0x4E2D, "yadv": 43, "gidx": 3,
             "glyphs": [(0, 2, 2, 4, 0, -2)],
             "bitmap": bytes([0b11000000, 0b01000000])},
        ], content_version=9)
        pack = fr.decode_pack(data, name_hint="t")
        self.assertTrue(pack.crc_ok)
        self.assertEqual(pack.content_version, 9)
        self.assertEqual(pack.font_count, 2)
        self.assertEqual(pack.codepoint_count(), 3)
        a, b = pack.fonts
        self.assertEqual((a.first, a.last, a.yAdvance, a.global_index), (0x41, 0x42, 12, 7))
        self.assertEqual(a.glyphs[0], dict(bitmapOffset=0, width=3, height=4,
                                           xAdvance=5, xOffset=-1, yOffset=-7))
        self.assertEqual(a.bitmap[:4], bytes([0x12, 0x34, 0xFF, 0x00]))
        self.assertTrue(b.covers(0x4E2D))
        # merge orders by global index (3 before 7)
        merged = fr.merge_fonts([pack])
        self.assertEqual([f.global_index for f in merged], [3, 7])

    def test_encode_roundtrip(self):
        data = _build_pack([
            {"first": 0x41, "last": 0x42, "yadv": 12, "gidx": 7,
             "glyphs": [(0, 3, 4, 5, -1, -7), (2, 6, 8, 9, 0, -3)],
             "bitmap": bytes([0x12, 0x34, 0xFF, 0x00, 0xAA, 0x55, 0x0F, 0xF0])},
            {"first": 0x4E2D, "last": 0x4E2D, "yadv": 43, "gidx": 3,
             "glyphs": [(0, 2, 2, 4, 0, -2)], "bitmap": bytes([0xC0])},
        ], content_version=9)
        pack = fr.decode_pack(data)
        re_enc = fr.encode_pack(pack.fonts, pack.content_version)
        self.assertEqual(re_enc, data, "encode(decode(x)) != x")

    def test_splice_replace(self):
        pack = fr.decode_pack(_build_pack([
            {"first": 0x41, "last": 0x41, "yadv": 8, "gidx": 2,
             "glyphs": [(0, 1, 1, 2, 0, 0)], "bitmap": bytes([0x80])},
            {"first": 0x42, "last": 0x42, "yadv": 8, "gidx": 5,
             "glyphs": [(0, 1, 1, 2, 0, 0)], "bitmap": bytes([0x80])},
        ]))
        repl = fr.PackFont("new", bytes([0x80]),
                           [dict(bitmapOffset=0, width=1, height=1, xAdvance=3,
                                 xOffset=0, yOffset=0)], 0x43, 0x43, 8, global_index=2)
        out = fr.splice_font(pack, repl)
        self.assertEqual(len(out), 2)                       # replaced, not added
        self.assertEqual([f.global_index for f in out], [2, 5])
        self.assertEqual(out[0].first, 0x43)               # the replacement

    def test_splice_insert_in_order(self):
        pack = fr.decode_pack(_build_pack([
            {"first": 0x41, "last": 0x41, "yadv": 8, "gidx": 2,
             "glyphs": [(0, 1, 1, 2, 0, 0)], "bitmap": bytes([0x80])},
            {"first": 0x42, "last": 0x42, "yadv": 8, "gidx": 8,
             "glyphs": [(0, 1, 1, 2, 0, 0)], "bitmap": bytes([0x80])},
        ]))
        new = fr.PackFont("new", bytes([0x80]),
                          [dict(bitmapOffset=0, width=1, height=1, xAdvance=3,
                                xOffset=0, yOffset=0)], 0x43, 0x43, 8, global_index=5)
        out = fr.splice_font(pack, new)
        self.assertEqual([f.global_index for f in out], [2, 5, 8])   # inserted in order

    def test_replace_glyph_preserves_siblings(self):
        # two-glyph font: A present, B empty. Fill B, keep A.
        pack = fr.decode_pack(_build_pack([
            {"first": 0x41, "last": 0x42, "yadv": 8, "gidx": 3,
             "glyphs": [(0, 2, 2, 3, 0, -2), (0, 0, 0, 0, 0, 0)],
             "bitmap": bytes([0xF0])},
        ]))
        font = pack.fonts[0]
        a_before = dict(font.glyphs[0])
        newg = dict(bitmapOffset=0, width=2, height=2, xAdvance=3, xOffset=0, yOffset=-2)
        merged = fr.replace_glyph(font, 0x42, newg, bytes([0xC0]))
        self.assertEqual(merged.first, 0x41)
        self.assertEqual(merged.last, 0x42)
        self.assertEqual(merged.global_index, 3)
        # A (sibling) unchanged in metrics
        self.assertEqual({k: merged.glyphs[0][k] for k in
                          ("width", "height", "xAdvance", "xOffset", "yOffset")},
                         {k: a_before[k] for k in
                          ("width", "height", "xAdvance", "xOffset", "yOffset")})
        # B now filled
        self.assertEqual(merged.glyphs[1]["width"], 2)
        # re-encodes cleanly and both glyphs' bitmaps are present
        data = fr.encode_pack([merged], 1)
        rp = fr.decode_pack(data)
        self.assertTrue(rp.crc_ok)
        self.assertEqual(rp.fonts[0].glyphs[1]["width"], 2)

    def test_replace_glyph_out_of_range(self):
        pack = fr.decode_pack(_build_pack([
            {"first": 0x41, "last": 0x41, "yadv": 8, "gidx": 0,
             "glyphs": [(0, 1, 1, 2, 0, 0)], "bitmap": bytes([0x80])}]))
        with self.assertRaises(ValueError):
            fr.replace_glyph(pack.fonts[0], 0x99,
                             dict(bitmapOffset=0, width=1, height=1, xAdvance=2,
                                  xOffset=0, yOffset=0), bytes([0x80]))

    def test_crc_mismatch_flagged(self):
        data = bytearray(_build_pack([
            {"first": 0x41, "last": 0x41, "yadv": 8, "glyphs": [(0, 1, 1, 2, 0, 0)],
             "bitmap": bytes([0x80])}]))
        data[-1] ^= 0xFF
        self.assertFalse(fr.decode_pack(bytes(data)).crc_ok)

    def test_bad_magic(self):
        with self.assertRaises(fr.PackDecodeError):
            fr.decode_pack(b"XXXX" + b"\x00" * 28)

    def test_empty_pack(self):
        pack = fr.decode_pack(_build_pack([]))
        self.assertEqual(pack.font_count, 0)
        self.assertEqual(pack.fonts, [])
        self.assertTrue(pack.crc_ok)


@unittest.skipUnless(os.path.isdir(RES) and os.path.exists(os.path.join(RES, "bundles.json")),
                     "shipped fontpack bundles not present")
class ShippedBundlesTest(unittest.TestCase):
    def test_all_bundles_decode(self):
        bundles = _load_bundles()
        self.assertTrue(bundles)
        for b in bundles:
            path = os.path.join(RES, b["file"])
            with self.subTest(bundle=b["id"]):
                pack = fr.decode_pack_file(path, name_hint=b["id"])
                self.assertTrue(pack.crc_ok, f"{b['id']} CRC failed")
                self.assertEqual(pack.total_size, b["size"])
                self.assertEqual(pack.content_version, b["content_version"])
                self.assertEqual(pack.font_count, len(pack.fonts))
                for f in pack.fonts:
                    self.assertEqual(len(f.glyphs), f.glyph_count)
                    self.assertGreaterEqual(f.last, f.first)

    def test_encode_roundtrip_byte_identical(self):
        for b in _load_bundles():
            with self.subTest(bundle=b["id"]):
                raw = open(os.path.join(RES, b["file"]), "rb").read()
                pack = fr.decode_pack(raw, b["id"])
                self.assertEqual(fr.encode_pack(pack.fonts, pack.content_version), raw)

    def test_global_indices_unique_across_bundles(self):
        bundles = _load_bundles()
        packs = [fr.decode_pack_file(os.path.join(RES, b["file"]), b["id"]) for b in bundles]
        merged = fr.merge_fonts(packs)
        gidx = [f.global_index for f in merged]
        self.assertEqual(gidx, sorted(gidx))
        self.assertEqual(len(set(gidx)), len(gidx), "duplicate global ALL_FONTS index")


if __name__ == "__main__":
    unittest.main()
