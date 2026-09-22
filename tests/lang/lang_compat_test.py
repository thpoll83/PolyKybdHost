"""`LangComp`, and the encoding bug that took PolyHost down on Windows.

The maps are read at `PolyHost.__init__` time, so anything that raises here
kills the tray AND the daemon before either can say why — which is exactly
what happened in the field (Windows 11 / Python 3.13, 2026-09-22)."""

import builtins
import pathlib
import unittest
from unittest.mock import patch

from polyhost.lang.lang_compat import LangComp

RES = pathlib.Path(__file__).resolve().parents[2] / "polyhost" / "res"
PLATFORMS = ("linux", "macos", "windows")

#: cp1252 leaves these byte values undefined, so decoding them RAISES. Every
#: other high byte decodes to some character — silently the wrong one.
CP1252_UNDEFINED = {0x81, 0x8D, 0x8F, 0x90, 0x9D}


class EncodingTest(unittest.TestCase):
    def test_the_map_is_read_as_utf8_not_the_platform_default(self):
        """⚠️ White-box on purpose. The bug WAS the missing argument, and no
        black-box test can reproduce it here: `open()` resolves the locale
        encoding inside CPython, so patching `locale.getpreferredencoding` or
        `locale.getencoding` does not change what it uses (verified). The
        argument itself is the only thing left to assert."""
        real = builtins.open
        seen = {}

        def spy(path, *a, **kw):
            if "forced_country_match" in str(path):
                seen["encoding"] = kw.get("encoding")
            return real(path, *a, **kw)

        with patch.object(builtins, "open", spy):
            LangComp("windows")
        self.assertEqual(seen.get("encoding"), "utf-8",
                         "read with the platform default — cp1252 on Windows")

    def test_every_shipped_map_really_is_utf8(self):
        """The other half: the argument is only right if the files match it."""
        for name in PLATFORMS:
            with self.subTest(platform=name):
                (RES / f"forced_country_match_{name}.txt").read_bytes().decode("utf-8")

    def test_a_map_carries_bytes_that_make_the_default_codec_RAISE(self):
        """Proof the explicit encoding is load-bearing rather than decoration.

        ⚠️ Only the Windows map contains such a byte (0x8f, the tail of a ⚠️
        variation selector). The other two decode to MOJIBAKE under cp1252
        instead of raising — so the crash was the lucky outcome, and a
        non-ASCII character in a VALUE rather than a comment would have
        resolved to the wrong layout in silence."""
        raising = [n for n in PLATFORMS
                   if CP1252_UNDEFINED & set((RES / f"forced_country_match_{n}.txt").read_bytes())]
        self.assertIn("windows", raising)


class DegradationTest(unittest.TestCase):
    """A compatibility map is a FALLBACK; losing it must not lose the app."""

    def test_an_undecodable_map_leaves_an_empty_table_not_an_exception(self):
        real = builtins.open

        def boom(path, *a, **kw):
            if "forced_country_match" in str(path):
                raise UnicodeDecodeError("charmap", b"\x8f", 0, 1, "undefined")
            return real(path, *a, **kw)

        with patch.object(builtins, "open", boom):
            comp = LangComp("windows")
        self.assertEqual(comp.mapping, {})
        self.assertEqual(comp.platform, "windows")
        self.assertIsNone(comp.get_compatible_lang_list("PF"))

    def test_a_missing_map_leaves_an_empty_table_not_an_exception(self):
        comp = LangComp("nosuchplatform")
        self.assertEqual(comp.mapping, {})

    def test_the_helpers_still_construct_when_the_map_cannot_be_read(self):
        """The real failure mode: this ran inside `PolyHost.__init__`."""
        real = builtins.open

        def boom(path, *a, **kw):
            if "forced_country_match" in str(path):
                raise OSError("nope")
            return real(path, *a, **kw)

        from polyhost.input.win_helper import WindowsInputHelper
        with patch.object(builtins, "open", boom):
            helper = WindowsInputHelper()
        self.assertEqual(helper.comp.mapping, {})
        # …and language switching still works, just without the folds.
        self.assertIsNone(helper.comp.get_compatible_lang_list("PF"))


if __name__ == "__main__":
    unittest.main()
