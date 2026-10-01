"""FwUf2Downloader: the .uf2 for a manual BOOTSEL flash (services/updater.py)."""
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from polyhost.services import updater


def _uf2(blocks=2) -> bytes:
    block = struct.pack("<II", updater.UF2_MAGIC_START0, 0x9E5D5157) + bytes(504)
    return block * blocks


def _release(uf2_url="https://example.com/dl/polykybd_split72_default.uf2"):
    return updater.FwUpReleaseInfo(
        tag="PolyKybd-fw-v1.4.1", version="1.4.1",
        bin_url="https://example.com/dl/polykybd_split72_default.bin",
        uf2_url=uf2_url, html_url="https://example.com/release", published_at="")


def _get(content):
    resp = mock.MagicMock()
    resp.content = content
    resp.raise_for_status.return_value = None
    resp.__enter__.return_value = resp
    return resp


class FwUf2DownloaderTest(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.result = None

    def _run(self, release, content=b""):
        def done(*a):
            self.result = a
        with mock.patch.object(updater, "check_fw_latest", return_value=release) as chk, \
             mock.patch.object(updater.requests, "get", return_value=_get(content)):
            t = updater.FwUf2Downloader(self.dir, on_finished=done)
            t.run()                      # synchronously: no thread needed to test it
        return chk

    def test_saves_the_release_uf2_under_its_own_name(self):
        data = _uf2()
        chk = self._run(_release(), data)
        ok, err, path, page = self.result
        self.assertTrue(ok, err)
        self.assertEqual(Path(path).name, "polykybd_split72_default.uf2")
        self.assertEqual(Path(path).read_bytes(), data)
        self.assertEqual(page, "https://example.com/release")
        # Asked against 0, so the newest release comes back whatever is installed.
        chk.assert_called_once_with("0")
        self.assertEqual([p.name for p in self.dir.iterdir()], [Path(path).name])

    def test_a_page_that_is_not_a_uf2_is_refused(self):
        self._run(_release(), b"<html>rate limited</html>" + bytes(487))
        ok, err, path, page = self.result
        self.assertFalse(ok)
        self.assertIn("not a UF2", err)
        self.assertEqual(path, "")
        self.assertEqual(page, "https://example.com/release")
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_a_release_without_a_uf2_points_at_the_page(self):
        self._run(_release(uf2_url=""))
        ok, err, _, page = self.result
        self.assertFalse(ok)
        self.assertIn("no firmware .uf2", err)
        self.assertEqual(page, "https://example.com/release")

    def test_no_release_at_all(self):
        self._run(None)
        ok, _, _, page = self.result
        self.assertFalse(ok)
        self.assertTrue(page.endswith("/releases/latest"))


if __name__ == "__main__":
    unittest.main()
