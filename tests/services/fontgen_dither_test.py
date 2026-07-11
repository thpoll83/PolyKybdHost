"""Unit tests for the NumPy dither pipeline (polyhost.services.fontgen_dither).

Pure (numpy only) — exercises the building blocks with hand-verifiable cases.
Cross-checking the whole pipeline against the C fontconvert lives in
fontgen_test.py (gated on the binary).
"""
import unittest

try:
    import numpy as np
    _ERR = None
except ImportError as e:  # pragma: no cover
    _ERR = e
else:
    from polyhost.services import fontgen_dither as fd


@unittest.skipIf(_ERR is not None, f"numpy unavailable: {_ERR}")
class DitherUnitTest(unittest.TestCase):

    def test_bits_pack_msb_first(self):
        b = fd._Bits(16)
        b.set(0); b.set(7); b.set(8)
        self.assertEqual(bytes(b.buf), bytes([0x81, 0x80]))
        self.assertEqual(b.get(0), 1)
        self.assertEqual(b.get(1), 0)
        b.flip(1); self.assertEqual(b.get(1), 1)

    def test_bgra_over_black(self):
        # opaque white -> 1.0 ; half-alpha white -> 0.5 ; opaque pure red -> 0.2126
        buf = bytes([255, 255, 255, 255,   255, 255, 255, 128,   0, 0, 255, 255])
        g = fd.bgra_to_gray(buf, pitch=12, width=3, rows=1)
        self.assertAlmostEqual(float(g[0, 0]), 1.0, places=4)
        self.assertAlmostEqual(float(g[0, 1]), 128 / 255.0, places=4)
        self.assertAlmostEqual(float(g[0, 2]), 0.2126, places=4)

    def test_threshold(self):
        gray = np.array([[0.4, 0.6], [0.5, 0.49]], dtype=np.float32)
        bits = fd._Bits(4)
        fd.dither(gray, fd.DITHER_THRESHOLD, bits)
        self.assertEqual([bits.get(i) for i in range(4)], [0, 1, 1, 0])

    def test_fs_extremes(self):
        ones = np.ones((3, 3), dtype=np.float32)
        b = fd._Bits(9); fd.dither(ones.copy(), fd.DITHER_FLOYD_STEINBERG, b)
        self.assertEqual([b.get(i) for i in range(9)], [1] * 9)
        zeros = np.zeros((3, 3), dtype=np.float32)
        b = fd._Bits(9); fd.dither(zeros, fd.DITHER_FLOYD_STEINBERG, b)
        self.assertEqual([b.get(i) for i in range(9)], [0] * 9)

    def test_fs_half_field_density(self):
        # a uniform 0.5 field should dither to ~50% lit (FS spreads the error)
        gray = np.full((8, 8), 0.5, dtype=np.float32)
        b = fd._Bits(64); fd.dither(gray, fd.DITHER_FLOYD_STEINBERG, b)
        lit = sum(b.get(i) for i in range(64))
        self.assertTrue(24 <= lit <= 40, lit)

    def test_mono_passthrough(self):
        # one mono row 0b10100000 width 3 -> bits 1,0,1
        buf = bytes([0b10100000])
        packed, w, h = fd.render_bitmap_to_bits(1, 3, 1, 1, buf, fd.DitherOpts())
        self.assertEqual((w, h), (3, 1))
        bits = fd._Bits(3); bits.buf[:] = packed
        self.assertEqual([bits.get(i) for i in range(3)], [1, 0, 1])

    def test_morphological_outline_single_pixel(self):
        # centre pixel lit in 3x3 mono, -O1 -> all 9 lit (8 neighbours added)
        buf = bytes([0b00000000, 0b01000000, 0b00000000])  # (1,1) set, pitch 1
        opts = fd.DitherOpts(outline=1)
        packed, w, h = fd.render_bitmap_to_bits(1, 3, 3, 1, buf, opts)
        bits = fd._Bits(9); bits.buf[:] = packed
        self.assertEqual(sum(bits.get(i) for i in range(9)), 9)

    def test_fit_dimensions(self):
        self.assertEqual(fd.fit_dimensions(80, 80, 0, 40), (40, 40))
        self.assertEqual(fd.fit_dimensions(80, 40, 60, 0), (60, 30))
        self.assertEqual(fd.fit_dimensions(10, 10, 0, 0), (10, 10))

    def test_scale_gray_identity(self):
        g = np.random.RandomState(0).rand(8, 8).astype(np.float32)
        self.assertIs(fd.scale_gray(g, 8, 8), g)


if __name__ == "__main__":
    unittest.main()
