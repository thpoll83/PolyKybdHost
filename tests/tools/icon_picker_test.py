"""`gen_icon_picker`: the Dune II map-tile and font decoders, the candidate
presets, and the shipped picker specs against the overlays they name.

Synthetic game files only. The page itself (icon_picker_template.html) is
checked by hand in a browser, as ICON_PICKER.md describes.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml

HOST = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HOST / "tools"))
sys.path.insert(0, str(HOST / "scripts"))

import apply_icon_picks as apply  # noqa: E402
import gen_icon_picker as gen  # noqa: E402
import icon_picker_sources as src  # noqa: E402
from polyhost.services.game_assets.westwood_d2 import formats as fmt  # noqa: E402
from generate_app_overlays import resolve_key  # noqa: E402
from polyhost.services.game_assets import build  # noqa: E402
from tests.services.game_assets_dune_test import make_font, make_icn, make_map  # noqa: E402

SOURCES = build.RES / "overlay_sources"


class DecoderTest(unittest.TestCase):

    def test_icn_tiles_use_their_own_palette_and_the_map_groups_them(self):
        rng = np.random.default_rng(1)
        tiles = [rng.integers(0, 16, (16, 16)) for _ in range(3)]
        pals = [list(range(100, 116)), list(range(200, 216))]
        got, groups = fmt.icn_tiles(make_icn(tiles, pals, [0, 1, 0]), make_map([[2], [0, 1, 2]]))
        self.assertEqual(len(got), 3)
        self.assertTrue((got[1] == np.array(pals[1])[tiles[1]]).all())
        self.assertTrue((got[2] == np.array(pals[0])[tiles[2]]).all())
        self.assertEqual(groups, [[2], [0, 1, 2]])

    def test_a_file_without_the_sset_section_is_refused(self):
        with self.assertRaises(ValueError):
            fmt.icn_tiles(bytes(64), make_map([[0]]))

    def test_font_glyph_values_and_odd_widths(self):
        a = np.array([[3, 1, 2], [0, 1, 0]], np.uint8)          # odd width: the last nibble pads
        h, chars = fmt.font_glyphs(make_font({65: a}, 2))
        self.assertEqual(h, 2)
        self.assertTrue((chars[65] == a).all())
        self.assertEqual(chars[64].shape, (2, 0))                # a code with no glyph is empty
        with self.assertRaises(ValueError):
            fmt.font_glyphs(bytes(16))


class SpecTest(unittest.TestCase):

    def test_presets_and_overrides(self):
        presets = {"portrait": {"engine": "dither", "lo": 5}, "word": {"font": "8p", "scale": 1}}
        c = gen.candidate({"label": "x", "src": "shp:shapes.shp:1", "preset": "portrait", "lo": 15}, presets)
        self.assertEqual(c, {"label": "x", "kind": "pic", "src": "shp:shapes.shp:1", "preset": "portrait",
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


WORD = {"pick": "word", "src": None, "params": {"font": "8p", "body": True, "shade": False, "outline": False,
                                                "scale": 1, "valign": "bottom", "gap": 1, "text": "Go"}}
PIC = {"pick": "portrait 1: x", "src": "shp:shapes.shp:1",
       "params": {"engine": "dither", "cut": True, "frame": 1, "mode": "levels", "lo": 5, "hi": 95, "gamma": 1,
                  "curve": 0.3, "sharpen": 1, "floor": 0.15, "outline": True, "mirror": False, "rw": 47}}


def raster_pick(gamma=1.0, rh=21):
    return {"pick": "shipped icon, re-rasterized (fa:pause)", "src": "fa:pause",
            "params": {"relief": True, "depth": 0.08, "azimuth": 225, "elevation": 42, "ambient": 0.35,
                       "falloff": 0.45, "grain": 1, "seed": 1, "flat": 0.6, "mode": "fs", "lo": 3, "hi": 97,
                       "gamma": gamma, "curve": 0, "sharpen": 0, "floor": 0.15, "outline": True,
                       "mirror": False, "valign": "bottom", "rh": rh}}


class ApplyTest(unittest.TestCase):
    """apply_icon_picks.py on two small overlays that share an icon file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        (self.d / "a.yaml").write_text(
            "bindings:\n"
            "  - { key: A, icon: x.png, label: \"Attack\" }\n"
            "  - { key: B, icon: y.png, label: \"Build\" }\n"
            "  - { key: \"1\", icon: g.png, label: \"Group 1\", region: [48, 40], margin: 5 }\n"
            "\n# game art\ngame_assets:\n  reader: westwood_d2\n  icons:\n    g: {plus: x}\n", encoding="utf-8")
        (self.d / "b.yaml").write_text("bindings:\n  - { key: A, icon: x.png, label: \"Attack\" }\n",
                                       encoding="utf-8")
        keys_a = [{"key": "A", "label": "Attack", "candidates": [{"word": "Go"}]},
                  {"key": "B", "label": "Build", "candidates": [{"word": "Go"}]},
                  {"key": "1", "label": "Group 1", "candidates": [{"word": "Go"}]}]
        (self.d / "picker.yaml").write_text(yaml.safe_dump({
            "reader": "westwood_d2", "fonts": {"8p": "new8p.fnt"},
            "overlays": [{"id": "a", "spec": "a.yaml", "template": "a.png", "keys": keys_a},
                         {"id": "b", "spec": "b.yaml", "template": "b.png",
                          "keys": [{"key": "A", "label": "Attack", "candidates": [{"word": "Go"}]}]}]}),
            encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_picks(self, picks):
        (self.d / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            apply.main([str(self.d / "picker.yaml"), str(self.d / "picks.json")])

    def icons(self, name="a.yaml"):
        return build.load_spec(self.d / name)["game_assets"]["icons"]

    def raster(self):
        return yaml.safe_load((self.d / "rasterize.yaml").read_text(encoding="utf-8")) or {}

    def test_recipes_regions_and_a_re_rasterized_icon(self):
        self.run_picks({"a": {"A": WORD, "1": PIC, "B": raster_pick()}})
        icons = self.icons()
        self.assertEqual(icons["x"]["word"], "Go")
        self.assertEqual((icons["x"]["region"], icons["x"]["margin"], icons["x"]["font"]), ([72, 40], 0, "new8p.fnt"))
        self.assertEqual((icons["g"]["src"], icons["g"]["region"], icons["g"]["margin"]),
                         ("shp:shapes.shp:1", [47, 40], 5))           # the binding's margin is kept
        self.assertNotIn("y", icons)
        self.assertEqual(self.raster()["y"]["region"], [40, 21])
        line = [ln for ln in (self.d / "a.yaml").read_text(encoding="utf-8").splitlines() if "y.png" in ln][0]
        self.assertEqual(line, '  - { key: B, icon: y.png, label: "Build", region: [40, 21] }')
        self.assertIn("# game art", (self.d / "a.yaml").read_text(encoding="utf-8"))

    def test_two_keys_on_one_icon_must_agree(self):
        (self.d / "a.yaml").write_text((self.d / "a.yaml").read_text(encoding="utf-8").replace("y.png", "x.png"),
                                       encoding="utf-8")
        before = (self.d / "a.yaml").read_text(encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.run_picks({"a": {"A": WORD, "B": dict(WORD, params=dict(WORD["params"], text="Stop"))}})
        self.assertEqual((self.d / "a.yaml").read_text(encoding="utf-8"), before)

    def test_two_overlays_re_rasterizing_one_icon_must_agree(self):
        before = (self.d / "a.yaml").read_text(encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.run_picks({"a": {"A": raster_pick(1.0)}, "b": {"A": raster_pick(1.5)}})
        self.assertEqual((self.d / "a.yaml").read_text(encoding="utf-8"), before)
        self.assertFalse((self.d / "rasterize.yaml").exists())
        self.run_picks({"a": {"A": raster_pick(1.0)}, "b": {"A": raster_pick(1.0)}})
        self.assertIn("x", self.raster())

    def test_a_re_rasterized_icon_resizes_every_overlay_that_draws_it(self):
        """x.png is drawn by a and b; picked on a, b's binding gets the region too."""
        self.run_picks({"a": {"A": raster_pick(rh=24)}})
        for name in ("a.yaml", "b.yaml"):
            with self.subTest(name):
                line = [ln for ln in (self.d / name).read_text(encoding="utf-8").splitlines() if "x.png" in ln][0]
                self.assertIn("region: [40, 24]", line)

    def test_an_icon_another_overlay_draws_keeps_its_re_rasterized_file(self):
        self.run_picks({"a": {"A": raster_pick()}})
        self.run_picks({"a": {"A": WORD}})                   # b still draws x.png
        self.assertIn("x", self.raster())
        self.assertEqual(self.icons()["x"]["word"], "Go")

    def test_the_last_re_rasterized_icon_removed_empties_the_file(self):
        self.run_picks({"a": {"B": raster_pick()}})
        self.assertIn("y", self.raster())
        self.run_picks({"a": {"B": {"pick": "shipped"}}})
        self.assertEqual(self.raster(), {})


if __name__ == "__main__":
    unittest.main()
