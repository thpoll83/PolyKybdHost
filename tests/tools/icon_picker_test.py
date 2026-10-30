"""`gen_icon_picker`: the Dune II map-tile and font decoders, the candidate
presets, and the shipped picker specs against the overlays they name.

Synthetic game files only. The page itself (icon_picker_template.html) is
checked by hand in a browser, as ICON_PICKER.md describes.
"""
import os
import struct
import sys
import unittest
from pathlib import Path

import numpy as np
import yaml

HOST = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HOST / "tools"))
sys.path.insert(0, str(HOST / "scripts"))

import gen_icon_picker as gen  # noqa: E402
import icon_picker_sources as src  # noqa: E402
from generate_app_overlays import resolve_key  # noqa: E402
from polyhost.services.game_assets import build  # noqa: E402

SOURCES = build.RES / "overlay_sources"


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


class DecoderTest(unittest.TestCase):

    def test_icn_tiles_use_their_own_palette_and_the_map_groups_them(self):
        rng = np.random.default_rng(1)
        tiles = [rng.integers(0, 16, (16, 16)) for _ in range(3)]
        pals = [list(range(100, 116)), list(range(200, 216))]
        got, groups = src.icn_tiles(make_icn(tiles, pals, [0, 1, 0]), make_map([[2], [0, 1, 2]]))
        self.assertEqual(len(got), 3)
        self.assertTrue((got[1] == np.array(pals[1])[tiles[1]]).all())
        self.assertTrue((got[2] == np.array(pals[0])[tiles[2]]).all())
        self.assertEqual(groups, [[2], [0, 1, 2]])

    def test_a_file_without_the_sset_section_is_refused(self):
        with self.assertRaises(ValueError):
            src.icn_tiles(bytes(64), make_map([[0]]))

    def test_font_glyph_values_and_odd_widths(self):
        a = np.array([[3, 1, 2], [0, 1, 0]], np.uint8)          # odd width: the last nibble pads
        h, chars = src.font_glyphs(make_font({65: a}, 2))
        self.assertEqual(h, 2)
        self.assertTrue((chars[65] == a).all())
        self.assertEqual(chars[64].shape, (2, 0))                # a code with no glyph is empty
        with self.assertRaises(ValueError):
            src.font_glyphs(bytes(16))


class SpecTest(unittest.TestCase):

    def test_presets_and_overrides(self):
        presets = {"portrait": {"engine": "dither", "lo": 5}, "word": {"font": "8p", "scale": 1}}
        c = gen.candidate({"label": "x", "src": "shp:shapes.shp:1", "preset": "portrait", "lo": 15}, presets)
        self.assertEqual(c, {"label": "x", "kind": "pic", "src": "shp:shapes.shp:1",
                             "params": {"engine": "dither", "lo": 15}})
        w = gen.candidate({"word": "Stop", "scale": 2}, presets)
        self.assertEqual(w["kind"], "word")
        self.assertEqual(w["params"], {"font": "8p", "scale": 2, "text": "Stop"})

    def test_every_picker_key_is_bound_by_its_overlay(self):
        specs = sorted(SOURCES.glob("*/picker.yaml"))
        self.assertTrue(specs)
        for path in specs:
            spec = yaml.safe_load(path.read_text(encoding="utf-8"))
            sources = src.SOURCES[spec["reader"]]
            for ov in spec["overlays"]:
                binds = {(str(b["key"]).upper(), tuple(m.upper() for m in b.get("mods") or []))
                         for b in build.bindings(build.load_spec(path.parent / ov["spec"]))}
                self.assertTrue((build.RES / "overlays" / ov["template"]).exists(), ov["template"])
                for k in ov["keys"]:
                    key = (str(k["key"]).upper(), tuple(m.upper() for m in k.get("mods") or []))
                    self.assertIn(key, binds, f"{path.parent.name}/{ov['id']} {key}")
                    resolve_key(key[0])
                    for c in k["candidates"]:
                        if "word" in c:
                            continue
                        self.assertIn(c.get("preset"), spec["presets"], f"{ov['id']} {key} {c['label']}")
                        kind = c["src"].split(":")[0]
                        self.assertIn(kind, ("shp", "sprite", "icn", "icnset", "icntile"), c["src"])
            self.assertTrue(sources)
            if spec.get("vector_sources"):
                self.assertIn("vector", spec["presets"], path)

    def test_a_shipped_icon_is_traced_to_its_svg_through_the_borrowed_sets(self):
        """Dune II's own icon, one it borrows from OpenRA, one OpenRA borrows from
        C&C Remastered, and a rendered unit that has no SVG."""
        spec = yaml.safe_load((SOURCES / "dune2" / "picker.yaml").read_text(encoding="utf-8"))
        mods = spec["vector_sources"]
        self.assertEqual(gen.vector_spec("move", mods), "fa:location-arrow")
        self.assertEqual(gen.vector_spec("attackmove", mods), "gi:lorc/crossed-swords")
        self.assertEqual(gen.vector_spec("stop", mods), "fa:hand")
        self.assertIsNone(gen.vector_spec("group1", mods))


if __name__ == "__main__":
    unittest.main()
