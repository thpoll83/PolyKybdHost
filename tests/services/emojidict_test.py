"""Tests for services/emojidict.py and the shipped emoji search dictionaries
(polyhost/res/emojidict, imported from qmk emoji_dict.py build-all)."""
import gzip
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from polyhost.device import hid_fontpack
from polyhost.services import emojidict


class ShippedDictionaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = emojidict.load_manifest()

    def test_manifest_is_shipped_and_numbered(self):
        self.assertIsNotNone(self.m, "polyhost/res/emojidict/manifest.json missing")
        ds = self.m["dictionaries"]
        self.assertGreaterEqual(len(ds), 79)
        self.assertEqual([d["number"] for d in ds], list(range(len(ds))))
        self.assertEqual(ds[0]["id"], emojidict.DEFAULT_DICT)
        self.assertEqual(self.m["bundle_id"], emojidict.BUNDLE_ID)

    def test_every_file_matches_its_entry(self):
        for d in self.m["dictionaries"]:
            data = gzip.decompress((Path(self.m["_dir"]) / d["file"]).read_bytes())
            self.assertEqual(len(data), d["size"], d["id"])
            self.assertEqual(hashlib.sha256(data).hexdigest()[:16], d["sha256"], d["id"])
            magic, abi, flags, ver = struct.unpack_from("<4sHHI", data)
            self.assertEqual((magic, flags & 1), (b"PlyF", 1), d["id"])
            self.assertEqual(ver, (d["number"] << 8) | d["revision"], d["id"])
            self.assertEqual(ver, d["content_version"], d["id"])
            self.assertLessEqual(len(data), self.m["slot_size"], d["id"])
            self.assertTrue(hid_fontpack.validate_fontpack(data)[0], d["id"])

    def test_identify_and_label(self):
        de = emojidict.find(self.m, "de")
        self.assertEqual(emojidict.identify(self.m, de["content_version"]), (de, de["revision"]))
        self.assertEqual(emojidict.identify(self.m, 0), (None, 0))
        self.assertEqual(emojidict.label(de), "Deutsch — German")
        self.assertEqual(emojidict.label(emojidict.find(self.m, "en")), "English")

    def test_bundle_entry_unpacks_once_and_falls_back_to_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            b = emojidict.bundle_entry(self.m, "zh-HK@cangjie", Path(tmp))
            self.assertEqual((b["index"], b["kind"], b["dict_id"]), (9, "emojidict", "zh-HK@cangjie"))
            self.assertEqual(Path(b["path"]).stat().st_size, b["size"])
            self.assertEqual(emojidict.bundle_entry(self.m, "xx", Path(tmp))["dict_id"], "en")


class UserFile(unittest.TestCase):
    def test_a_dictionary_file_is_an_entry_with_its_own_version(self):
        m = emojidict.load_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            path = emojidict.unpacked_path(m, emojidict.find(m, "ru"), Path(tmp))
            e, err = emojidict.user_entry(path)
        self.assertEqual(err, "")
        self.assertEqual((e["index"], e["kind"], e["dict_id"], e["path"]), (9, "emojidict", "file", path))
        self.assertEqual(e["content_version"], emojidict.find(m, "ru")["content_version"])

    def test_files_that_are_not_dictionaries_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.plyd"
            empty.write_bytes(hid_fontpack.build_empty_pack())
            big = Path(tmp) / "big.plyd"
            big.write_bytes(b"\0" * (emojidict.SLOT_SIZE + 1))
            self.assertIn("not an emoji search dictionary", emojidict.user_entry(str(empty))[1])
            self.assertIn("larger than", emojidict.user_entry(str(big))[1])
            self.assertIn("cannot read", emojidict.user_entry(str(Path(tmp) / "none.plyd"))[1])

    def test_user_revision_is_above_every_shipped_one(self):
        for d in emojidict.load_manifest()["dictionaries"]:
            self.assertLess(d["revision"], emojidict.USER_REVISION, d["id"])


class Staleness(unittest.TestCase):
    def test_dictionary_is_stale_on_any_mismatch(self):
        b = {"index": 9, "kind": "emojidict", "content_version": (0 << 8) | 1}
        self.assertTrue(hid_fontpack.bundle_is_stale(b, (1 << 8) | 1))   # de held, en wanted
        self.assertFalse(hid_fontpack.bundle_is_stale(b, (0 << 8) | 1))
        f = {"index": 0, "content_version": 2}
        self.assertFalse(hid_fontpack.bundle_is_stale(f, 3))              # fonts never downgrade

    def test_slot_9_is_never_assumed(self):
        b = {"index": 9, "kind": "emojidict", "content_version": 1}
        self.assertFalse(hid_fontpack.device_has_slot({}, b))
        self.assertFalse(hid_fontpack.device_has_slot({0: 1}, b))
        self.assertTrue(hid_fontpack.device_has_slot({9: 0}, b))


if __name__ == "__main__":
    unittest.main()
