"""Tests for polyhost/util/prc_codec.py, the PRC-coded overlay format (cmd 41).

The golden vectors in prc_codec_vectors.json are what the firmware's
``make test:polykybd_prc_codec`` decodes too (tools/gen_prc_vectors.py writes
both). A change that breaks them here breaks the keyboard.
"""
import hashlib
import json
import os
import unittest

import numpy as np

from polyhost.util import prc_codec

VECTORS = os.path.join(os.path.dirname(__file__), "prc_codec_vectors.json")
TABLE_V1_SHA256 = "c67ffa5a9e4af7e25f155cf9e3dcdeda24f37c2e7f4c550f987fea8db93cb2b7"


def _vectors():
    with open(VECTORS, encoding="utf-8") as fh:
        return json.load(fh)


def _frame(hexstr):
    return np.unpackbits(np.frombuffer(bytes.fromhex(hexstr), dtype=np.uint8)).reshape(40, 72).astype(bool)


class TableTest(unittest.TestCase):
    def test_table_v1_is_frozen(self):
        # The firmware compiles in the same bytes (base/prc_table.h). Any change
        # is a new table id, never an edit.
        self.assertEqual(hashlib.sha256(prc_codec.table()).hexdigest(), TABLE_V1_SHA256)
        self.assertEqual(prc_codec.TABLE_ID, 1)

    def test_vectors_were_made_with_this_table(self):
        self.assertEqual(_vectors()["table_id"], prc_codec.TABLE_ID)


class GoldenVectorTest(unittest.TestCase):
    def test_encoder_reproduces_every_payload(self):
        for v in _vectors()["vectors"]:
            roi = _frame(v["overlay"])[v["top"]:v["top"] + v["height"], v["left"]:v["left"] + v["width"]]
            self.assertEqual(prc_codec.encode(roi).hex(), v["payload"], v["name"])

    def test_decoder_reproduces_every_overlay(self):
        for v in _vectors()["vectors"]:
            roi = prc_codec.decode(bytes.fromhex(v["payload"]), v["height"], v["width"])
            frame = np.zeros((40, 72), dtype=bool)
            frame[v["top"]:v["top"] + v["height"], v["left"]:v["left"] + v["width"]] = roi
            self.assertEqual(np.packbits(frame).tobytes().hex(), v["overlay"], v["name"])

    def test_records_pack_and_parse_to_the_same_bytes(self):
        packed = 0
        for v in _vectors()["vectors"]:
            if not v["record"]:
                self.assertGreater(len(v["payload"]) // 2, prc_codec.MAX_RECORD_PAYLOAD)
                continue
            payload = bytes.fromhex(v["payload"])
            record = prc_codec.pack_record(v["keycode"], v["modifier"], v["top"], v["left"],
                                           v["height"], v["width"], payload)
            self.assertEqual(record.hex(), v["record"], v["name"])
            parsed = list(prc_codec.parse_records(record))
            self.assertEqual(parsed, [(v["keycode"], v["modifier"], v["top"], v["left"],
                                       v["height"], v["width"], payload)])
            packed += 1
        self.assertGreaterEqual(packed, 7)

    def test_modifier_bits_all_vary_across_the_vectors(self):
        # The firmware test relies on this to catch a truncated modifier field.
        seen = 0
        for v in _vectors()["vectors"]:
            if v["record"]:
                seen |= v["modifier"]
        self.assertEqual(seen, 0x0F)


class CodecTest(unittest.TestCase):
    def test_round_trip_random_shapes(self):
        rng = np.random.default_rng(7)
        for _ in range(20):
            h, w = rng.integers(1, 41), rng.integers(1, 73)
            roi = rng.random((h, w)) < 0.3
            self.assertTrue((prc_codec.decode(prc_codec.encode(roi), h, w) == roi).all())

    def test_trailing_zeros_are_dropped(self):
        roi = np.zeros((10, 10), dtype=bool)
        roi[0, 0] = True
        payload = prc_codec.encode(roi)
        self.assertFalse(payload.endswith(b"\x00"))

    def test_roi_box_and_crop(self):
        m = np.zeros((40, 72), dtype=bool)
        self.assertIsNone(prc_codec.roi_box(m))
        self.assertIsNone(prc_codec.crop_to_roi(m))
        m[3:7, 10:20] = True
        self.assertEqual(prc_codec.roi_box(m), (3, 10, 4, 10))
        self.assertEqual(prc_codec.crop_to_roi(m).shape, (4, 10))


class RecordTest(unittest.TestCase):
    def test_header_is_six_bytes_in_the_documented_bit_order(self):
        # keycode 8 | modifier 4 | top 6 | left 7 | height-1 6 | width-1 7 | len 6 | 0 4
        rec = prc_codec.pack_record(0x04, 0x0F, 39, 71, 1, 1, b"\xAB")
        f = int.from_bytes(rec[1:6], "big")
        self.assertEqual(rec[0], 0x04)
        self.assertEqual((f >> 36) & 0x0F, 0x0F)
        self.assertEqual((f >> 30) & 0x3F, 39)
        self.assertEqual((f >> 23) & 0x7F, 71)
        self.assertEqual((f >> 17) & 0x3F, 0)
        self.assertEqual((f >> 10) & 0x7F, 0)
        self.assertEqual((f >> 4) & 0x3F, 1)
        self.assertEqual(f & 0x0F, 0)
        self.assertEqual(rec[6:], b"\xAB")

    def test_pack_refuses_what_the_firmware_would_refuse(self):
        for args in [(0, 0, 0, 0, 1, 1), (256, 0, 0, 0, 1, 1), (4, 16, 0, 0, 1, 1),
                     (4, 0, 39, 0, 2, 1), (4, 0, 0, 71, 1, 2), (4, 0, 0, 0, 0, 1),
                     (4, 0, 0, 0, 1, 0), (4, 0, -1, 0, 1, 1)]:
            with self.assertRaises(ValueError, msg=str(args)):
                prc_codec.pack_record(*args, b"")
        with self.assertRaises(ValueError):
            prc_codec.pack_record(4, 0, 0, 0, 1, 1, bytes(64))
        prc_codec.pack_record(4, 0, 0, 0, 40, 72, bytes(63))

    def test_parse_stops_at_zero_padding_and_on_malformed_records(self):
        a = prc_codec.pack_record(4, 1, 0, 0, 2, 2, b"\x01\x02")
        b = prc_codec.pack_record(5, 2, 1, 1, 3, 3, b"\x03")
        report = a + b + bytes(62 - len(a) - len(b))
        self.assertEqual([r[0] for r in prc_codec.parse_records(report)], [4, 5])
        bad = bytearray(a)
        bad[5] |= 0x01                      # reserved bit
        self.assertEqual(list(prc_codec.parse_records(bytes(bad) + b)), [])
        self.assertEqual(list(prc_codec.parse_records(a[:-1])), [])   # payload runs past the end


if __name__ == "__main__":
    unittest.main()
