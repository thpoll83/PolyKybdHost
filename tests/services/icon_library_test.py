"""The PlyI overlay icon library: format, the shipped bundle and its frozen ids.

The firmware half is base/icon_lib.c (make test:polykybd_icon_lib). These pin the
host half of the same contract: what `build` writes is what `parse` -- which
applies the firmware's own checks -- reads back, pixel for pixel.
"""
import binascii
import contextlib
import hashlib
import io
import json
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from polyhost.services import icon_library as il

ROOT = Path(__file__).resolve().parents[2]
FONTPACK = ROOT / "polyhost" / "res" / "fontpack"


# What `build_icon_library.select()` picks from today's templates. It decodes
# every shipped template for every modifier and takes about a minute, and three
# tests below need it, so it is computed once per run and shared. Each of them
# re-ran it before, together over the test runner's two-minute limit per test.
_SELECTED = None


def _builder():
    """`scripts/build_icon_library.py` as a module, or a SkipTest when the image
    stack it needs is missing."""
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import build_icon_library as bil
    except Exception as exc:         # the builder needs the image stack
        raise unittest.SkipTest(f"icon library builder unavailable: {exc}") from exc
    return bil


def _selected(bil):
    global _SELECTED
    if _SELECTED is None:
        _SELECTED = bil.select()
    return _SELECTED


def _run_check(case, bil):
    """`build_icon_library.py --check` in this process, on the shared selection.
    Returns (exit code, stdout)."""
    patcher = mock.patch.object(bil, "select", return_value=_selected(bil))
    patcher.start()
    case.addCleanup(patcher.stop)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = bil.main(["--check"])
    return rc, out.getvalue()


def frame(pixels):
    """A packed 72x40 frame with the given (x, y) pixels set."""
    buf = bytearray(il.FRAME_BYTES)
    for x, y in pixels:
        bit = y * il.FRAME_W + x
        buf[bit >> 3] |= 0x80 >> (bit & 7)
    return bytes(buf)


def box(x0, y0, w, h):
    return frame([(x, y) for y in range(y0, y0 + h) for x in range(x0, x0 + w)])


class FormatTest(unittest.TestCase):

    def test_round_trip_keeps_every_pixel_and_its_placement(self):
        frames = [box(40, 2, 10, 8), frame([(34, 0), (71, 39), (50, 20)]), box(36, 1, 36, 38)]
        cver, back = il.parse(il.build(frames, 5))
        self.assertEqual(cver, 5)
        self.assertEqual(back, frames)

    def test_the_header_is_PlyI_with_the_shared_layout(self):
        data = il.build([box(40, 2, 3, 3)], 1)
        magic, abi = struct.unpack_from("<4sH", data)
        self.assertEqual(magic, b"PlyI")
        self.assertEqual(abi, 2)
        self.assertEqual(len(data) % 4, 0)

    def test_it_is_byte_reproducible(self):
        frames = [box(40 + i % 20, i % 30, 5, 5) for i in range(50)]
        self.assertEqual(il.build(frames, 3), il.build(frames, 3))

    def test_bitmaps_past_64_KB_split_into_contiguous_records(self):
        """GFXglyph.bitmapOffset is 16 bits, so one record addresses 64 KB."""
        frames = [box(34, 0, 38, 40) for _ in range(400)]    # 190 B each, 76 KB
        data = il.build(frames, 1)
        n_rec = struct.unpack_from("<I", data, 12)[0]
        self.assertEqual(n_rec, 2)
        self.assertEqual(il.parse(data)[1], frames)

    def test_the_empty_bundle_is_the_wipe_sentinel(self):
        data = il.build([], 2)
        self.assertEqual(len(data), 32)
        self.assertEqual(il.parse(data), (2, []))

    def test_a_blank_frame_is_refused(self):
        with self.assertRaises(il.IconLibraryError):
            il.build([bytes(il.FRAME_BYTES)], 1)

    def test_a_font_bundle_is_not_an_icon_bundle(self):
        data = bytearray(il.build([box(40, 2, 3, 3)], 1))
        data[3:4] = b"F"
        with self.assertRaises(il.IconLibraryError):
            il.parse(bytes(data))

    def test_a_corrupt_body_is_refused(self):
        data = bytearray(il.build([box(40, 2, 3, 3)], 1))
        data[-1] ^= 1
        with self.assertRaises(il.IconLibraryError):
            il.parse(bytes(data))

    def test_a_box_outside_the_keycap_is_refused(self):
        data = bytearray(il.build([box(40, 2, 3, 3)], 1))
        glyph_off = struct.unpack_from("<I", data, 32 + 4)[0]
        data[glyph_off + 5] = 70                 # xOffset: 70 + 3 > 72
        crc = binascii.crc32(bytes(data[32:])) & 0xFFFFFFFF
        struct.pack_into("<I", data, 24, crc)
        with self.assertRaises(il.IconLibraryError):
            il.parse(bytes(data))

    def _recrc(self, data):
        struct.pack_into("<I", data, 24, binascii.crc32(bytes(data[32:])) & 0xFFFFFFFF)
        return bytes(data)

    def test_a_glyph_table_past_the_end_is_refused_not_crashed(self):
        """CodeRabbit on #291: a CRC-valid bundle whose offsets overrun it
        raised struct.error, which the send path does not catch."""
        data = bytearray(il.build([box(40, 2, 3, 3)], 1))
        struct.pack_into("<I", data, 32 + 4, len(data) - 2)     # glyph_off
        with self.assertRaises(il.IconLibraryError):
            il.parse(self._recrc(data))

    def test_a_bitmap_past_the_end_is_refused_not_crashed(self):
        data = bytearray(il.build([box(40, 2, 3, 3)], 1))
        glyph_off = struct.unpack_from("<I", data, 32 + 4)[0]
        struct.pack_into("<H", data, glyph_off, 0xFFFF)          # bitmapOffset
        with self.assertRaises(il.IconLibraryError):
            il.parse(self._recrc(data))

    def test_frame_index_maps_pixels_to_the_first_id(self):
        frames = [box(40, 2, 3, 3), box(50, 2, 3, 3), box(40, 2, 3, 3)]
        _, index = il.frame_index(il.build(frames, 1))
        self.assertEqual(index, {frames[0]: 0, frames[1]: 1})


class ShippedLibraryTest(unittest.TestCase):

    def setUp(self):
        self.data = (FONTPACK / "icons.plyi").read_bytes()
        self.ids = yaml.safe_load((FONTPACK / "icon_ids.yaml").read_text(encoding="utf-8"))

    def test_it_parses_and_fits_its_slot(self):
        _, frames = il.parse(self.data)
        self.assertGreater(len(frames), 0)
        self.assertLessEqual(len(self.data), 0x80000)

    def test_ids_are_dense_from_zero_and_match_the_glyph_count(self):
        """⚠️ Append-only and frozen: the id IS the glyph index, so a gap or a
        reorder would make every later fill draw the wrong icon."""
        _, frames = il.parse(self.data)
        self.assertEqual([e["id"] for e in self.ids], list(range(len(frames))))

    def test_every_id_key_names_its_glyph(self):
        import hashlib
        _, frames = il.parse(self.data)
        for e, f in zip(self.ids, frames):
            self.assertEqual(e["key"], hashlib.sha256(f).hexdigest()[:20], e["id"])

    def test_the_manifest_entry_matches_the_file(self):
        import hashlib
        import json
        manifest = json.loads((FONTPACK / "bundles.json").read_text(encoding="utf-8"))
        entry = next(b for b in manifest["bundles"] if b["id"] == "icons")
        self.assertEqual(entry["index"], il.BUNDLE_ID)
        self.assertEqual(entry["kind"], "icons")
        self.assertEqual(entry["size"], len(self.data))
        self.assertEqual(entry["sha256"], hashlib.sha256(self.data).hexdigest()[:16])
        self.assertEqual(entry["content_version"], il.parse(self.data)[0])

    def test_the_build_is_current(self):
        """The shipped bundle is what the builder makes from today's templates."""
        try:
            import generate_app_overlays  # noqa: F401
        except Exception:
            sys.path.insert(0, str(ROOT / "scripts"))
            try:
                import generate_app_overlays  # noqa: F401
            except Exception as exc:     # the generator needs the image stack
                self.skipTest(f"overlay generator unavailable: {exc}")
        rc, out = _run_check(self, _builder())
        self.assertEqual(rc, 0, out)


class RenumberByUsageTest(unittest.TestCase):
    """The one-time renumbering puts the icons most apps use first, keeps every
    retired icon with its own pixels, and leaves no id gap."""

    def test_ids_follow_usage_and_retired_icons_follow_with_their_pixels(self):
        bil = _builder()
        a, b, c, gone = box(0, 0, 4, 4), box(10, 0, 4, 4), box(20, 0, 4, 4), box(30, 0, 4, 4)
        ids_doc = [{"id": 0, "key": bil._key(a), "name": "a.png"},
                   {"id": 1, "key": bil._key(gone), "name": "gone.png"},
                   {"id": 2, "key": bil._key(b), "name": "b.png"}]
        previous = [a, gone, b]
        selected = {a: "a.png", b: "b.png", c: "c.png"}          # c is new
        usage = {a: 2, b: 9, c: 5}
        table, frames = bil.renumber_by_usage(selected, usage, ids_doc, previous)
        self.assertEqual([e["name"] for e in table], ["b.png", "c.png", "a.png", "gone.png"])
        self.assertEqual([e["id"] for e in table], [0, 1, 2, 3])
        self.assertEqual(frames, [b, c, a, gone])
        self.assertEqual(table[3]["key"], bil._key(gone))

    def test_a_retired_frame_that_does_not_match_its_key_stops_the_build(self):
        """icon_ids.yaml out of step with icons.plyi must not write another
        icon's pixels under a retired id, in either assignment path."""
        bil = _builder()
        a, gone, other = box(0, 0, 4, 4), box(30, 0, 4, 4), box(40, 0, 4, 4)
        ids_doc = [{"id": 0, "key": bil._key(a), "name": "a.png"},
                   {"id": 1, "key": bil._key(gone), "name": "gone.png"}]
        previous = [a, other]                       # id 1 holds the wrong pixels
        for assign in (lambda: bil.assign_ids({a: "a.png"}, ids_doc, previous),
                       lambda: bil.renumber_by_usage({a: "a.png"}, {a: 1}, ids_doc, previous)):
            with self.assertRaises(SystemExit) as cm:
                assign()
            self.assertIn("gone.png", str(cm.exception))

    def test_it_cannot_run_with_check(self):
        bil = _builder()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            bil.main(["--check", "--renumber-by-usage"])


class CheckToleratesPendingIconsTest(unittest.TestCase):
    """`--check` must not force a rebuild for every new icon. A library one
    rebuild behind the templates passes and lists the new icons as pending
    (they are uploaded as bitmaps meanwhile). A library that disagrees with
    its own frozen id table still fails."""

    def setUp(self):
        self.bil = bil = _builder()
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        ids = yaml.safe_load(bil.IDS_FILE.read_text(encoding="utf-8"))
        _ver, frames = il.parse(bil.PLYI_FILE.read_bytes())
        manifest = json.loads(bil.MANIFEST.read_text(encoding="utf-8"))
        # The library as it was before its two newest icons were appended.
        self.dropped = [e["name"] for e in ids[-2:]]
        self.dropped_keys = {e["key"] for e in ids[-2:]}
        old = il.build(frames[:-2], 1)
        entry = next(b for b in manifest["bundles"] if b["id"] == "icons")
        entry.update(content_version=1, size=len(old),
                     sha256=hashlib.sha256(old).hexdigest()[:16])
        self.ids_path, self.plyi, self.man = tmp / "ids.yaml", tmp / "i.plyi", tmp / "b.json"
        self.ids_path.write_text(
            "# Frozen overlay icon ids (HID cmd 42). APPEND-ONLY: an id never changes\n"
            "# and a retired icon keeps its entry. Written by scripts/build_icon_library.py.\n"
            + yaml.safe_dump(ids[:-2], sort_keys=False, width=200), encoding="utf-8")
        self.plyi.write_bytes(old)
        self.man.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        for name, path in (("IDS_FILE", self.ids_path), ("PLYI_FILE", self.plyi),
                           ("MANIFEST", self.man)):
            patcher = mock.patch.object(bil, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _check(self):
        return _run_check(self, self.bil)

    def test_a_library_behind_the_templates_passes_and_lists_pending(self):
        # The pending list names an image by the file the selection found it
        # in, which need not be the name its id was frozen under: another app
        # can ship the same pixels under another file name (Cinema 4D's
        # zoomselected.png is zoomsel.png). Match the dropped ids by key.
        selected = _selected(self.bil)
        names = [n for f, n in selected.items() if self.bil._key(f) in self.dropped_keys]
        self.assertEqual(len(names), len(self.dropped_keys), self.dropped)
        rc, out = self._check()
        self.assertEqual(rc, 0, out)
        # The shipped library may itself be behind, so only the two dropped
        # icons are certain to be listed, not an exact count.
        self.assertIn("pending: ", out)
        for name in names:
            self.assertIn(name, out)

    def test_a_library_that_disagrees_with_its_id_table_fails(self):
        self.plyi.write_bytes(il.build(il.parse(self.plyi.read_bytes())[1][:-1], 1))
        rc, out = self._check()
        self.assertEqual(rc, 1, out)


if __name__ == "__main__":
    unittest.main()
