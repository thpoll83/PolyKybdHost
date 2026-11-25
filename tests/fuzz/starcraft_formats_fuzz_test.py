"""Properties of the StarCraft file-format readers in services/game_assets/starcraft:
PKWARE DCL explode, MPQ archives and GRP sprites.

They read the user's game files. A reader may refuse a damaged file only with the
errors ``build.render`` skips one key for: KeyError, IndexError, ValueError and
struct.error. The encoders come from the unit tests
(tests/services/game_assets_starcraft_test.py).
"""
import struct
import unittest
import zlib

import numpy as np
from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from tests.services.game_assets_starcraft_test import implode, write_grp, write_mpq
from polyhost.services.game_assets.starcraft import explode, grp, mpq

load_profile()

DAMAGED = (KeyError, IndexError, ValueError, struct.error)
# Repetitive data, so the encoder emits copies and not only literals.
DATA = st.one_of(st.binary(max_size=300),
                 st.lists(st.sampled_from([b"a", b"ab", b"\0" * 7, b"xyz", b"\xff"]),
                          max_size=80).map(b"".join))


class ExplodeFuzzTest(unittest.TestCase):
    @given(DATA, st.booleans(), st.sampled_from([4, 5, 6]))
    def test_round_trip(self, data, coded, dict_bits):
        self.assertEqual(explode.explode(implode(data, coded, dict_bits)), data)

    @given(DATA, st.booleans(), st.integers(0, 400))
    def test_max_size(self, data, coded, max_size):
        stream = implode(data, coded)
        if len(data) <= max_size:
            self.assertEqual(explode.explode(stream, max_size), data)
        else:
            with self.assertRaisesRegex(ValueError, "grows past"):
                explode.explode(stream, max_size)

    @given(st.binary(max_size=64), st.sampled_from([b"", b"\0\4", b"\1\6", b"\0\5"]))
    def test_arbitrary(self, data, head):
        try:
            out = explode.explode(head + data, 4096)
        except ValueError:
            return
        self.assertLessEqual(len(out), 4096)

    @given(DATA, st.integers(0, 10 ** 6), st.integers(1, 255))
    def test_a_damaged_stream(self, data, where, flip):
        stream = bytearray(implode(data))
        stream[where % len(stream)] ^= flip
        try:
            explode.explode(bytes(stream), 4096)
        except ValueError:
            pass  # a documented refusal; any other exception fails the test


def _single_only_if_smaller(data, method, options):
    """An archiver stores a single-unit file compressed only when that is
    smaller (a reader takes csize >= size as stored); the test encoder does not
    check, so a file zlib cannot shrink is written sector by sector instead."""
    if method == "single" and len(zlib.compress(data)) + 1 >= len(data):
        method = "zlib"
    return data, method, options


METHOD = st.sampled_from(["stored", "zlib", "bzip2", "pkware", "implode", "single"])
OPTIONS = st.sets(st.sampled_from(["encrypt", "fix_key"]))
FILES = st.dictionaries(st.sampled_from(["unit\\wirefram\\wirefram.grp", "tileset\\x.wpe",
                                         "a.txt", "B\\C", "(listfile)"]),
                        st.tuples(st.binary(min_size=1, max_size=1100), METHOD,
                                  OPTIONS).map(lambda f: _single_only_if_smaller(*f)),
                        min_size=1, max_size=3)


class MpqFuzzTest(unittest.TestCase):
    @given(FILES, st.sampled_from([b"", b"\0" * 512]), st.sampled_from([4, 8]))
    def test_round_trip(self, files, prefix, hash_size):
        archive = mpq.Archive(write_mpq(files, prefix, hash_size))
        for name, (data, _m, _o) in files.items():
            self.assertIn(name, archive)
            self.assertEqual(archive.get(name), data)
            self.assertEqual(archive.get(name.upper().replace("/", "\\")), data)
        self.assertIsNone(archive.get("not\\there"))

    @given(FILES, st.lists(st.tuples(st.integers(0, 10 ** 6), st.integers(1, 255)),
                           min_size=1, max_size=3))
    def test_a_damaged_archive(self, files, flips):
        data = bytearray(write_mpq(files))
        for where, flip in flips:
            data[where % len(data)] ^= flip
        try:
            archive = mpq.Archive(bytes(data))
            for name in files:
                got = archive.get(name)
                self.assertTrue(got is None or len(got) <= mpq.MAX_FILE)
        except DAMAGED:
            pass  # a documented refusal; any other exception fails the test

    @given(st.binary(max_size=200))
    def test_arbitrary_bytes(self, data):
        try:
            mpq.Archive(mpq.MAGIC + data).get("a.txt")
        except DAMAGED:
            pass  # a documented refusal; any other exception fails the test

    @given(st.binary(max_size=80), st.integers(0, 600),
           st.sampled_from([mpq.IMPLODE, mpq.COMPRESS]))
    def test_decompress_sector(self, data, size, flags):
        for head in (b"", bytes([mpq.ZLIB]), bytes([mpq.BZIP2]), bytes([mpq.PKWARE])):
            try:
                out = mpq.decompress_sector(head + data, size, flags)
            except DAMAGED:
                continue
            self.assertEqual(len(out), size)


FRAME = st.tuples(st.integers(1, 12), st.integers(1, 12)).flatmap(
    lambda hw: st.lists(st.sampled_from([0, 0, 1, 7, 200]), min_size=hw[0] * hw[1],
                        max_size=hw[0] * hw[1]).map(
        lambda px, hw=hw: np.array(px, np.uint8).reshape(hw)))


class GrpFuzzTest(unittest.TestCase):
    @given(st.lists(FRAME, min_size=1, max_size=4))
    def test_round_trip(self, frames):
        data = write_grp(frames)
        self.assertEqual(grp.frame_count(data), len(frames))
        h = max(f.shape[0] for f in frames)
        w = max(f.shape[1] for f in frames)
        for i, f in enumerate(frames):
            got = grp.frame(data, i)
            self.assertEqual(got.shape, (h, w))
            np.testing.assert_array_equal(got[:f.shape[0], :f.shape[1]], f)
            self.assertFalse(got[f.shape[0]:, :].any() or got[:, f.shape[1]:].any())
        with self.assertRaises(IndexError):
            grp.frame(data, len(frames))

    @given(st.lists(st.lists(st.one_of(
        st.integers(1, 0x7F).map(lambda n: ("transparent", n)),
        st.tuples(st.integers(1, 0x3F), st.integers(1, 255)).map(lambda nv: ("repeat",) + nv),
        st.binary(min_size=1, max_size=0x3F).map(lambda b: ("literal", b))),
        min_size=1, max_size=4), min_size=1, max_size=4), st.integers(0, 3), st.integers(0, 3))
    def test_rows_of_every_command(self, rows, x, y):
        """One frame whose rows use each command up to its longest count, written
        here from the format: 1nnnnnnn n transparent pixels, 01nnnnnn and a byte
        n copies of it, 00nnnnnn and n literal pixels."""
        coded, want = [], []
        for ops in rows:
            row, pixels = bytearray(), bytearray()
            for op in ops:
                if op[0] == "transparent":
                    row.append(0x80 | op[1])
                    pixels += bytes(op[1])
                elif op[0] == "repeat":
                    row += bytes([0x40 | op[1], op[2]])
                    pixels += bytes([op[2]]) * op[1]
                else:
                    row += bytes([len(op[1])]) + op[1]
                    pixels += op[1]
            coded.append(bytes(row))
            want.append(bytes(pixels))
        fw = max(len(p) for p in want)
        if fw > 255:
            return                                   # a frame's width is one byte
        for r, p in enumerate(want):                 # a shorter row ends transparent
            gap = fw - len(p)
            while gap:
                coded[r] += bytes([0x80 | min(gap, 0x7F)])
                gap -= min(gap, 0x7F)
            want[r] = p + bytes(fw - len(p))
        table_at = 6 + 8
        table, pos = bytearray(), 2 * len(rows)
        for c in coded:
            table += struct.pack("<H", pos)
            pos += len(c)
        data = (struct.pack("<HHH", 1, fw + x, len(rows) + y)
                + struct.pack("<BBBBI", x, y, fw, len(rows), table_at)
                + bytes(table) + b"".join(coded))
        got = grp.frame(data, 0)
        expected = np.zeros((len(rows) + y, fw + x), np.uint8)
        for r, p in enumerate(want):
            expected[y + r, x:] = np.frombuffer(p, np.uint8)
        np.testing.assert_array_equal(got, expected)

    @given(st.binary(max_size=120), st.integers(-1, 4))
    def test_arbitrary(self, data, index):
        try:
            out = grp.frame(data, index)
        except DAMAGED:
            return
        self.assertLessEqual(max(out.shape), 2 * grp.MAX_BOX)

    @given(st.lists(FRAME, min_size=1, max_size=3), st.integers(0, 10 ** 6),
           st.integers(1, 255))
    def test_a_damaged_file(self, frames, where, flip):
        data = bytearray(write_grp(frames))
        data[where % len(data)] ^= flip
        for i in range(len(frames)):
            try:
                grp.frame(bytes(data), i)
            except DAMAGED:
                pass  # a documented refusal; any other exception fails the test


if __name__ == "__main__":
    unittest.main()
