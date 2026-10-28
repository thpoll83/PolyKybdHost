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
import unittest.mock as mock
from pathlib import Path

import numpy as np

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.services import game_assets
from polyhost.services.game_assets import build
from polyhost.services.game_assets.westwood_td import reader as westwood_td
from polyhost.services.game_assets.westwood_td import westwood

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


def _rle_zeros(flat: bytes) -> bytes:
    enc = bytearray()
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
    return bytes(enc)


def write_d2(frames: list, compressed=False, table=None, two_byte=False) -> bytes:
    """A Dune-2-style shape file with the zero-run encoding: uncompressed
    (flag 2) or LCW, with or without a colour table (flags 1|4, `frames` then
    hold table indices), with 4- or 2-byte offsets."""
    blobs = []
    for f in frames:
        h, w = f.shape
        enc = _rle_zeros(f.astype(np.uint8).tobytes())
        flags, extra = (0 if compressed else 2), b""
        if table is not None:
            flags |= 1 | 4
            extra = bytes([len(table)]) + bytes(table)
        body = lcw_literal(enc) if compressed else enc
        size = 10 + len(extra) + len(body)
        blobs.append(struct.pack("<HBHBHH", flags, h, w, h, size, len(enc)) + extra + body)
    n = len(frames)
    step, fmt = (2, "<H") if two_byte else (4, "<I")
    pos = 2 + step * (n + 1)
    offs = []
    for b in blobs:
        offs.append(pos - 2)
        pos += len(b)
    offs.append(pos - 2)
    return struct.pack("<H", n) + b"".join(struct.pack(fmt, o) for o in offs) + b"".join(blobs)


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

    def test_a_damaged_size_is_refused_not_padded(self):
        """A header claiming 65535 x 65535 with one byte of data must raise at
        once, not allocate the 4 GiB it claims."""
        start = 14 + 8 * 3
        head = struct.pack("<HHHHHHH", 1, 0, 0, 0xFFFF, 0xFFFF, 0, 0)
        head += struct.pack("<II", start | (0x80 << 24), 0)
        head += struct.pack("<II", start + 2, 0) + struct.pack("<II", 0, 0)
        with self.assertRaises(ValueError):
            westwood.shp_frames(head + bytes([0x81, 7]))
        with self.assertRaises(ValueError):
            westwood._rle_zeros(bytes([5, 0, 3]), 0xFFFF * 0xFFFF)

    def test_d2_lcw_frames_with_a_colour_table_and_two_byte_offsets(self):
        """The layout of TD's MOUSE.SHP: 2-byte offsets, LCW, a colour table."""
        table = [0, 15, 120, 121, 179, 200, 201, 202]
        idx = [np.where(blob_frame(9, 11, i) > 0, 1 + i, 0).astype(np.uint8) for i in range(3)]
        idx[1][4, 2:6] = 6
        data = write_d2(idx, compressed=True, table=table, two_byte=True)
        # The reader tells the offset width from the low byte of the 2nd offset.
        self.assertTrue(struct.unpack_from("<I", data, 2)[0] & 0xFF0000)
        out = westwood.shp_d2_frames(data)
        self.assertEqual(len(out), 3)
        for a, b in zip(idx, out):
            np.testing.assert_array_equal(np.asarray(table, np.uint8)[a], b)

    def test_td_shape_delta_chain_against_a_keyframe(self):
        """0x80 keyframe, 0x20 against the previous frame, 0x40 against the
        keyframe by its offset, then 0x20 against that 0x40 frame."""
        h, w = 6, 8
        key = blob_frame(h, w, 0)
        d1 = bytes([0x02, 9, 9, 0x80, 0x00, 0x00])           # row 0: ^ 9 9
        d2 = bytes([0x88, 0x01, 5, 0x80, 0x00, 0x00])        # skip 8, row 1: ^ 5
        d3 = bytes([0x00, 2, 4, 0x80, 0x00, 0x00])           # fill 2 x 4: ^ 4 4
        key_blob = lcw_literal(key.tobytes())
        n = 4
        start = 14 + 8 * (n + 2)
        offs = [start]
        for b in (key_blob, d1, d2):
            offs.append(offs[-1] + len(b))
        end = offs[-1] + len(d3)
        head = struct.pack("<HHHHHHH", n, 0, 0, w, h, 0, 0)
        head += struct.pack("<II", offs[0] | (0x80 << 24), 0)
        head += struct.pack("<II", offs[1] | (0x20 << 24), 0)
        head += struct.pack("<II", offs[2] | (0x40 << 24), offs[0])
        head += struct.pack("<II", offs[3] | (0x20 << 24), 0)
        head += struct.pack("<II", end, 0) + struct.pack("<II", 0, 0)
        out = westwood.shp_frames(head + key_blob + d1 + d2 + d3)
        f1 = key.copy()
        f1[0, :2] ^= 9
        f2 = key.copy()                                      # from the KEYFRAME, not f1
        f2[1, 0] ^= 5
        f3 = f2.copy()
        f3[0, :2] ^= 4
        for want, got in zip((key, f1, f2, f3), out):
            np.testing.assert_array_equal(want, got)


TEMPLATE = "cnc_remastered_template.mods.png"
SPEC = build.RES / "overlay_sources" / "cnc_remastered" / "cnc_remastered.yaml"
SHIPPED = build.RES / "overlays" / TEMPLATE


def build_copy(cache, folder, faction, hint=None):
    settings = {"game_cnc_data_dir": str(folder), "game_cnc_faction": faction}
    return build.build(TEMPLATE, SPEC, settings.get, Path(cache), hint)


class FindDataTest(unittest.TestCase):

    def setUp(self):
        # No real Steam or EA install may answer for these tests.
        p = mock.patch.object(westwood_td, "_steam_libraries", return_value=[])
        p.start()
        self.addCleanup(p.stop)
        e = mock.patch.dict(os.environ, {"PROGRAMFILES": "", "PROGRAMFILES(X86)": ""})
        e.start()
        self.addCleanup(e.stop)

    def test_configured_folder_in_either_case(self):
        for upper in (True, False):
            with tempfile.TemporaryDirectory() as d:
                make_game_files(Path(d), upper=upper)
                files = westwood_td.find(d)
                self.assertEqual(sorted(files), ["cclocal.mix", "conquer.mix", "temperat.mix"])

    def test_a_folder_without_the_required_files_is_not_used(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "CONQUER.MIX").write_bytes(b"")
            self.assertIsNone(westwood_td.find(d))

    def test_remastered_layout_is_found_under_any_cd_folder(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d)
            cd = lib / "steamapps" / "common" / "CnCRemastered" / "Data" / "CNCDATA" / "TIBERIAN_DAWN" / "CD1"
            cd.mkdir(parents=True)
            make_game_files(cd)
            with mock.patch.object(westwood_td, "_steam_libraries", return_value=[lib]):
                files = westwood_td.find("")
            self.assertEqual(files["conquer.mix"].parent, cd)

    def test_the_running_game_folder_is_searched_first(self):
        """An install in no library the host knows is found from the folder of
        the game's executable, in any case."""
        with tempfile.TemporaryDirectory() as d:
            inst = Path(d) / "Games" / "C&C"
            td = inst / "data" / "CNCDATA" / "Tiberian_Dawn"
            td.mkdir(parents=True)
            make_game_files(td)
            self.assertIsNone(westwood_td.find(""))
            self.assertEqual(westwood_td.find("", hint=inst)["conquer.mix"].parent, td)


class BuildTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name) / "td"
        cls.data.mkdir()
        make_game_files(cls.data)
        cls.cache = Path(cls.tmp.name) / "cache"
        cls.built = {f: build_copy(cls.cache, cls.data, f) for f in ("gdi", "nod")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @staticmethod
    def _cells(path, mod):
        conv = ImageConverter(DeviceSettings())
        if not conv.open(str(path)):
            raise AssertionError(f"cannot open {path}")
        cells = conv.extract_overlays(mod) or {}
        return {kc: od.all_bytes for kc, od in cells.items()}, conv.no_legend

    def test_without_game_files_there_is_no_copy(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(build_copy(d, d, "gdi"))

    def test_exactly_the_drawn_keys_change(self):
        """Every key the reader has art for differs from the shipped cell, and
        every other key on both layers is byte-identical to the shipped file."""
        drawn = {Modifier.NO_MOD: {"1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
                                   "W", "E", "R", "T", "S", "X", "G", "Q", "A", "H", "TAB"},
                 Modifier.CTRL: {"1", "2", "3", "4", "5", "6", "7", "8", "9", "0"}}
        for faction, path in self.built.items():
            self.assertIsNotNone(path)
            for mod, keys in drawn.items():
                shipped, shipped_nl = self._cells(SHIPPED, mod)
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
        self.assertEqual(build_copy(self.cache, self.data, "gdi"), gdi)
        self.assertEqual(os.stat(gdi).st_mtime_ns, stamp, "a cached copy must not be rebuilt")

    def test_unknown_faction_falls_back_to_the_first_choice(self):
        self.assertEqual(build_copy(self.cache, self.data, "orcs").name, self.built["gdi"].name)

    def test_a_build_removes_temp_files_left_by_another_process(self):
        """A host that exits mid-build leaves its temp file; the next process
        removes it, but never a temp file of a build running in this one."""
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d)
            stale = cache / f"x.mods.png.{os.getpid() + 1}.123.tmp"
            mine = cache / f"x.mods.png.{os.getpid()}.456.tmp"
            stale.write_bytes(b"x")
            mine.write_bytes(b"x")
            self.assertIsNotNone(build_copy(cache, self.data, "gdi"))
            self.assertFalse(stale.exists())
            self.assertTrue(mine.exists())

    def test_builds_of_the_same_copy_can_overlap(self):
        """A settings change during a build starts a second build of the same
        file; neither may move the other's temp file away."""
        import threading
        spec = build.load_spec(SPEC)
        icons = build.render(westwood_td, westwood_td.open_source(westwood_td.find(str(self.data))),
                             spec, "gdi")
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "copy.mods.png"
            errors = []
            gate = threading.Barrier(4, timeout=60)

            def one():
                try:
                    gate.wait()
                    build.patch(SHIPPED, spec, icons, out)
                except Exception as e:  # noqa: BLE001 — collected and asserted below
                    errors.append(e)

            threads = [threading.Thread(target=one) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(60)
                self.assertFalse(t.is_alive(), "a patch thread did not finish in 60 s")
            self.assertEqual(errors, [])
            self.assertTrue(out.exists())
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["copy.mods.png"])


class BadRecipeTest(unittest.TestCase):

    def test_one_bad_recipe_costs_only_its_own_key(self):
        """A sprite this install lacks skips that icon and keeps the others."""
        with tempfile.TemporaryDirectory() as d:
            make_game_files(Path(d))
            source = westwood_td.open_source(westwood_td.find(d))
            spec = {"game_assets": {"reader": "westwood_td", "icons": {
                        "group2": {"unit": "nosuchunit"}, "group3": {"unit": "apc", "face": 999},
                        "group4": {"unit": "mtnk", "face": 28}}},
                    "bindings": [{"key": k, "icon": f"group{k}.png", "region": [48, 40]}
                                 for k in "234"]}
            with self.assertLogs("PolyHost", "WARNING") as logs:
                icons = build.render(westwood_td, source, spec, "gdi")
        self.assertEqual(set(icons), {"group4"})
        self.assertEqual(len(logs.output), 2)


class SpecTest(unittest.TestCase):
    """The C&C spec's game_assets block against its own bindings."""

    def test_every_recipe_replaces_a_bound_icon(self):
        spec = build.load_spec(SPEC)
        stems = {Path(b["icon"]).stem for b in build.bindings(spec)}
        for variant in ("gdi", "nod"):
            got = build.recipes(spec, variant)
            self.assertEqual(set(got) - stems, set(), f"{variant}: a recipe for no key")
            for stem, recipe in got.items():
                if "plus" in recipe:
                    self.assertIn(recipe["plus"], got, f"{stem} adds a plus to nothing")

    def test_the_mapping_entry_point_registers_the_template(self):
        import yaml
        with open(build.RES / "overlay-mapping.poly.yaml", encoding="utf-8") as f:
            mapping = yaml.safe_load(f)
        with mock.patch.dict(game_assets._specs, clear=True):
            game_assets.register_mapping(mapping)
            self.assertEqual(game_assets._specs.get(TEMPLATE), SPEC)
            self.assertTrue(all(p.exists() for p in game_assets._specs.values()))


class ReaderSettingsTest(unittest.TestCase):

    def test_reader_settings_extend_the_defaults(self):
        from polyhost.services.game_assets import readers
        from polyhost.settings import DEFAULT_SETTINGS
        for s in readers.all_settings():
            self.assertIn(s.key, DEFAULT_SETTINGS)
            self.assertEqual(DEFAULT_SETTINGS[s.key], s.default)
            self.assertIn(s.key, game_assets.SETTING_KEYS)
        for r in readers.READERS.values():
            keys = {s.key for s in r.settings}
            self.assertLessEqual({r.folder, r.variant} - {None}, keys)


class RequestTest(unittest.TestCase):
    """The on-demand registry: request(), override_for(), take_changed(), reset()."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name) / "td"
        cls.data.mkdir()
        make_game_files(cls.data)
        cls.cache = Path(cls.tmp.name) / "cache"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        for d in (game_assets._specs, game_assets._overrides, game_assets._started):
            p = mock.patch.dict(d, clear=True)
            p.start()
            self.addCleanup(p.stop)
        c = mock.patch.object(game_assets, "cache_dir", return_value=self.cache)
        c.start()
        self.addCleanup(c.stop)
        game_assets.take_changed()
        self.addCleanup(game_assets.take_changed)
        game_assets.register_mapping({"clientg": {"overlay": TEMPLATE,
                                                  "game_assets": "cnc_remastered/cnc_remastered.yaml"}})
        self.settings = {"game_assets_enabled": True, "game_cnc_data_dir": str(self.data),
                         "game_cnc_faction": "nod"}

    def _request(self, hint=None):
        t = game_assets.request(TEMPLATE, self.settings.get, hint)
        if t is not None:
            t.join(60)
            self.assertFalse(t.is_alive(), "the build did not finish in 60 s")
        return t

    def test_nothing_is_built_before_the_overlay_is_sent(self):
        self.assertIsNone(game_assets.override_for(TEMPLATE))
        self.assertFalse(game_assets.take_changed())

    def test_the_first_send_builds_once_and_asks_for_a_resend(self):
        self.assertIsNotNone(self._request())
        self.assertTrue(game_assets.override_for(TEMPLATE).endswith(".mods.png"))
        self.assertTrue(game_assets.take_changed(), "a new copy must ask for a re-send")
        self.assertFalse(game_assets.take_changed(), "the flag is taken once")
        self.assertIsNone(self._request(), "a built copy is not built again")

    def test_templates_without_an_entry_point_and_a_disabled_feature_build_nothing(self):
        self.assertFalse(game_assets.wants("vscode_template.mods.png", self.settings.get))
        self.assertIsNone(game_assets.request("vscode_template.mods.png", self.settings.get))
        self.assertTrue(game_assets.wants(TEMPLATE, self.settings.get))
        self.settings["game_assets_enabled"] = False
        self.assertFalse(game_assets.wants(TEMPLATE, self.settings.get))
        self.assertIsNone(game_assets.request(TEMPLATE, self.settings.get))

    def test_a_built_copy_is_not_wanted_again(self):
        self._request()
        self.assertFalse(game_assets.wants(TEMPLATE, self.settings.get))

    def test_the_hint_is_read_on_the_build_thread(self):
        seen = []
        self.settings["game_cnc_data_dir"] = ""
        with mock.patch.object(westwood_td, "install_candidates", return_value=[]):
            self._request(hint=lambda: seen.append(1) or None)
        self.assertEqual(seen, [1])
        self.assertIsNone(game_assets.override_for(TEMPLATE))

    def test_an_attempt_without_game_files_is_retried_with_the_next_hint(self):
        """A forwarded window brings no folder; the next local send does."""
        self.settings["game_cnc_data_dir"] = ""
        with tempfile.TemporaryDirectory() as d:
            inst = Path(d)
            td = inst / "Data" / "CNCDATA" / "TIBERIAN_DAWN"
            td.mkdir(parents=True)
            make_game_files(td)
            with mock.patch.object(westwood_td, "install_candidates", return_value=[]):
                self.assertIsNotNone(self._request(hint=None))
                self.assertIsNone(game_assets.override_for(TEMPLATE))
                self.assertIsNotNone(self._request(hint=inst), "a failed attempt must be retried")
            self.assertIsNotNone(game_assets.override_for(TEMPLATE))

    def test_a_switch_rebuilds_and_turning_it_off_drops_the_copy(self):
        self._request()
        nod = game_assets.override_for(TEMPLATE)
        game_assets.take_changed()
        self.settings["game_cnc_faction"] = "gdi"
        game_assets.reset(self.settings.get)
        self.assertTrue(game_assets.take_changed(), "a reset re-sends what is on the keyboard")
        self._request()
        self.assertNotEqual(game_assets.override_for(TEMPLATE), nod)
        self.assertTrue(game_assets.take_changed())
        self.settings["game_assets_enabled"] = False
        game_assets.reset(self.settings.get)
        self.assertIsNone(game_assets.override_for(TEMPLATE))
        self.assertTrue(game_assets.take_changed())

    def test_a_reset_before_any_game_overlay_resends_nothing(self):
        game_assets.reset(self.settings.get)
        self.assertFalse(game_assets.take_changed())

    def test_an_overridden_underlay_stays_an_underlay(self):
        """The send path dims an Underlay; the copy must keep that mark."""
        from polyhost.core.poly_core import get_overlay_path
        from polyhost.handler.common import Underlay
        game_assets._overrides[TEMPLATE] = "/cache/copy.png"
        plain = get_overlay_path(TEMPLATE)
        under = get_overlay_path(Underlay(TEMPLATE))
        self.assertEqual(plain, "/cache/copy.png")
        self.assertFalse(getattr(plain, "underlay", False))
        self.assertEqual(under, "/cache/copy.png")
        self.assertTrue(getattr(under, "underlay", False))


if __name__ == "__main__":
    unittest.main()
