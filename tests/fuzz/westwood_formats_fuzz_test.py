"""Properties of the Westwood file-format readers in services/game_assets
(westwood_td/westwood.py, westwood_ra/mix.py, westwood_d2/pak.py, westwood_d2k/r16.py).

They read the user's game files, which a mod or a damaged download can change. A
reader may refuse such a file only with the errors ``build.render`` skips one key
for: KeyError, IndexError, ValueError and struct.error.
"""
import struct
import unittest

import numpy as np
from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.services.game_assets.westwood_d2.pak import Pak
from polyhost.services.game_assets.westwood_d2k.r16 import R16
from polyhost.services.game_assets.westwood_ra import mix as ra_mix
from polyhost.services.game_assets.westwood_td import westwood

load_profile()

DAMAGED = (KeyError, IndexError, ValueError, struct.error)
BYTE = st.integers(0, 255)


@st.composite
def lcw_programs(draw):
    """(encoded LCW, the bytes it must decode to): a random sequence of the five
    commands, run on a model of the output as the format describes them."""
    out, enc = bytearray(), bytearray()
    for _ in range(draw(st.integers(0, 12))):
        kind = draw(st.sampled_from(["literal", "fill", "relative", "short", "long"]))
        if kind == "literal" or not out:
            chunk = draw(st.binary(min_size=1, max_size=63))
            enc += bytes([0x80 | len(chunk)]) + chunk
            out += chunk
        elif kind == "fill":
            cnt, value = draw(st.integers(0, 300)), draw(BYTE)
            enc += b"\xFE" + struct.pack("<HB", cnt, value)
            out += bytes([value]) * cnt
        elif kind == "relative":                 # 0cccpppp pppppppp, from len(out) - p
            cnt = draw(st.integers(3, 10))
            back = draw(st.integers(1, min(len(out), 0xFFF)))
            enc += bytes([((cnt - 3) << 4) | (back >> 8), back & 0xFF])
            start = len(out) - back
            for k in range(cnt):                 # overlapping: may copy its own output
                out.append(out[start + k])
        else:                                    # absolute position, short or long
            pos = draw(st.integers(0, len(out) - 1))
            if kind == "short":
                cnt = draw(st.integers(3, 3 + 0x3D))   # 0xFE and 0xFF are other commands
                enc += bytes([0xC0 | (cnt - 3)]) + struct.pack("<H", pos)
            else:
                cnt = draw(st.integers(0, 300))
                enc += b"\xFF" + struct.pack("<HH", cnt, pos)
            for k in range(cnt):
                out.append(out[pos + k])
    return bytes(enc) + b"\x80", bytes(out)


@st.composite
def xor_programs(draw):
    """(encoded format-40 delta, frame size, the frame it must give)."""
    size = draw(st.integers(1, 400))
    dst, enc, p = bytearray(size), bytearray(), 0
    for _ in range(draw(st.integers(0, 10))):
        room = size - p
        if room <= 0:
            break
        kind = draw(st.sampled_from(["fill", "literal", "skip", "lskip", "lliteral", "lfill"]))
        if kind == "fill":
            cnt, v = draw(st.integers(1, min(255, room))), draw(BYTE)
            enc += bytes([0, cnt, v])
            dst[p:p + cnt] = bytes([v]) * cnt
        elif kind == "literal":
            data = draw(st.binary(min_size=1, max_size=min(127, room)))
            cnt = len(data)
            enc += bytes([cnt]) + data
            dst[p:p + cnt] = data
        elif kind == "skip":
            cnt = draw(st.integers(1, min(127, room)))
            enc += bytes([0x80 | cnt])
        elif kind == "lskip":
            cnt = draw(st.integers(1, min(0x7FFF, room)))
            enc += b"\x80" + struct.pack("<H", cnt)
        elif kind == "lliteral":
            data = draw(st.binary(min_size=1, max_size=min(0x3FFF, room, 200)))
            cnt = len(data)
            enc += b"\x80" + struct.pack("<H", 0x8000 | cnt) + data
            dst[p:p + cnt] = data
        else:
            cnt, v = draw(st.integers(1, min(0x3FFF, room))), draw(BYTE)
            enc += b"\x80" + struct.pack("<H", 0xC000 | cnt) + bytes([v])
            dst[p:p + cnt] = bytes([v]) * cnt
        p += cnt
    return bytes(enc) + b"\x80\x00\x00", size, bytes(dst)


def rle_zeros_encode(data: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(data):
        if data[i] == 0:
            n = 1
            while i + n < len(data) and data[i + n] == 0 and n < 255:
                n += 1
            out += bytes([0, n])
            i += n
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


NAME = st.text("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._", min_size=1, max_size=12)


class WestwoodFuzzTest(unittest.TestCase):
    @given(lcw_programs(), st.binary(max_size=4))
    def test_lcw_round_trip(self, program, tail):
        enc, want = program
        self.assertEqual(westwood.lcw(enc + tail, len(want)), want)
        if want:
            # Asking for less stops early; asking for more is a damaged file.
            self.assertEqual(westwood.lcw(enc, len(want) - 1), want[:-1])
        with self.assertRaises(ValueError):
            westwood.lcw(enc, len(want) + 1)

    @given(st.binary(max_size=80), st.integers(0, 2000))
    def test_lcw_arbitrary(self, src, size):
        try:
            out = westwood.lcw(src, size)
        except DAMAGED:
            return
        self.assertEqual(len(out), size)

    @given(xor_programs())
    def test_xor_delta_round_trip(self, program):
        enc, size, want = program
        self.assertEqual(westwood.xor_delta(enc, size), want)

    @given(st.binary(max_size=60), st.integers(0, 600))
    def test_xor_delta_arbitrary(self, src, size):
        try:
            out = westwood.xor_delta(src, size)
        except DAMAGED:
            return
        self.assertEqual(len(out), size)

    @given(st.binary(max_size=200))
    def test_rle_zeros_round_trip(self, data):
        self.assertEqual(westwood._rle_zeros(rle_zeros_encode(data), len(data)), data)

    @given(st.binary(max_size=60), st.integers(0, 300))
    def test_rle_zeros_arbitrary(self, src, size):
        try:
            self.assertEqual(len(westwood._rle_zeros(src, size)), size)
        except DAMAGED:
            pass  # a documented refusal; any other exception fails the test

    @given(st.dictionaries(NAME, st.binary(max_size=40), max_size=6))
    def test_mix_round_trip(self, files):
        hashes = {westwood.td_hash(n) for n in files}
        if len(hashes) != len(files):
            return                                   # two names with one hash
        body, entries = bytearray(), []
        for name, data in files.items():
            entries.append((westwood.td_hash(name), len(body), len(data)))
            body += data
        head = struct.pack("<HI", len(entries), len(body))
        head += b"".join(struct.pack("<III", *e) for e in sorted(entries))
        archive = head + bytes(body)
        # An empty TD archive starts with the count 0, which is how a Red Alert
        # archive starts too, so only a non-empty one is told apart.
        for reader in (westwood.Mix, ra_mix.read) if files else (westwood.Mix,):
            m = reader(archive)
            for name, data in files.items():
                self.assertEqual(m.get(name.lower()), data)
        # Red Alert's unencrypted form: a flags word, then the same header.
        m = ra_mix.read(b"\0\0\0\0" + archive)
        for name, data in files.items():
            self.assertEqual(m.get(name), data)

    @given(st.binary(max_size=120), st.sampled_from([b"", b"\0\0\0\0", b"\0\0\2\0"]))
    def test_mix_arbitrary(self, data, prefix):
        try:
            m = ra_mix.read(prefix + data)
        except DAMAGED:
            return
        for off, size in m.entries.values():
            self.assertIsInstance(m.data[m.body + off:m.body + off + size], bytes)

    @given(st.lists(st.tuples(NAME, st.binary(max_size=30)), max_size=6,
                    unique_by=lambda t: t[0].lower()))
    def test_pak_round_trip(self, files):
        table = sum(4 + len(n) + 1 for n, _ in files) + 4
        head, body, pos = bytearray(), bytearray(), table
        for name, data in files:
            head += struct.pack("<I", pos) + name.encode() + b"\0"
            body += data
            pos += len(data)
        archive = bytes(head) + b"\0\0\0\0" + bytes(body)
        pak = Pak(archive)
        # A file ends where the next one starts, so an empty file directly before
        # another one shares that one's start and gets its bytes too.
        for i, (name, data) in enumerate(files):
            got = pak.get(name.swapcase())
            if data:
                self.assertEqual(got, data)
            else:
                rest = next((d for _, d in files[i + 1:] if d), b"")
                self.assertEqual(got, rest)

    @given(st.binary(max_size=120))
    def test_pak_arbitrary(self, data):
        try:
            pak = Pak(data)
        except DAMAGED:
            return
        for start, end in pak.entries.values():
            self.assertLessEqual(start, end)
            self.assertLessEqual(end, len(data))

    @given(st.binary(max_size=160), st.none() | st.integers(0, 4))
    def test_shape_files_arbitrary(self, data, count):
        for reader in (westwood.shp_frames, westwood.shp_d2_frames):
            try:
                frames = reader(data, count)
            except DAMAGED:
                continue
            for f in frames:
                self.assertEqual(f.dtype, np.uint8)
                self.assertLessEqual(f.size, westwood.MAX_FRAME_PIXELS)

    @given(st.binary(max_size=160), st.sampled_from([None, bytes(768)]))
    def test_r16_arbitrary(self, data, palette):
        try:
            r = R16(data, palette)
            for k in range(len(r)):
                rgb, cover = r.frame(k)
                self.assertEqual(rgb.shape[:2], cover.shape)
        except DAMAGED:
            pass  # a documented refusal; any other exception fails the test


if __name__ == "__main__":
    unittest.main()
