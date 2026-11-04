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


def make_icn(tiles, palettes, tile_pal):
    """An ICON.ICN: 0x18 header bytes, SSET (8 more header bytes, then the 4-bit
    tiles), RPAL (16 colours per palette), RTBL (a palette per tile)."""
    sset = b"".join(bytes((t[y, x] << 4) | t[y, x + 1] for y in range(16) for x in range(0, 16, 2)) for t in tiles)
    out = bytes(0x18) + b"SSET" + struct.pack(">I", len(sset) + 8) + bytes(8) + sset
    rpal = b"".join(bytes(p) for p in palettes)
    out += b"RPAL" + struct.pack(">I", len(rpal)) + rpal
    return out + b"RTBL" + struct.pack(">I", len(tile_pal)) + bytes(tile_pal)


def make_map(groups):
    """An ICON.MAP: a table of word offsets to each group's tile numbers."""
    head = len(groups)
    words, body = [], []
    for g in groups:
        words.append(head + len(body))
        body += g
    return struct.pack(f"<{len(words) + len(body)}H", *words, *body)


def make_font(glyphs, height):
    """A Dune II .FNT with `glyphs` {code: 2-D array of 0..3}, laid out as
    OpenDUNE's Font_LoadFile reads it."""
    count = max(glyphs) + 1
    start, data_start = 14, 20
    width_list = data_start + 2 * count
    line_list = width_list + count + 2
    data = bytearray()
    data_off = line_list + 2 * count
    offs, lines = [], []
    for i in range(count):
        g = glyphs.get(i)
        if g is None:
            offs.append(0)
            lines.append((0, 0))
            continue
        offs.append(data_off + len(data))
        lines.append((0, g.shape[0]))
        for row in g:
            packed = [row[x] | ((row[x + 1] if x + 1 < len(row) else 0) << 4) for x in range(0, len(row), 2)]
            data += bytes(packed)
    widths = [glyphs[i].shape[1] if i in glyphs else 0 for i in range(count)]
    head = bytearray(data_off)
    head[2:4] = b"\x00\x05"
    struct.pack_into("<5H", head, 4, start, data_start, width_list, width_list + count, line_list)
    head[start + 4], head[start + 5] = height, max(widths)
    struct.pack_into(f"<{count}H", head, data_start, *offs)
    head[width_list:width_list + count] = bytes(widths)
    for i, (u, n) in enumerate(lines):
        head[line_list + 2 * i], head[line_list + 2 * i + 1] = u, n
    return bytes(head) + bytes(data)


def portrait_frame(seed, background=100):
    """A 32x24 build portrait: a 1 px frame (colour 15), a flat background
    and a unit in the middle."""
    f = np.full((24, 32), background, np.uint8)
    f[0], f[-1], f[:, 0], f[:, -1] = 15, 15, 15, 15
    unit = blob_frame(14, 20, seed, colour=60)
    f[5:19, 6:26] = np.where(unit != 0, unit, f[5:19, 6:26])
    return f


def to_v1_0(shp: bytes) -> bytes:
    """A 1.07 shape file rewritten as 1.0 writes it: 2-byte offsets counted
    from the start of the file."""
    n, = struct.unpack_from("<H", shp, 0)
    offs = struct.unpack_from(f"<{n + 1}I", shp, 2)
    start = 2 + 2 * (n + 1)
    return struct.pack("<H", n) + b"".join(struct.pack("<H", o - offs[0] + start) for o in offs) + shp[2 + 4 * (n + 1):]


def map_and_fonts() -> dict:
    """ICON.ICN / ICON.MAP with 27 groups of 64 tiles each (a building is a run
    of a group's tiles) and the two fonts, with a glyph for every printable
    ASCII character."""
    rng = np.random.default_rng(7)
    tiles = [rng.integers(0, 16, (16, 16)) for _ in range(130)]
    groups = [[(g * 5 + i) % 130 for i in range(64)] for g in range(27)]
    glyphs = {c: np.array([[3, 3, 3, 0], [3, 1, 2, 0], [3, 1 if c % 2 else 2, 2, 0], [0, 0, 0, 0]], np.uint8)
              for c in range(32, 127)}
    return {"ICON.ICN": make_icn(tiles, [list(range(40, 56))], [0] * 130), "ICON.MAP": make_map(groups),
            "NEW8P.FNT": make_font(glyphs, 4), "NEW6P.FNT": make_font(glyphs, 4)}


def make_dune_pak(folder: Path, v1_0=False) -> None:
    """DUNE.PAK with every shape file the Dune II specs draw, in the 1.07 layout
    or, with `v1_0`, in the 1.0 one."""
    pal = bytes(min(63, i // 2) for i in range(256) for _ in range(3))
    files = {"IBM.PAL": pal,
             # 1.0's 2-byte offsets address 64 KB: a colour-0 background keeps
             # the zero-run encoded file below that.
             "SHAPES.SHP": write_d2([portrait_frame(i, 0 if v1_0 else 100) for i in range(103)]),
             "UNITS.SHP": write_d2([blob_frame(16, 16, i, colour=60) for i in range(120)]),
             "UNITS1.SHP": write_d2([blob_frame(16, 16, i, colour=60) for i in range(90)]),
             "UNITS2.SHP": write_d2([blob_frame(16, 16, i, colour=60) for i in range(40)]),
             "MOUSE.SHP": write_d2([blob_frame(16, 16, i, colour=60) for i in range(7)]),
             **map_and_fonts()}
    if v1_0:
        files = {n: to_v1_0(d) if n.endswith(".SHP") else d for n, d in files.items()}
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
        for data in (v107, to_v1_0(v107)):
            got = westwood.shp_d2_frames(data)
            self.assertEqual(len(got), len(frames))
            self.assertTrue((got[1] == frames[1]).all())

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

    def test_dune_ii_1_0_files_are_read(self):
        """The 1.0 demo has the same pictures at the same frame numbers as
        1.07; only the offset table differs."""
        with tempfile.TemporaryDirectory() as d:
            make_dune_pak(Path(d), v1_0=True)
            self._check(SOURCES / "dune2" / "dune2.yaml", ["dune2_template.mods.png"],
                        {"game_dune2_data_dir": d, "game_dune2_house": "atreides"})

    PORTRAIT = {"src": "shp:shapes.shp:78", "engine": "dither", "cut": True, "frame": 1, "mode": "levels",
                "lo": 5, "hi": 95, "gamma": 1, "curve": 0.3, "sharpen": 1, "floor": 0.15, "outline": True}

    def test_a_picture_recipe_cuts_the_frame_and_background(self):
        sp = d2.open_source(d2.find(str(self.d2)))
        m = d2.draw(sp, self.PORTRAIT, (48, 40))
        self.assertEqual(m.shape, (40, 48))
        self.assertTrue(m.any())
        # The unit is 20 of the 30 inner columns and 14 of the 22 rows: the
        # flat background around it is not drawn.
        self.assertFalse(m[0].all() or m[:, -1].all())
        self.assertLess(m.mean(), 0.6)
        whole = d2.draw(sp, dict(self.PORTRAIT, cut=False, outline=False, frame=0), (48, 40))
        self.assertGreater(whole.mean(), m.mean())

    def test_word_map_tile_and_cursor_recipes(self):
        sp = d2.open_source(d2.find(str(self.d2)))
        w = d2.draw(sp, {"word": "Ab", "font": "new8p.fnt", "body": True, "valign": "bottom"}, (72, 40))
        self.assertEqual(w.shape, (40, 72))
        ys, xs = np.nonzero(w)
        self.assertEqual((ys.max(), xs.max()), (38, 71))       # bottom right, 1 px above the edge
        tile = d2.draw(sp, {"src": "icn:22:12:3x2", "engine": "dither", "cut": False, "frame": 0, "mode": "fs",
                            "lo": 5, "hi": 95, "gamma": 1, "curve": 0, "floor": 0.15}, (48, 40))
        self.assertEqual(tile.shape, (40, 48))
        self.assertTrue(tile.any())
        cur = d2.draw(sp, {"src": "shp:mouse.shp:2", "engine": "pixel", "lit": "nonzero", "scale": 0}, (40, 40))
        self.assertEqual(int(cur.sum()) % 4, 0)                 # a 16 px cursor at 2x: whole 2x2 blocks
        for bad in ({"portrait": 78}, {"src": "png:foo"}, dict(self.PORTRAIT, mode="halftone")):
            with self.subTest(bad), self.assertRaises((ValueError, KeyError)):
                d2.draw(sp, bad, (48, 40))

    def test_a_recipe_region_keeps_the_margin_it_names(self):
        """Group 3's recipe is 47 px wide with the binding's 5 px margin: the
        picture's right edge is 5 px from the cell's."""
        s = {"game_dune2_data_dir": str(self.d2), "game_dune2_house": "atreides"}
        out = build.build("dune_legacy_template.mods.png", SOURCES / "dune2" / "dune_legacy.yaml", s.get, self.cache)
        from PIL import Image

        from polyhost.res.overlay_layout import CH, PRIMARY_CH, SLOT_H, SLOT_W, cell_for
        r, c = cell_for(KeyCode.KC_3)
        arr = np.array(Image.open(out).convert("RGBA"))
        cell = arr[r * SLOT_H:(r + 1) * SLOT_H, c * SLOT_W:(c + 1) * SLOT_W, CH[PRIMARY_CH[build.modifier([])]]] > 127
        cols = np.nonzero(cell.any(axis=0))[0]
        self.assertTrue(cols.size)
        self.assertEqual(cols.max(), SLOT_W - 5 - 1)
        self.assertGreaterEqual(cols.min(), SLOT_W - 5 - 47)


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
