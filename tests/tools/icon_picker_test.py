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
            self.assertIn(spec["reader"], src.SOURCES, path)
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
                        self.assertIn(kind, sources.KINDS, c["src"])
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


class WarzoneSourceTest(unittest.TestCase):
    """The Warzone 2100 source reads interface images from a data/base folder or
    from base.wz, and marks their transparent pixels as the page's background."""

    @staticmethod
    def _png(path: Path) -> bytes:
        from PIL import Image
        a = np.zeros((4, 6, 4), np.uint8)
        a[1:3, 1:5] = (200, 40, 40, 255)          # an opaque red block, the rest transparent
        Image.fromarray(a, "RGBA").save(path)
        return path.read_bytes()

    def test_a_data_folder_and_base_wz_give_the_same_picture(self):
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "data" / "base" / "images" / "intfac"
            d.mkdir(parents=True)
            data = self._png(d / "image_x.png")
            with zipfile.ZipFile(Path(tmp) / "base.wz", "w") as z:
                z.writestr("images/intfac/image_x.png", data)
            pics = []
            for root in (Path(tmp), Path(tmp) / "base.wz"):
                files = src.Warzone2100.find(str(root))
                self.assertIsNotNone(files, root)
                s = src.Warzone2100(dict(files, palette_from=["image_x"]))
                self.assertEqual(s.palette.shape, (256, 3))
                pics.append(s.picture("intfac:image_x"))
            np.testing.assert_array_equal(pics[0], pics[1])
            idx = pics[0]
            self.assertTrue((idx[0] == src.Warzone2100.BG).all())    # transparent row
            self.assertNotEqual(idx[1, 1], src.Warzone2100.BG)       # opaque pixel
            self.assertNotIn(int(idx[1, 1]), (src.Warzone2100.BG, 254))
            self.assertEqual(tuple(int(v) for v in s.palette[idx[1, 1]]), (200, 40, 40))   # the block's own colour

    def test_no_game_files_and_an_unknown_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(src.Warzone2100.find(tmp))
            d = Path(tmp) / "images" / "intfac"
            d.mkdir(parents=True)
            self._png(d / "image_x.png")
            s = src.Warzone2100(src.Warzone2100.find(tmp))
            with self.assertRaises(ValueError):
                s.picture("shp:x:1")


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

    def test_keys_after_the_game_assets_block_are_kept(self):
        with (self.d / "a.yaml").open("a", encoding="utf-8") as f:
            f.write("# after the block\nlater_key: 7\n")
        self.run_picks({"a": {"A": WORD}})
        text = (self.d / "a.yaml").read_text(encoding="utf-8")
        self.assertEqual(build.load_spec(self.d / "a.yaml")["later_key"], 7)
        self.assertIn("# after the block\nlater_key: 7\n", text)
        self.assertEqual(self.icons()["x"]["word"], "Go")
        self.assertEqual(text.count("game_assets:"), 1)
        self.run_picks({"a": {"A": WORD}})                           # a second write changes nothing
        self.assertEqual((self.d / "a.yaml").read_text(encoding="utf-8"), text)

    def test_a_block_on_the_first_line_is_replaced(self):
        text = (self.d / "b.yaml").read_text(encoding="utf-8")
        (self.d / "b.yaml").write_text("game_assets:\n  reader: westwood_d2\n  icons:\n    x: {plus: y}\n" + text,
                                       encoding="utf-8")
        self.run_picks({"b": {"A": {"pick": "shipped"}}})
        new = (self.d / "b.yaml").read_text(encoding="utf-8")
        self.assertEqual(new.count("game_assets:"), 1)
        self.assertTrue(new.startswith("game_assets:\n"))
        self.assertEqual(build.load_spec(self.d / "b.yaml")["game_assets"]["icons"], None)
        self.assertEqual(len(build.load_spec(self.d / "b.yaml")["bindings"]), 1)

    def test_a_shipped_variant_drops_an_earlier_redraw(self):
        self.use_variants()
        self.run_picks({"a": {"1 (Atreides)": raster_pick()}})
        self.assertIn("g", self.raster())
        self.run_picks({"a": {"1 (Atreides)": {"pick": "shipped"}}})
        self.assertNotIn("g", self.raster())

    def test_an_overlay_without_picks_or_a_block_is_left_alone(self):
        before = (self.d / "b.yaml").read_text(encoding="utf-8")
        self.run_picks({"a": {"B": WORD}})
        self.assertEqual((self.d / "b.yaml").read_text(encoding="utf-8"), before)

    def test_shipped_on_one_overlay_and_redrawn_on_another_must_agree(self):
        with self.assertRaises(SystemExit):
            self.run_picks({"a": {"A": raster_pick()}, "b": {"A": {"pick": "shipped"}}})
        self.assertFalse((self.d / "rasterize.yaml").exists())       # nothing written

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

    def use_variants(self):
        """Key 1 of overlay a as two variants, each with its own recipe for g."""
        spec = yaml.safe_load((self.d / "picker.yaml").read_text(encoding="utf-8"))
        spec["overlays"][0]["keys"][2:] = [
            {"key": "1", "variant": v, "label": f"Group 1 ({v.title()})", "candidates": [{"word": "Go"}]}
            for v in ("atreides", "harkonnen")]
        (self.d / "picker.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
        text = (self.d / "a.yaml").read_text(encoding="utf-8")
        (self.d / "a.yaml").write_text(text.replace("g: {plus: x}", "g:\n      atreides: {plus: x}\n"
                                                                    "      harkonnen: {plus: y}"), encoding="utf-8")

    def test_a_re_rasterized_variant_keeps_the_other_variants_recipes(self):
        self.use_variants()
        self.run_picks({"a": {"1 (Atreides)": raster_pick()}})
        self.assertEqual(self.icons()["g"], {"harkonnen": {"plus": "y"}})
        self.assertIn("g", self.raster())

    def test_two_variants_re_rasterizing_one_icon_must_agree(self):
        self.use_variants()
        before = (self.d / "a.yaml").read_text(encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.run_picks({"a": {"1 (Atreides)": raster_pick(1.0), "1 (Harkonnen)": raster_pick(1.5)}})
        self.assertEqual((self.d / "a.yaml").read_text(encoding="utf-8"), before)

    def test_a_shipped_variant_and_a_redrawn_variant_must_agree(self):
        """Both variants draw g.png: one keeping it shipped while the other redraws it
        would show the redrawn file on the shipped one."""
        self.use_variants()
        with self.assertRaises(SystemExit):
            self.run_picks({"a": {"1 (Atreides)": raster_pick(), "1 (Harkonnen)": {"pick": "shipped"}}})
        self.assertFalse((self.d / "rasterize.yaml").exists())

    def test_a_word_in_a_font_the_spec_does_not_list_is_refused(self):
        with self.assertRaises(SystemExit) as e:
            self.run_picks({"a": {"A": dict(WORD, params=dict(WORD["params"], font="12p"))}})
        self.assertIn("'12p'", str(e.exception))

    def test_the_last_re_rasterized_icon_removed_empties_the_file(self):
        self.run_picks({"a": {"B": raster_pick()}})
        self.assertIn("y", self.raster())
        self.run_picks({"a": {"B": {"pick": "shipped"}}})
        self.assertEqual(self.raster(), {})


class PageTest(unittest.TestCase):

    def test_spec_text_cannot_end_the_title_or_the_script_block(self):
        bad = "</title></script></SCRIPT><img src=x onerror=alert(1)>"
        page = gen.page_html({"title": bad, "overlays": [{"title": bad, "keys": [{"label": bad}]}]})
        template = (HOST / "tools" / "icon_picker_template.html").read_text(encoding="utf-8")
        for tag in ("</title>", "</script>"):
            self.assertEqual(page.lower().count(tag), template.lower().count(tag), tag)
        self.assertEqual(page.count("&lt;/title&gt;&lt;/script&gt;&lt;/SCRIPT&gt;&lt;img"), 2)    # <title>, <h1>

    def test_a_shipped_icon_with_two_modifiers_comes_from_the_combo_file(self):
        from PIL import Image

        from polyhost.device.keys import KeyCode, Modifier
        from polyhost.res.overlay_layout import CH, COMBO_CH, SLOT_H, SLOT_W, cell_for
        got = gen.shipped_icon("ableton_template.mods.png", "A", ["CTRL", "SHIFT"])
        arr = np.array(Image.open(build.RES / "overlays" / "ableton_template.combo.mods.png").convert("RGBA"))
        r, c = cell_for(KeyCode.KC_A)
        want = arr[r * SLOT_H:(r + 1) * SLOT_H, c * SLOT_W:(c + 1) * SLOT_W, CH[COMBO_CH[Modifier.CTRL_SHIFT]]] > 127
        self.assertTrue((got == want).all())
        with self.assertRaises(SystemExit):
            gen.shipped_icon("ableton_template.mods.png", "A", ["GUI"])


class ShippedApplyTest(unittest.TestCase):
    """For a source whose art ships (Warzone 2100), a picked game picture goes to
    pictures.yaml and the binding's region, never to a run-time recipe."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        (self.d / "w.yaml").write_text(
            "bindings:\n"
            "  - { key: A, icon: x.png, label: \"Attack\" }\n"
            "  - { key: B, icon: y.png, label: \"Build\" }\n", encoding="utf-8")
        keys = [{"key": "A", "label": "Attack", "candidates": [{"word": "Go"}]},
                {"key": "B", "label": "Build", "candidates": [{"word": "Go"}]}]
        (self.d / "picker.yaml").write_text(yaml.safe_dump({
            "reader": "warzone2100", "overlays": [{"id": "w", "spec": "w.yaml", "template": "w.png", "keys": keys}]}),
            encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_picks(self, picks):
        (self.d / "picks.json").write_text(json.dumps({"w": picks}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            apply.main([str(self.d / "picker.yaml"), str(self.d / "picks.json")])

    def pictures(self):
        return yaml.safe_load((self.d / "pictures.yaml").read_text(encoding="utf-8")) or {}

    def test_a_picture_ships_and_shipped_takes_it_back(self):
        self.assertTrue(src.Warzone2100.SHIPS)
        pic = dict(PIC, src="intfac:image_x")
        self.run_picks({"A": pic, "B": raster_pick()})
        self.assertEqual((self.pictures()["x"]["src"], self.pictures()["x"]["region"]), ("intfac:image_x", [47, 40]))
        text = (self.d / "w.yaml").read_text(encoding="utf-8")
        self.assertNotIn("game_assets", text)                       # no run-time recipe
        self.assertIn('icon: x.png, label: "Attack", region: [47, 40] }', text)
        self.assertEqual(set(yaml.safe_load((self.d / "rasterize.yaml").read_text(encoding="utf-8"))), {"y"})
        self.run_picks({"A": {"pick": "shipped"}, "B": {"pick": "shipped"}})
        self.assertEqual(self.pictures(), {})
        self.assertEqual(yaml.safe_load((self.d / "rasterize.yaml").read_text(encoding="utf-8")) or {}, {})

    def test_a_re_rasterized_pick_replaces_a_picture(self):
        self.run_picks({"A": dict(PIC, src="intfac:image_x")})
        self.run_picks({"A": raster_pick()})
        self.assertNotIn("x", self.pictures())
        self.assertIn("x", yaml.safe_load((self.d / "rasterize.yaml").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
