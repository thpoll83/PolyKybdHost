"""Framing of tools/pipe_bench.py against the firmware's rules (poly_pipe.h).

The firmware is not here, so the checks are the parts a reader can verify
against the header by eye: the byte layout, the CRC scope (cmd + length +
payload, zlib.crc32), the chained SINK CRC, and reassembly of a reply that
arrives in pieces or behind noise bytes.
"""
import os
import struct
import sys
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "tools"))
import pipe_bench as pb  # noqa: E402


class PackFrameTest(unittest.TestCase):
    def test_layout_matches_header(self):
        f = pb.pack_frame(pb.CMD_ECHO, b"ab")
        self.assertEqual(f[:2], b"PB")
        self.assertEqual(f[2], pb.CMD_ECHO)
        self.assertEqual(struct.unpack_from("<H", f, 3)[0], 2)
        self.assertEqual(f[5:7], b"ab")
        crc = zlib.crc32(bytes([pb.CMD_ECHO, 2, 0]) + b"ab") & 0xFFFFFFFF
        self.assertEqual(struct.unpack_from("<I", f, 7)[0], crc)
        self.assertEqual(len(f), 11)

    def test_empty_payload(self):
        f = pb.pack_frame(pb.CMD_STAT)
        self.assertEqual(len(f), 9)
        self.assertEqual(struct.unpack_from("<H", f, 3)[0], 0)


class FrameParserTest(unittest.TestCase):
    def test_reassembles_split_reply_behind_noise(self):
        reply = pb.pack_frame(pb.CMD_PING | pb.REPLY, b"\x01\x00\x02\x40\x08v1\0")
        p = pb.FrameParser()
        self.assertEqual(p.feed(b"AT\r\n" + reply[:4]), [])
        self.assertEqual(p.feed(reply[4:9]), [])
        got = p.feed(reply[9:])
        self.assertEqual(got, [(pb.CMD_PING | pb.REPLY, b"\x01\x00\x02\x40\x08v1\0")])
        self.assertEqual(p.dropped, 4)

    def test_bad_crc_is_skipped_not_returned(self):
        good = pb.pack_frame(pb.CMD_RESET | pb.REPLY)
        bad = bytearray(good)
        bad[-1] ^= 0xFF
        p = pb.FrameParser()
        self.assertEqual(p.feed(bytes(bad) + good), [(pb.CMD_RESET | pb.REPLY, b"")])

    def test_trailing_magic_start_is_kept(self):
        p = pb.FrameParser()
        self.assertEqual(p.feed(b"xxP"), [])
        self.assertEqual(p.dropped, 2)
        self.assertEqual(p.feed(b"B" + pb.pack_frame(pb.CMD_STAT | pb.REPLY, bytes(28))[2:]),
                         [(pb.CMD_STAT | pb.REPLY, bytes(28))])


class SinkCrcTest(unittest.TestCase):
    def test_chain_equals_whole(self):
        chunks = [b"hello ", b"bulk ", b"pipe"]
        self.assertEqual(pb.sink_crc_chain(chunks), zlib.crc32(b"".join(chunks)) & 0xFFFFFFFF)

    def test_parse_stat_fields(self):
        vals = list(range(7))
        st = pb.parse_stat(struct.pack("<7I", *vals))
        self.assertEqual(st["sink_bytes"], 0)
        self.assertEqual(st["last_ms"], 6)
        with self.assertRaises(ValueError):
            pb.parse_stat(b"\0" * 27)


if __name__ == "__main__":
    unittest.main()
