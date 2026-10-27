"""The game-art reader (polyhost/services/game_assets) on synthetic game files.

EA's files may not be committed, so the tests write small MIX, shape and palette
files with encoders that exist only here. They check the decoders against those
encoders, that the files are found in a configured folder without regard to
case, and that a build replaces exactly the C&C overlay cells it has art for,
read back through the same `ImageConverter` the device path uses.
"""
import os
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.services import game_assets
from polyhost.services.game_assets import cnc_classic, westwood

# --------------------------------------------------------------------------- #
# encoders (test-only)
# --------------------------------------------------------------------------- #

def lcw_literal(data: bytes) -> bytes:
    """LCW with literal runs only, then the end marker."""
    out = bytearray()
    for i in range(0, len(data), 63):
        chunk = data[i:i + 63]
        out.append(0x80 | len(chunk))
        out += chunk
    out.append(0x80)
    return bytes(out)


def write_mix(path: Path, files: dict) -> None:
    body, entries = bytearray(), []
    for name, data in files.items():
        entries.append((westwood.td_hash(name), len(body), len(data)))
        body += data
    head = struct.pack("<HI", len(entries), len(body))
    for e in sorted(entries):
        head += struct.pack("<III", *e)
    path.write_bytes(head + bytes(body))


def write_shp(frames: list) -> bytes:
    """A TD shape file with every frame LCW-compressed (format 0x80)."""
    h, w = frames[0].shape
    n = len(frames)
    data_start = 14 + 8 * (n + 2)
    blobs, offsets, pos = [], [], data_start
    for f in frames:
        blob = lcw_literal(f.astype(np.uint8).tobytes())
        offsets.append(pos)
        blobs.append(blob)
        pos += len(blob)
    out = struct.pack("<HHHHHHH", n, 0, 0, w, h, 0, 0)
    for off in offsets:
        out += struct.pack("<II", off | (0x80 << 24), 0)
    out += struct.pack("<II", pos, 0) + struct.pack("<II", 0, 0)
    return out + b"".join(blobs)


def write_d2(frames: list) -> bytes:
    """A Dune-2-style shape file, every frame uncompressed (flag 2) with the
    zero-run encoding."""
    blobs = []
    for f in frames:
        h, w = f.shape
        enc = bytearray()
        flat = f.astype(np.uint8).tobytes()
        i = 0
        while i < len(flat):
            if flat[i] == 0:
                run = 1
                while i + run < len(flat) and flat[i + run] == 0 and run < 255:
                    run += 1
                enc += bytes([0, run])
                i += run
            else:
                enc.append(flat[i])
                i += 1
        blobs.append(struct.pack("<HBHBHH", 2, h, w, h, 10 + len(enc), w * h) + bytes(enc))
    n = len(frames)
    pos = 2 + 4 * (n + 1)
    offs = []
    for b in blobs:
        offs.append(pos - 2)
        pos += len(b)
    offs.append(pos - 2)
    return struct.pack("<H", n) + b"".join(struct.pack("<I", o) for o in offs) + b"".join(blobs)


def blob_frame(h, w, seed, colour=40):
    """A filled ellipse with a lighter band, different per seed, so every sprite
    and facing has a distinct shape."""
    yy, xx = np.mgrid[0:h, 0:w]
    rx, ry = w / 2 - 1 - seed % 3, h / 2 - 1 - (seed // 3) % 3
    inside = ((xx - w / 2) / rx) ** 2 + ((yy - h / 2) / ry) ** 2 <= 1
    f = np.where(inside, colour, 0).astype(np.uint8)
    f[inside & (xx % 5 == seed % 5)] = colour + 30
    return f


# Every sprite the C&C reader draws, with enough frames for the facings and
# turret frames it reads.
SPRITES = {
    "e1": (6, 20, 10), "jeep": (64, 24, 24), "apc": (32, 24, 24), "mtnk": (64, 24, 24),
    "htnk": (64, 24, 24), "msam": (96, 24, 24), "orca": (32, 24, 36), "a10": (32, 30, 30),
    "tran": (32, 48, 48), "harv": (32, 24, 24), "bggy": (64, 24, 24), "bike": (32, 24, 24),
    "ltnk": (64, 24, 24), "ftnk": (32, 24, 24), "stnk": (32, 24, 24), "arty": (32, 24, 24),
    "mlrs": (64, 24, 24), "heli": (32, 29, 46), "lrotor": (12, 15, 29), "rrotor": (12, 15, 29),
    "fact": (1, 48, 72), "pyle": (1, 48, 48), "weap": (1, 72, 72), "weap2": (1, 72, 72),
    "hq": (1, 48, 48), "hand": (1, 72, 48), "afld": (1, 48, 96),
}


def make_game_files(folder: Path, upper: bool = True) -> None:
    """CONQUER.MIX, TEMPERAT.MIX and CCLOCAL.MIX with synthetic content."""
    conquer = {}
    for k, (name, (n, h, w)) in enumerate(SPRITES.items()):
        conquer[f"{name}.shp"] = write_shp([blob_frame(h, w, k + i) for i in range(n)])
    pal = bytes(min(63, i // 2) for i in range(256) for _ in range(3))
    mouse = write_d2([blob_frame(24, 24, i, colour=60) for i in range(120)])
    cap = str.upper if upper else str.lower
    write_mix(folder / cap("conquer.mix"), conquer)
    write_mix(folder / cap("temperat.mix"), {"temperat.pal": pal})
    write_mix(folder / cap("cclocal.mix"), {"mouse.shp": mouse})


# --------------------------------------------------------------------------- #

class WestwoodDecoderTest(unittest.TestCase):

    def test_hash_ignores_case_and_differs_by_name(self):
        self.assertEqual(westwood.td_hash("conquer.mix"), westwood.td_hash("CONQUER.MIX"))
        self.assertNotEqual(westwood.td_hash("e1.shp"), westwood.td_hash("e2.shp"))

    def test_mix_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "x.mix"
            write_mix(path, {"a.shp": b"alpha", "b.pal": b"beta-data"})
            mix = westwood.Mix.open(path)
            self.assertEqual(mix.get("A.SHP"), b"alpha")
            self.assertEqual(mix.get("b.pal"), b"beta-data")
            self.assertIsNone(mix.get("missing.shp"))

    def test_lcw_every_command(self):
        src = bytes([
            0x83, 1, 2, 3,                  # literal 1 2 3
            0x00, 0x03,                     # relative copy: 3 bytes from 3 back
            0xC0, 0x00, 0x00,               # short absolute copy: 3 bytes from 0
            0xFE, 0x04, 0x00, 0x09,         # fill: 4 x 9
            0xFF, 0x02, 0x00, 0x01, 0x00,   # long absolute copy: 2 bytes from 1
            0x80,                           # end
        ])
        self.assertEqual(westwood.lcw(src, 15), bytes([1, 2, 3, 1, 2, 3, 1, 2, 3, 9, 9, 9, 9, 2, 3]))

    def test_xor_delta_runs_and_skips(self):
        src = bytes([0x02, 5, 6,            # literal 5 6
                     0x82,                  # skip 2
                     0x00, 3, 7,            # fill 3 x 7
                     0x80, 0x00, 0x00])     # end
        self.assertEqual(westwood.xor_delta(src, 8), bytes([5, 6, 0, 0, 7, 7, 7, 0]))

    def test_td_shape_frames(self):
        frames = [blob_frame(10, 12, i) for i in range(3)]
        out = westwood.shp_frames(write_shp(frames))
        self.assertEqual(len(out), 3)
        for a, b in zip(frames, out):
            np.testing.assert_array_equal(a, b)

    def test_td_shape_xor_frame_against_previous(self):
        base = blob_frame(6, 8, 0)
        delta = bytes([0x03, 1, 2, 3, 0x80, 0x00, 0x00])   # XOR onto the base row 0
        base_blob = lcw_literal(base.tobytes())
        n = 2
        start = 14 + 8 * (n + 2)
        head = struct.pack("<HHHHHHH", n, 0, 0, 8, 6, 0, 0)
        head += struct.pack("<II", start | (0x80 << 24), 0)
        head += struct.pack("<II", (start + len(base_blob)) | (0x20 << 24), 0)
        head += struct.pack("<II", start + len(base_blob) + len(delta), 0) + struct.pack("<II", 0, 0)
        out = westwood.shp_frames(head + base_blob + delta)
        expected = base.copy()
        expected[0, :3] ^= np.array([1, 2, 3], np.uint8)
        np.testing.assert_array_equal(out[1], expected)

    def test_d2_shape_frames(self):
        frames = [blob_frame(9, 11, i) for i in range(4)]
        out = westwood.shp_d2_frames(write_d2(frames))
        for a, b in zip(frames, out):
            np.testing.assert_array_equal(a, b)


class FindDataTest(unittest.TestCase):

    def test_configured_folder_in_either_case(self):
        for upper in (True, False):
            with tempfile.TemporaryDirectory() as d:
                make_game_files(Path(d), upper=upper)
                files = cnc_classic.find_data(d)
                self.assertEqual(sorted(files), ["cclocal.mix", "conquer.mix", "temperat.mix"])

    def test_a_folder_without_the_required_files_is_not_used(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "CONQUER.MIX").write_bytes(b"")
            self.assertIsNone(cnc_classic.find_data(d))

    def test_remastered_layout_is_found_under_any_cd_folder(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d)
            cd = lib / "steamapps" / "common" / "CnCRemastered" / "Data" / "CNCDATA" / "TIBERIAN_DAWN" / "CD1"
            cd.mkdir(parents=True)
            make_game_files(cd)
            orig = cnc_classic._steam_libraries
            cnc_classic._steam_libraries = lambda: [lib]
            try:
                files = cnc_classic.find_data("")
            finally:
                cnc_classic._steam_libraries = orig
            self.assertEqual(files["conquer.mix"].parent, cd)


class BuildTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name) / "td"
        cls.data.mkdir()
        make_game_files(cls.data)
        cls.cache = Path(cls.tmp.name) / "cache"
        cls.built = {f: cnc_classic.build(cls.cache, str(cls.data), f) for f in cnc_classic.FACTION_NAMES}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @staticmethod
    def _cells(path, mod):
        conv = ImageConverter(DeviceSettings())
        assert conv.open(str(path))
        cells = conv.extract_overlays(mod) or {}
        return {kc: od.all_bytes for kc, od in cells.items()}, conv.no_legend

    def test_without_game_files_there_is_no_copy(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(cnc_classic.build(Path(d), d, "gdi"))

    def test_exactly_the_drawn_keys_change(self):
        """Every key the reader has art for differs from the shipped cell, and
        every other key on both layers is byte-identical to the shipped file."""
        drawn = {Modifier.NO_MOD: {"1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
                                   "W", "E", "R", "T", "S", "X", "G", "Q", "A", "H", "TAB"},
                 Modifier.CTRL: {"1", "2", "3", "4", "5", "6", "7", "8", "9", "0"}}
        for faction, path in self.built.items():
            self.assertIsNotNone(path)
            for mod, keys in drawn.items():
                shipped, shipped_nl = self._cells(cnc_classic.SHIPPED, mod)
                patched, patched_nl = self._cells(path, mod)
                self.assertEqual(shipped_nl, patched_nl, "the no-legend list must carry over")
                want = {KeyCode[f"KC_{k}"].value for k in keys}
                for kc in set(shipped) | set(patched):
                    changed = shipped.get(kc) != patched.get(kc)
                    self.assertEqual(changed, kc in want,
                                     f"{faction} {mod.name} keycode 0x{kc:02x}: "
                                     f"{'changed' if changed else 'unchanged'}")
                for kc in want:
                    self.assertIn(kc, patched, f"{faction} {mod.name} 0x{kc:02x} drew nothing")

    def test_factions_differ_and_are_cached_by_name(self):
        gdi, nod = self.built["gdi"], self.built["nod"]
        self.assertNotEqual(gdi.name, nod.name)
        self.assertIn(".mods.", gdi.name, "the loader picks the channel layout by '.mods.'")
        stamp = os.stat(gdi).st_mtime_ns
        self.assertEqual(cnc_classic.build(self.cache, str(self.data), "gdi"), gdi)
        self.assertEqual(os.stat(gdi).st_mtime_ns, stamp, "a cached copy must not be rebuilt")

    def test_unknown_faction_falls_back_to_gdi(self):
        self.assertEqual(cnc_classic.build(self.cache, str(self.data), "orcs").name, self.built["gdi"].name)

    def test_registry_serves_the_copy_and_respects_the_switch(self):
        settings = {"game_assets_enabled": True, "game_cnc_data_dir": str(self.data),
                    "game_cnc_faction": "nod"}
        orig = game_assets.cache_dir
        game_assets.cache_dir = lambda: self.cache
        try:
            game_assets.start(settings.get).join(60)
            self.assertEqual(game_assets.override_for(cnc_classic.TEMPLATE), str(self.built["nod"]))
            settings["game_assets_enabled"] = False
            game_assets.start(settings.get).join(60)
            self.assertIsNone(game_assets.override_for(cnc_classic.TEMPLATE))
        finally:
            game_assets.cache_dir = orig


if __name__ == "__main__":
    unittest.main()
