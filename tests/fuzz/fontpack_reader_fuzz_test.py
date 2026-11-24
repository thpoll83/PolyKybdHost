"""Properties of polyhost/services/fontpack_reader.py (PlyF font packs from files).

decode_pack() reads files a user picks, so on any input it returns a Pack or raises
PackDecodeError, never another exception."""
import struct
import unittest

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.services import fontpack_reader as fr

load_profile()


@st.composite
def fonts(draw):
    first = draw(st.integers(0x20, 0x2FFFF))
    count = draw(st.integers(1, 6))
    glyphs, off = [], 0
    for _ in range(count):
        w, h = draw(st.integers(0, 12)), draw(st.integers(0, 16))
        glyphs.append(dict(bitmapOffset=off, width=w, height=h,
                           xAdvance=draw(st.integers(-128, 127)),
                           xOffset=draw(st.integers(-128, 127)),
                           yOffset=draw(st.integers(-128, 127))))
        if w and h:
            off += fr._glyph_len(w, h)
    bitmap = draw(st.binary(min_size=off, max_size=off))
    return fr.PackFont(name="f", bitmap=bitmap, glyphs=glyphs, first=first,
                       last=first + count - 1, yAdvance=draw(st.integers(-32768, 32767)),
                       global_index=draw(st.integers(0, 0xFFFF)))


def _decode_or_error(data):
    try:
        return fr.decode_pack(data)
    except fr.PackDecodeError:
        return None


class FontpackReaderFuzzTest(unittest.TestCase):
    @given(st.lists(fonts(), max_size=4), st.integers(0, 0xFFFFFFFF))
    def test_encode_decode_round_trip(self, fs, version):
        data = fr.encode_pack(fs, version)
        pack = fr.decode_pack(data)
        self.assertTrue(pack.crc_ok)
        self.assertEqual(pack.content_version, version)
        self.assertEqual(len(pack.fonts), len(fs))
        for a, b in zip(fs, pack.fonts):
            self.assertEqual((a.first, a.last, a.yAdvance, a.global_index, a.glyphs),
                             (b.first, b.last, b.yAdvance, b.global_index, b.glyphs))
            self.assertEqual(b.bitmap[:a.bitmap_content_len()], a.bitmap[:a.bitmap_content_len()])
        self.assertEqual(fr.encode_pack(pack.fonts, version), data)

    @given(st.binary(max_size=256))
    def test_arbitrary_bytes(self, data):
        _decode_or_error(data)

    @given(st.binary(min_size=0, max_size=200))
    def test_arbitrary_body_behind_a_valid_header(self, body):
        # Gets past the magic, ABI and size checks, so the table walk is reached.
        count, table_off = (body[0] if body else 0), 32
        data = struct.pack(fr._HEADER_FMT, fr.MAGIC, fr.ABI_VERSION, 0, 0, count,
                           table_off, 32 + len(body), 0, 0) + body
        _decode_or_error(data)

    @given(st.lists(fonts(), min_size=1, max_size=3), st.data())
    def test_corrupted_valid_pack(self, fs, data):
        raw = bytearray(fr.encode_pack(fs))
        for _ in range(data.draw(st.integers(1, 8))):
            i = data.draw(st.integers(fr.HEADER_SIZE, len(raw) - 1))
            raw[i] = data.draw(st.integers(0, 255))
        _decode_or_error(bytes(raw))


if __name__ == "__main__":
    unittest.main()
