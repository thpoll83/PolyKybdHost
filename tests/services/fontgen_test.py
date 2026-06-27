"""Tests for polyhost.services.fontgen — the FreeType render/emit layer.

Two layers:
  * always-on (given freetype-py + a system TTF): render a range, check the
    PackFont is well-formed, deterministic, and that the mono passthrough matches
    a direct FreeType rasterisation;
  * opt-in C cross-check: if a `fontconvert` binary is available (env
    FONTCONVERT_BIN, or `fontconvert` on PATH), assert byte-for-byte equality with
    its output on a few option sets — the parity guarantee for the extend path.
"""
import glob
import os
import re
import shutil
import subprocess
import unittest

try:
    import numpy  # noqa: F401
    import freetype  # noqa: F401
    from polyhost.services import fontgen
    from polyhost.services.fontgen import RenderOptions
    from polyhost.services import fontgen_dither as fd
    _ERR = None
except Exception as e:  # pragma: no cover
    _ERR = e


def _find_font():
    for pat in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/**/*.ttf"):
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    return None


_FONT = _find_font()
_FONTCONVERT = os.environ.get("FONTCONVERT_BIN") or shutil.which("fontconvert")


def _parse_header(txt):
    bm = re.search(r'Bitmaps\[\]\s*PROGMEM\s*=\s*\{(.*?)\};', txt, re.S).group(1)
    bm = re.sub(r'/\*.*?\*/', '', bm, flags=re.S)
    bitmap = bytes(int(b, 16) for b in re.findall(r'0x([0-9A-Fa-f]{2})', bm))
    gl = re.search(r'GFXglyph\s+\w+\[\]\s*PROGMEM\s*=\s*\{(.*?)\};', txt, re.S).group(1)
    gl = re.sub(r'//[^\n]*', '', gl)
    fields = ("bitmapOffset", "width", "height", "xAdvance", "xOffset", "yOffset")
    glyphs = [dict(zip(fields, map(int, m.groups())))
              for m in re.finditer(r'\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),'
                                   r'\s*(-?\d+),\s*(-?\d+)\s*\}', gl)]
    return bitmap, glyphs


@unittest.skipIf(_ERR is not None, f"freetype/numpy unavailable: {_ERR}")
@unittest.skipIf(_FONT is None, "no system TTF found")
class RenderRangeTest(unittest.TestCase):

    def test_ascii_well_formed(self):
        pf = fontgen.render_range(_FONT, 0x20, 0x7e, RenderOptions(size=14))
        self.assertEqual(len(pf.glyphs), 0x7e - 0x20 + 1)
        self.assertEqual(pf.first, 0x20)
        self.assertEqual(pf.last, 0x7e)
        self.assertGreater(pf.yAdvance, 0)
        # 'A' (0x41) has pixels and a positive advance
        self.assertGreater(pf.glyphs[0x41 - 0x20]["width"], 0)
        self.assertGreater(pf.glyphs[0x41 - 0x20]["xAdvance"], 0)
        self.assertTrue(pf.bitmap)

    def test_deterministic(self):
        a = fontgen.render_range(_FONT, 0x41, 0x5a, RenderOptions(size=16))
        b = fontgen.render_range(_FONT, 0x41, 0x5a, RenderOptions(size=16))
        self.assertEqual(a.bitmap, b.bitmap)
        self.assertEqual(a.glyphs, b.glyphs)

    def test_offset_applied_to_codepoints(self):
        pf = fontgen.render_range(_FONT, 0x41, 0x5a, RenderOptions(size=14, offset=-0x10))
        self.assertEqual((pf.first, pf.last), (0x31, 0x4a))

    def test_yadvance_override(self):
        pf = fontgen.render_range(_FONT, 0x41, 0x42, RenderOptions(size=14, yadvance=48))
        self.assertEqual(pf.yAdvance, 48)


@unittest.skipIf(_ERR is not None, f"freetype/numpy unavailable: {_ERR}")
@unittest.skipIf(_FONT is None, "no system TTF found")
@unittest.skipIf(_FONTCONVERT is None, "no fontconvert binary (set FONTCONVERT_BIN)")
class CParityTest(unittest.TestCase):
    """Byte-for-byte equality with the C tool — the extend-path parity guarantee.
    Requires the C tool to be built against the SAME FreeType as freetype-py."""

    def _c(self, args):
        out = subprocess.run([_FONTCONVERT, "-f", _FONT, *args],
                             capture_output=True, text=True, check=True)
        return _parse_header(out.stdout)

    def _assert_parity(self, args, opts, first, last):
        c_bitmap, c_glyphs = self._c(args)
        pf = fontgen.render_range(_FONT, first, last, opts)
        self.assertEqual(c_bitmap, pf.bitmap, "bitmap bytes differ")
        self.assertEqual(c_glyphs, pf.glyphs, "glyph records differ")

    def test_mono_ascii(self):
        self._assert_parity(["-s14", "0x20", "0x7e"], RenderOptions(size=14), 0x20, 0x7e)

    def test_gray_fs(self):
        self._assert_parity(["-s14", "-g", "0x20", "0x7e"],
                            RenderOptions(size=14, render_mode=1), 0x20, 0x7e)

    def test_gray_stucki(self):
        self._assert_parity(["-s16", "-g", "-Dstucki", "0x20", "0x7e"],
                            RenderOptions(size=16, render_mode=1,
                                          dither_mode=fd.DITHER_STUCKI), 0x20, 0x7e)

    def test_mono_outline(self):
        self._assert_parity(["-s16", "-O1", "0x41", "0x5a"],
                            RenderOptions(size=16, outline=1), 0x41, 0x5a)

    def test_adjust_chain(self):
        self._assert_parity(
            ["-s14", "-g", "-N", "-G1.3", "-c1.4", "-e0.1", "-U0.5", "0x20", "0x7e"],
            RenderOptions(size=14, render_mode=1, normalize=True, gamma_val=1.3,
                          contrast=1.4, exposure=0.1, sharpness=0.5), 0x20, 0x7e)


if __name__ == "__main__":
    unittest.main()
