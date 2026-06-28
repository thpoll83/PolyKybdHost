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


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = os.path.join(self.tmp.name, "cache")
        # a fake "remote" font file served over file://
        src = os.path.join(self.tmp.name, "remote.ttf")
        self.payload = b"FAKEFONT" * 1000
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
        # second call skips (no .part left, returns same path)
        again = fdl.download_font(self.font, dest_dir=self.cache)
        self.assertEqual(again, path)
        self.assertFalse(os.path.exists(path + ".part"))

    def test_not_downloaded_initially(self):
        self.assertFalse(fdl.is_downloaded(self.font, self.cache))
        self.assertEqual(fdl.local_path(self.font, self.cache),
                         os.path.join(self.cache, "Fake-Regular.ttf"))


if __name__ == "__main__":
    unittest.main()
