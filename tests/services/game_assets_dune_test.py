"""The Dune II (westwood_d2) and Dune 2000 (westwood_d2k) readers and the
overlays drawn from them. Synthetic game files only."""
import os
import struct
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

import numpy as np

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode
from polyhost.services import game_assets
from polyhost.services.game_assets import build
from polyhost.services.game_assets.westwood_d2 import reader as d2
from polyhost.services.game_assets.westwood_d2.pak import Pak
from polyhost.services.game_assets.westwood_d2k import reader as d2k
from polyhost.services.game_assets.westwood_d2k.r16 import R16
from polyhost.services.game_assets.westwood_td import westwood
from tests.services.game_assets_test import blob_frame, write_d2

SOURCES = build.RES / "overlay_sources"
OVERLAYS = build.RES / "overlays"


def write_pak(files: dict) -> bytes:
    head_len = sum(4 + len(n) + 1 for n in files) + 4
    head, body, off = b"", b"", head_len
    for name, data in files.items():
        head += struct.pack("<I", off) + name.encode() + b"\0"
        body += data
        off += len(data)
    return head + struct.pack("<I", 0) + body


def make_dune_pak(folder: Path) -> None:
    """DUNE.PAK with every shape file the Dune II specs draw, in the 1.07 layout."""
    pal = bytes(min(63, i // 2) for i in range(256) for _ in range(3))
    files = {"IBM.PAL": pal,
             "UNITS.SHP": write_d2([blob_frame(16, 16, i, colour=60) for i in range(120)]),
             "UNITS1.SHP": write_d2([blob_frame(16, 16, i, colour=60) for i in range(90)]),
             "UNITS2.SHP": write_d2([blob_frame(16, 16, i, colour=60) for i in range(40)]),
             "MOUSE.SHP": write_d2([blob_frame(16, 16, i, colour=60) for i in range(7)])}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "DUNE.PAK").write_bytes(write_pak(files))


def r16_frame(w, h, seed, palette=None):
    px = blob_frame(h, w, seed, colour=60)
    typ = 1 if palette is not None else 2
    out = bytes([typ]) + struct.pack("<iiiiIi", w, h, 0, 0, 0, 1 if palette is not None else 0)
    out += bytes([8, h, w, 0]) + px.tobytes()
    if palette is not None:
        out += bytes(8) + palette
    return out + b"\0"


def make_d2k_files(folder: Path, frames=4400) -> None:
    pal16 = struct.pack("<256H", *[((i >> 3) << 10) | ((i >> 3) << 5) | (i >> 3) for i in range(256)])
    data = r16_frame(8, 8, 0, pal16) + b"".join(r16_frame(24, 20, k) for k in range(1, frames))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "DATA.R16").write_bytes(data)
    (folder / "PALETTE.BIN").write_bytes(bytes(768))


def cells(path, mod):
    conv = ImageConverter(DeviceSettings())
    if not conv.open(str(path)):
        raise AssertionError(f"cannot open {path}")
    return {kc: od.all_bytes for kc, od in (conv.extract_overlays(mod) or {}).items()}


class FormatTest(unittest.TestCase):

    def test_pak_entries_and_a_file_listed_twice(self):
        """C.SHP points at A.SHP's data, as a sound PAK of the game does: both
        end at the next larger offset, B.PAL's."""
        table = 3 * (4 + 6) + 4                 # three (offset, 5-letter name + NUL) entries + terminator
        a, b = table, table + 4
        data = (struct.pack("<I", a) + b"A.SHP\0" + struct.pack("<I", b) + b"B.PAL\0"
                + struct.pack("<I", a) + b"C.SHP\0" + struct.pack("<I", 0) + b"aaaa" + b"bb")
        p = Pak(data)
        self.assertEqual(p.get("a.shp"), b"aaaa")
        self.assertEqual(p.get("C.SHP"), b"aaaa")
        self.assertEqual(p.get("B.PAL"), b"bb")
        self.assertIsNone(p.get("missing"))

    def test_a_pak_offset_past_the_end_is_refused(self):
        with self.assertRaises(ValueError):
            Pak(struct.pack("<I", 9999) + b"A\0" + struct.pack("<I", 0))

    def test_shape_files_of_both_versions_decode(self):
        frames = [blob_frame(10, 12, i, colour=60) for i in range(3)]
        v107 = write_d2(frames)
        # 1.0: 2-byte offsets counted from the start of the file.
        n = len(frames)
        body = v107[2 + 4 * (n + 1):]
        offs = struct.unpack_from(f"<{n + 1}I", v107, 2)
        start = 2 + 2 * (n + 1)
        v10 = struct.pack("<H", n) + b"".join(struct.pack("<H", o - offs[0] + start) for o in offs) + body
        for data in (v107, v10):
            got = westwood.shp_d2_frames(data)
            self.assertEqual(len(got), n)
            self.assertTrue((got[1] == frames[1]).all())
        self.assertTrue(d2.is_v1_0(v10))
        self.assertFalse(d2.is_v1_0(v107))

    def test_r16_frames_and_their_palette(self):
        with tempfile.TemporaryDirectory() as d:
            make_d2k_files(Path(d), frames=5)
            r = R16(Path(d, "DATA.R16").read_bytes(), Path(d, "PALETTE.BIN").read_bytes())
        self.assertEqual(len(r), 5)
        rgb, cover = r.frame(3)
        self.assertEqual(rgb.shape, (20, 24, 3))
        self.assertTrue(cover.any())
        with self.assertRaises(IndexError):
            r.frame(5)

    def test_a_damaged_r16_is_refused(self):
        bad = bytes([1]) + struct.pack("<iiiiIi", 5000, 5000, 0, 0, 0, 0) + bytes([8, 0, 0, 0])
        with self.assertRaises(ValueError):
            R16(bad)


class FindTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        for p in (mock.patch.object(Path, "home", return_value=self.home),
                  mock.patch.dict(os.environ, {"APPDATA": "", "XDG_CONFIG_HOME": ""}),
                  mock.patch.object(d2, "data_dirs", wraps=d2.data_dirs)):
            p.start()
            self.addCleanup(p.stop)

    def test_dune_legacy_data_folder_and_the_game_folder(self):
        self.assertIsNone(d2.find(""))
        legacy = self.home / ".config" / "DuneLegacy" / "data"
        make_dune_pak(legacy)
        self.assertEqual(d2.find("")["dune.pak"].parent, legacy)
        game = self.home / "OpenDUNE"
        make_dune_pak(game / "data")
        self.assertEqual(d2.find("", hint=game)["dune.pak"].parent, game / "data")

    def test_dune_2000_in_the_openra_content_folder(self):
        self.assertIsNone(d2k.find(""))
        v3 = self.home / ".config" / "openra" / "Content" / "d2k" / "v3"
        make_d2k_files(v3, frames=3)
        self.assertEqual(d2k.find("")["sprites"].name, "DATA.R16")


class BuildTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.d2, cls.d2k, cls.cache = root / "d2", root / "d2k", root / "cache"
        make_dune_pak(cls.d2)
        make_d2k_files(cls.d2k)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _check(self, spec_path, templates, settings):
        spec = build.load_spec(spec_path)
        stems = set(spec["game_assets"]["icons"])
        want = {}
        for b in build.bindings(spec):
            if Path(b["icon"]).stem in stems:
                want.setdefault(build.modifier(b.get("mods")), set()).add(KeyCode[f"KC_{str(b['key']).upper()}"].value)
        for template in templates:
            out = build.build(template, spec_path, settings.get, self.cache)
            self.assertIsNotNone(out, template)
            for mod, keys in want.items():
                if (mod.name in ("CTRL_SHIFT", "CTRL_ALT", "ALT_SHIFT")) != (".combo." in template):
                    continue
                shipped, patched = cells(OVERLAYS / template, mod), cells(out, mod)
                for kc in set(shipped) | set(patched):
                    self.assertEqual(shipped.get(kc) != patched.get(kc), kc in keys,
                                     f"{template} {mod.name} 0x{kc:02x}")

    def test_dune_legacy_and_the_original_for_each_house(self):
        for house in ("atreides", "harkonnen", "ordos"):
            with self.subTest(house):
                s = {"game_dune2_data_dir": str(self.d2), "game_dune2_house": house}
                self._check(SOURCES / "dune2" / "dune_legacy.yaml", ["dune_legacy_template.mods.png"], s)
                self._check(SOURCES / "dune2" / "dune2.yaml", ["dune2_template.mods.png"], s)

    def test_openra_dune_2000_for_each_house(self):
        for house in ("atreides", "harkonnen", "ordos"):
            with self.subTest(house):
                self._check(SOURCES / "openra" / "openra_d2k.yaml",
                            ["openra_d2k_template.mods.png", "openra_d2k_template.combo.mods.png"],
                            {"game_d2k_data_dir": str(self.d2k), "game_d2k_house": house})

    def test_dune_ii_1_0_files_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            make_dune_pak(Path(d))
            data = Path(d, "DUNE.PAK").read_bytes()
            p = Pak(data)
            units = p.get("units.shp")
            n, = struct.unpack_from("<H", units, 0)
            offs = struct.unpack_from(f"<{n + 1}I", units, 2)
            start = 2 + 2 * (n + 1)
            v10 = struct.pack("<H", n) + b"".join(struct.pack("<H", o - offs[0] + start) for o in offs) + units[2 + 4 * (n + 1):]
            Path(d, "DUNE.PAK").write_bytes(write_pak({"IBM.PAL": p.get("ibm.pal"), "UNITS.SHP": v10}))
            with self.assertRaises(ValueError):
                d2.open_source(d2.find(d))


class MappingTest(unittest.TestCase):

    def test_every_dune_overlay_is_registered_with_its_spec(self):
        import yaml
        with open(build.RES / "overlay-mapping.poly.yaml", encoding="utf-8") as f:
            mapping = yaml.safe_load(f)
        with mock.patch.dict(game_assets._specs, clear=True):
            game_assets.register_mapping(mapping)
            for template, spec in (("dune_legacy_template.mods.png", "dune2/dune_legacy.yaml"),
                                   ("dune2_template.mods.png", "dune2/dune2.yaml"),
                                   ("openra_d2k_template.mods.png", "openra/openra_d2k.yaml"),
                                   ("openra_d2k_template.combo.mods.png", "openra/openra_d2k.yaml")):
                self.assertEqual(game_assets._specs.get(template), SOURCES / spec, template)

    def test_every_recipe_replaces_a_bound_icon(self):
        for spec_path, houses in ((SOURCES / "dune2" / "dune_legacy.yaml", ("atreides", "harkonnen", "ordos")),
                                  (SOURCES / "dune2" / "dune2.yaml", ("atreides",)),
                                  (SOURCES / "openra" / "openra_d2k.yaml", ("atreides", "harkonnen", "ordos"))):
            spec = build.load_spec(spec_path)
            stems = {Path(b["icon"]).stem for b in build.bindings(spec)}
            for house in houses:
                got = build.recipes(spec, house)
                self.assertEqual(set(got) - stems, set(), f"{spec_path.name} {house}")


if __name__ == "__main__":
    unittest.main()
