"""Tests for polyhost.services.fontpack_bundle — bundled-pack discovery and the
pure auto-flash decision."""
import binascii
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from polyhost.services import fontpack_bundle as fb


def _make_pack(content_version=7, abi=1, body=b'\xAB' * 64) -> bytes:
    total = 32 + len(body)
    crc = binascii.crc32(body) & 0xFFFFFFFF
    hdr = struct.pack("<4sHHIIIIII", b"PlyF", abi, 0, content_version, 3, 32, total, crc, 0)
    return hdr + body


# ---------------------------------------------------------------------------
# decide_auto_flash (pure)
# ---------------------------------------------------------------------------

class TestDecideAutoFlash(unittest.TestCase):

    def _bundled(self, ver=7, abi=1):
        return {"abi_version": abi, "content_version": ver, "font_count": 3}

    def _device(self, present=True, ver=5, abi=1):
        return {"present": present, "abi": abi, "content_version": ver, "font_count": 3}

    def test_older_keyboard_flashes(self):
        should, reason = fb.decide_auto_flash(True, self._device(ver=5), self._bundled(ver=7))
        self.assertTrue(should)
        self.assertIn("older", reason)

    def test_missing_pack_flashes(self):
        should, reason = fb.decide_auto_flash(True, self._device(present=False, ver=0), self._bundled())
        self.assertTrue(should)
        self.assertIn("no font pack", reason)

    def test_up_to_date_does_not_flash(self):
        should, reason = fb.decide_auto_flash(True, self._device(ver=7), self._bundled(ver=7))
        self.assertFalse(should)
        self.assertIn("up to date", reason)

    def test_newer_keyboard_never_downgrades(self):
        should, _ = fb.decide_auto_flash(True, self._device(ver=9), self._bundled(ver=7))
        self.assertFalse(should)

    def test_abi_mismatch_skips(self):
        should, reason = fb.decide_auto_flash(True, self._device(abi=2, ver=0, present=False),
                                              self._bundled(abi=1))
        self.assertFalse(should)
        self.assertIn("ABI", reason)

    def test_no_bundled_pack_skips(self):
        should, reason = fb.decide_auto_flash(True, self._device(), None)
        self.assertFalse(should)
        self.assertIn("no bundled", reason)

    def test_status_query_failed_skips(self):
        should, reason = fb.decide_auto_flash(False, None, self._bundled())
        self.assertFalse(should)
        self.assertIn("status", reason)

    def test_self_terminating_after_flash(self):
        # Model a flash: device was v5, becomes v7; re-deciding must NOT flash again.
        should, _ = fb.decide_auto_flash(True, self._device(ver=5), self._bundled(ver=7))
        self.assertTrue(should)
        should2, _ = fb.decide_auto_flash(True, self._device(ver=7), self._bundled(ver=7))
        self.assertFalse(should2)


# ---------------------------------------------------------------------------
# bundled_pack_path / bundled_pack_info
# ---------------------------------------------------------------------------

class TestBundledPackDiscovery(unittest.TestCase):

    def test_override_path_used_when_present(self):
        with tempfile.NamedTemporaryFile(suffix=".plyf", delete=False) as f:
            f.write(_make_pack(content_version=11))
            path = f.name
        try:
            self.assertEqual(fb.bundled_pack_path(path), path)
            p, info = fb.bundled_pack_info(path)
            self.assertEqual(p, path)
            self.assertEqual(info["content_version"], 11)
        finally:
            os.unlink(path)

    def test_override_missing_returns_none(self):
        self.assertIsNone(fb.bundled_pack_path("/no/such/pack.plyf"))
        self.assertEqual(fb.bundled_pack_info("/no/such/pack.plyf"), (None, None))

    def test_no_res_dir_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(fb, "_res_dir", return_value=Path(d) / "missing"):
                self.assertIsNone(fb.bundled_pack_path())

    def test_empty_res_dir_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(fb, "_res_dir", return_value=Path(d)):
                self.assertIsNone(fb.bundled_pack_path())

    def test_single_pack_in_res_dir(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "fonts.plyf").write_bytes(_make_pack(content_version=4))
            with patch.object(fb, "_res_dir", return_value=Path(d)):
                p, info = fb.bundled_pack_info()
                self.assertTrue(p.endswith("fonts.plyf"))
                self.assertEqual(info["content_version"], 4)

    def test_multiple_packs_picks_highest_version(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.plyf").write_bytes(_make_pack(content_version=3))
            (Path(d) / "b.plyf").write_bytes(_make_pack(content_version=9))
            (Path(d) / "c.plyf").write_bytes(_make_pack(content_version=5))
            with patch.object(fb, "_res_dir", return_value=Path(d)):
                _, info = fb.bundled_pack_info()
                self.assertEqual(info["content_version"], 9)

    def test_invalid_pack_file_returns_none_info(self):
        with tempfile.NamedTemporaryFile(suffix=".plyf", delete=False) as f:
            f.write(b"not a pack")
            path = f.name
        try:
            self.assertEqual(fb.bundled_pack_info(path), (None, None))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
