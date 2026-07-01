"""Tests for polyhost.services.font_downloader — the shared Noto catalog + fetch.

No network: the catalog is parsed from the shipped noto-fonts.yaml, and the
download path is exercised against a local ``file://`` URL into a temp cache.
Also asserts the host's shipped YAML is byte-identical to the firmware copy when
both are present (the single-source-of-truth invariant).
"""
import os
import pathlib
import tempfile
import unittest

from polyhost.services import font_downloader as fdl


class CatalogTest(unittest.TestCase):
    def test_shipped_catalog_parses(self):
        fonts = fdl.load_catalog()
        self.assertTrue(fonts)
        # every entry well-formed; filenames flat + unique
        names = set()
        for f in fonts:
            self.assertTrue(f.name and f.url.startswith("https://"))
            self.assertTrue(f.filename.endswith((".ttf", ".otf")))
            self.assertEqual(f.filename, os.path.basename(f.filename))
            names.add(f.filename)
        self.assertEqual(len(names), len(fonts), "duplicate cache filenames")
        # the color emoji font (needed for flags/emoji) is in the list
        self.assertTrue(any("ColorEmoji" in f.filename for f in fonts))

    def test_yaml_matches_firmware_copy(self):
        host = pathlib.Path(fdl._catalog_path())
        fw = (host.parents[4] / "qmk_firmware" / "keyboards" / "polykybd"
              / "fonts" / "noto-fonts.yaml")
        if not fw.exists():
            self.skipTest("firmware checkout not present")
        self.assertEqual(host.read_bytes(), fw.read_bytes(),
                         "noto-fonts.yaml drifted between host and firmware")


def _sfnt(extra: bytes = b"") -> bytes:
    """A minimal but structurally-valid sfnt (TrueType) blob: signature + a 1-entry
    table directory whose table fits in the file.  Truncating it makes the table
    run past EOF, which _validate_sfnt rejects."""
    import struct
    body = b"PolyKybdTestFont" + extra
    head = struct.pack(">4sHHHH", b"\x00\x01\x00\x00", 1, 16, 0, 0)   # 12 bytes
    offset = 12 + 16
    entry = struct.pack(">4sIII", b"glyf", 0, offset, len(body))      # 16 bytes
    return head + entry + body


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = os.path.join(self.tmp.name, "cache")
        # a fake but structurally-valid "remote" font served over file://
        src = os.path.join(self.tmp.name, "remote.ttf")
        self.payload = _sfnt(b"x" * 4000)
        with open(src, "wb") as f:
            f.write(self.payload)
        self.font = fdl.NotoFont("Fake", pathlib.Path(src).as_uri(), "Fake-Regular.ttf")

    def test_download_and_skip(self):
        seen = []
        path = fdl.download_font(self.font, dest_dir=self.cache,
                                 progress_cb=lambda d, t: seen.append(d))
        self.assertTrue(os.path.exists(path))
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), self.payload)
        self.assertTrue(fdl.is_downloaded(self.font, self.cache))
        self.assertTrue(seen and seen[-1] == len(self.payload))
        # second call skips (returns same path); no temp .part files left behind
        # (download_font uses a randomized *.part name, so scan the cache dir).
        again = fdl.download_font(self.font, dest_dir=self.cache)
        self.assertEqual(again, path)
        self.assertEqual([p for p in os.listdir(self.cache) if p.endswith(".part")], [])

    def test_not_downloaded_initially(self):
        self.assertFalse(fdl.is_downloaded(self.font, self.cache))
        self.assertEqual(fdl.local_path(self.font, self.cache),
                         os.path.join(self.cache, "Fake-Regular.ttf"))

    def test_validate_sfnt_rejects_truncation(self):
        full = _sfnt(b"y" * 2000)
        p = os.path.join(self.tmp.name, "full.ttf")
        with open(p, "wb") as f:
            f.write(full)
        self.assertTrue(fdl._validate_sfnt(p))
        with open(p, "wb") as f:
            f.write(full[:len(full) - 500])         # drop the tail → table past EOF
        self.assertFalse(fdl._validate_sfnt(p))
        with open(p, "wb") as f:
            f.write(b"<html>error</html>")          # not a font at all
        self.assertFalse(fdl._validate_sfnt(p))

    def test_rejects_non_font_download(self):
        bad = os.path.join(self.tmp.name, "bad.ttf")
        with open(bad, "wb") as f:
            f.write(b"NOT A FONT" * 100)
        font = fdl.NotoFont("Bad", pathlib.Path(bad).as_uri(), "Bad-Regular.ttf")
        with self.assertRaises(fdl.DownloadError):
            fdl.download_font(font, dest_dir=self.cache)
        # nothing cached, no leftover .part
        self.assertFalse(fdl.is_downloaded(font, self.cache))
        self.assertFalse(os.path.exists(fdl.local_path(font, self.cache)))
        self.assertEqual([p for p in os.listdir(self.cache) if p.endswith(".part")], [])

    def test_corrupt_cache_is_redownloaded(self):
        # a previously-cached truncated file must be treated as missing and re-fetched
        os.makedirs(self.cache, exist_ok=True)
        final = fdl.local_path(self.font, self.cache)
        with open(final, "wb") as f:
            f.write(self.payload[:20])              # truncated → invalid
        self.assertFalse(fdl.is_downloaded(self.font, self.cache))
        path = fdl.download_font(self.font, dest_dir=self.cache)   # overwrites the bad file
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), self.payload)
        self.assertTrue(fdl.is_downloaded(self.font, self.cache))

    def test_force_redownloads_valid_cache(self):
        fdl.download_font(self.font, dest_dir=self.cache)
        # marker file alongside to prove force re-runs the transfer (overwrites)
        final = fdl.local_path(self.font, self.cache)
        os.utime(final, (0, 0))                     # set mtime to epoch
        fdl.download_font(self.font, dest_dir=self.cache, force=True)
        self.assertNotEqual(os.path.getmtime(final), 0)   # rewritten


if __name__ == "__main__":
    unittest.main()
