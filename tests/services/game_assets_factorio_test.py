"""The Factorio reader (polyhost/services/game_assets/factorio) on a synthetic
data folder.

Wube's images may not be committed, so the tests draw small coloured PNG files
laid out as a Factorio 2.0 data folder: 64x64 item icons with their mipmaps to
the right (120 px wide), 56 px shortcut icons, and the 64 px side-menu sheet.
They check where the folder is found, which square of a file is read, the three
drawing modes, and that a build replaces exactly the overlay cells the spec has
recipes for, read back through the same `ImageConverter` the device path uses.
"""
import json
import os
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.services import game_assets
from polyhost.services.game_assets import build
from polyhost.services.game_assets.factorio import reader as factorio

SPEC = build.RES / "overlay_sources" / "factorio" / "factorio.yaml"
TEMPLATES = ("factorio_template.mods.png", "factorio_template.combo.mods.png",
             "factorio_template_mac.mods.png", "factorio_template_mac.combo.mods.png")


# --------------------------------------------------------------------------- #
# a synthetic data folder (test-only)
# --------------------------------------------------------------------------- #

def item_art(seed: int, side: int = 64) -> Image.Image:
    """A coloured picture with light and dark parts, different per seed."""
    im = Image.new("RGBA", (side, side))
    d = ImageDraw.Draw(im)
    k = side / 64
    rng = np.random.default_rng(seed)
    body = tuple(int(c) for c in rng.integers(60, 200, 3)) + (255,)
    d.rounded_rectangle([8 * k, (10 + seed % 7) * k, 56 * k, 54 * k], 8 * k, fill=(30, 30, 30, 255))
    d.rounded_rectangle([10 * k, (12 + seed % 7) * k, 54 * k, 52 * k], 7 * k, fill=body)
    d.ellipse([(18 + seed % 9) * k, 22 * k, (38 + seed % 9) * k, 42 * k], fill=(240, 240, 230, 255))
    return im


def glyph(seed: int, side: int = 64) -> Image.Image:
    """A one-colour symbol on a transparent background, as the GUI icons are."""
    im = Image.new("RGBA", (side, side))
    d = ImageDraw.Draw(im)
    k = side / 64
    n = 3 + seed % 5
    pts = [(32 * k + 26 * k * np.cos(2 * np.pi * i / n + seed), 32 * k + 26 * k * np.sin(2 * np.pi * i / n + seed))
           for i in range(n)]
    d.polygon(pts, fill=(225, 225, 225, 255))
    return im


def with_mipmaps(im: Image.Image, levels: int = 4) -> Image.Image:
    """`im` with its smaller copies packed to the right, as Factorio stores
    icons. Each mipmap is filled solid, so a test can tell it was not read."""
    side = im.width
    widths = [side >> i for i in range(levels)]
    out = Image.new("RGBA", (sum(widths), side))
    out.paste(im, (0, 0))
    x = side
    for w in widths[1:]:
        out.paste(Image.new("RGBA", (w, w), (255, 0, 0, 255)), (x, 0))
        x += w
    return out


def sheet(rows: int, side: int = 64) -> Image.Image:
    """A side-menu sheet: one symbol per row, mipmap_count 2."""
    out = Image.new("RGBA", (side + side // 2, rows * side))
    for r in range(rows):
        out.paste(glyph(100 + r, side), (0, r * side))
        out.paste(glyph(100 + r, side // 2), (side, r * side))
    return out


def make_data(data: Path, shortcut_px: int = 56, skip=()) -> Path:
    """Every file the Factorio spec reads, under `data` (the data folder)."""
    for mod in ("base", "core"):
        (data / mod).mkdir(parents=True, exist_ok=True)
        (data / mod / "info.json").write_text(json.dumps({"name": mod, "version": "2.0.77"}))
    spec = build.load_spec(SPEC)
    for k, recipe in enumerate(spec["game_assets"]["icons"].values()):
        files = recipe["file"] if isinstance(recipe["file"], list) else [recipe["file"]]
        name = next((f for f in files if f"x{shortcut_px}" in f), files[0])
        if Path(name).name in skip:
            continue
        path = data.joinpath(*name.split("/"))
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if "side-menu-buttons" in name:
            sheet(12).save(path)
        elif "shortcut-toolbar" in name:
            with_mipmaps(glyph(k, shortcut_px)).save(path)
        elif recipe.get("mode") == "silhouette":
            with_mipmaps(glyph(k), 2).save(path)
        else:
            with_mipmaps(item_art(k)).save(path)
    return data


def no_known_installs(test: unittest.TestCase, home: Path) -> None:
    """No real Steam library, Program Files folder or home folder may answer."""
    for p in (mock.patch.object(factorio, "_steam_libraries", return_value=[]),
              mock.patch.dict(os.environ, {"PROGRAMFILES": "", "PROGRAMFILES(X86)": ""}),
              mock.patch.object(Path, "home", return_value=home)):
        p.start()
        test.addCleanup(p.stop)


# --------------------------------------------------------------------------- #

class FindTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        no_known_installs(self, self.root / "home")
        (self.root / "home").mkdir()

    def test_the_configured_folder_may_be_the_data_or_the_install_folder(self):
        inst = self.root / "Factorio"
        make_data(inst / "data")
        for folder in (inst / "data", inst):
            self.assertEqual(factorio.find(str(folder)), {"data": inst / "data"})

    def test_the_configured_folder_may_be_the_macos_app(self):
        app = self.root / "factorio.app"
        make_data(app / "Contents" / "data")
        self.assertEqual(factorio.find(str(app))["data"], app / "Contents" / "data")
        self.assertEqual(factorio.find(str(self.root))["data"], app / "Contents" / "data")

    def test_a_folder_without_the_mods_is_not_used(self):
        d = self.root / "data"
        (d / "base" / "graphics" / "icons").mkdir(parents=True)
        (d / "base" / "info.json").write_text("{}")
        self.assertIsNone(factorio.find(str(d)), "core/info.json is missing")
        self.assertIsNone(factorio.find(""))

    def test_a_steam_library_is_searched(self):
        lib = self.root / "lib"
        make_data(lib / "steamapps" / "common" / "Factorio" / "data")
        with mock.patch.object(factorio, "_steam_libraries", return_value=[lib]):
            self.assertEqual(factorio.find("")["data"], lib / "steamapps" / "common" / "Factorio" / "data")

    def test_the_macos_steam_layout_is_searched(self):
        lib = self.root / "lib"
        data = lib / "steamapps" / "common" / "Factorio" / "factorio.app" / "Contents" / "data"
        make_data(data)
        with mock.patch.object(factorio, "_steam_libraries", return_value=[lib]):
            self.assertEqual(factorio.find("")["data"], data)

    def test_the_standalone_installs_are_searched(self):
        pf = self.root / "pf"
        make_data(pf / "Factorio" / "data")
        with mock.patch.dict(os.environ, {"PROGRAMFILES": str(pf)}):
            self.assertEqual(factorio.find("")["data"], pf / "Factorio" / "data")
        with tempfile.TemporaryDirectory() as home:
            make_data(Path(home) / "factorio" / "data")
            with mock.patch.object(Path, "home", return_value=Path(home)):
                self.assertEqual(factorio.find("")["data"], Path(home) / "factorio" / "data")

    def test_the_running_game_folder_is_searched_first(self):
        """The executable is bin/x64/factorio; the data folder is two levels up.
        An install in no folder the host knows is found from it, and before a
        Steam install."""
        inst = self.root / "Games" / "Factorio Space Age"
        make_data(inst / "data")
        (inst / "bin" / "x64").mkdir(parents=True)
        lib = self.root / "lib"
        make_data(lib / "steamapps" / "common" / "Factorio" / "data")
        self.assertIsNone(factorio.find(""))
        with mock.patch.object(factorio, "_steam_libraries", return_value=[lib]):
            self.assertEqual(factorio.find("", hint=inst / "bin" / "x64")["data"], inst / "data")
            self.assertEqual(factorio.find("", hint=str(inst))["data"], inst / "data",
                             "Proton's working folder is the install folder")

    def test_the_cache_key_is_the_mods_manifests(self):
        make_data(self.root / "data")
        files = factorio.fingerprint(factorio.find(str(self.root / "data")))
        self.assertEqual([p.name for p in files], ["info.json", "info.json"])
        self.assertTrue(all(p.exists() for p in files))


class PictureTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.icons = factorio.Icons(self.data)

    def _save(self, name, im):
        path = self.data.joinpath(*name.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        im.save(path)

    def test_only_the_first_square_of_a_mipmapped_icon_is_read(self):
        art = item_art(3)
        self._save("base/graphics/icons/pistol.png", with_mipmaps(art))
        with Image.open(self.data / "base/graphics/icons/pistol.png") as im:
            self.assertEqual(im.size, (120, 64))
        grey, alpha = factorio.picture(self.icons, {"file": "base/graphics/icons/pistol.png"})
        self.assertEqual(grey.shape, (64, 64))
        np.testing.assert_allclose(alpha, np.asarray(art, float)[..., 3] / 255)
        # The red mipmaps would light every pixel of the right part if read.
        mask = factorio.draw(self.icons, {"file": "base/graphics/icons/pistol.png"}, (40, 40))
        self.assertLess(mask.mean(), 0.9)

    def test_a_row_of_a_sheet(self):
        self._save("core/graphics/side-menu-buttons.png", sheet(12))
        for row in (0, 7, 11):
            _, alpha = factorio.picture(self.icons, {"file": "core/graphics/side-menu-buttons.png",
                                                     "size": 64, "row": row})
            want = np.asarray(glyph(100 + row), float)[..., 3] / 255
            np.testing.assert_allclose(alpha, want)
        with self.assertRaisesRegex(ValueError, "row 12"):
            factorio.picture(self.icons, {"file": "core/graphics/side-menu-buttons.png", "size": 64, "row": 12})

    def test_a_list_of_files_reads_the_first_present(self):
        """Shortcut icons are 56 px since 2.0.18 and 32 px before."""
        old = "base/graphics/icons/shortcut-toolbar/mip/new-blueprint-x32.png"
        new = "base/graphics/icons/shortcut-toolbar/mip/new-blueprint-x56.png"
        self._save(old, with_mipmaps(glyph(1, 32)))
        grey, _ = factorio.picture(self.icons, {"file": [new, old]})
        self.assertEqual(grey.shape, (32, 32))
        self._save(new, with_mipmaps(glyph(1, 56)))
        grey, _ = factorio.picture(factorio.Icons(self.data), {"file": [new, old]})
        self.assertEqual(grey.shape, (56, 56))

    def test_files_outside_the_data_folder_and_bad_files_are_refused(self):
        for name in ("../secret.png", "/etc/passwd", "base/../../x.png"):
            with self.assertRaises(ValueError, msg=name):
                self.icons.rgba(name)
        with self.assertRaises(KeyError):
            self.icons.rgba("base/graphics/icons/missing.png")
        (self.data / "base" / "graphics" / "icons").mkdir(parents=True)
        (self.data / "base/graphics/icons/broken.png").write_bytes(b"not a png")
        with self.assertRaises(ValueError):
            self.icons.rgba("base/graphics/icons/broken.png")
        self._save("base/graphics/icons/empty.png", Image.new("RGBA", (64, 64)))
        with self.assertRaisesRegex(ValueError, "empty"):
            factorio.draw(self.icons, {"file": "base/graphics/icons/empty.png"}, (40, 40))

    def test_a_huge_file_is_refused_before_decoding(self):
        self._save("base/graphics/icons/huge.png", Image.new("1", (5000, 4000)))
        with self.assertRaisesRegex(ValueError, "larger than"):
            self.icons.rgba("base/graphics/icons/huge.png")


class ModeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name)
        icons = cls.data / "base" / "graphics" / "icons"
        icons.mkdir(parents=True)
        with_mipmaps(item_art(5)).save(icons / "item.png")
        with_mipmaps(glyph(4)).save(icons / "glyph.png")
        # A light symbol with a dark line drawn on it: not one colour.
        lined = glyph(4)
        ImageDraw.Draw(lined).line([(10, 32), (54, 32)], fill=(20, 20, 20, 255), width=5)
        with_mipmaps(lined).save(icons / "lined.png")
        # A disc shaded from light to dark, as rendered item art is.
        yy, xx = np.mgrid[0:64, 0:64]
        disc = (yy - 32) ** 2 + (xx - 32) ** 2 <= 28 ** 2
        shade = (40 + 200 * xx / 63).astype(np.uint8)
        rgba = np.dstack([shade, shade, shade, np.where(disc, 255, 0).astype(np.uint8)])
        with_mipmaps(Image.fromarray(rgba, "RGBA")).save(icons / "shaded.png")
        cls.icons = factorio.Icons(cls.data)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def draw(self, stem, mode, size=(40, 40)):
        return factorio.draw(self.icons, {"file": f"base/graphics/icons/{stem}.png", "mode": mode}, size)

    def test_every_mode_fits_the_area(self):
        for mode in ("dither", "threshold", "silhouette"):
            for size in ((40, 40), (34, 40), (30, 34)):
                m = self.draw("item", mode, size)
                self.assertLessEqual(m.shape[1], size[0])
                self.assertLessEqual(m.shape[0], size[1])
                self.assertTrue(m.any())

    def test_a_silhouette_is_the_shape_of_a_one_colour_symbol(self):
        m = self.draw("glyph", "silhouette")
        alpha = np.asarray(glyph(4).getchannel("A")) > 127
        ys, xs = np.nonzero(alpha)
        alpha = alpha[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        self.assertGreater(m.mean(), 0.9 * alpha.mean(), "the shape is filled, not outlined")
        self.assertEqual(factorio.mode_for(*self._grey_cover("glyph"), "silhouette"), "silhouette")

    def _grey_cover(self, stem):
        grey, alpha = factorio.picture(self.icons, {"file": f"base/graphics/icons/{stem}.png"})
        return grey, alpha >= 0.5

    def test_a_silhouette_with_inner_lines_keeps_them(self):
        self.assertEqual(factorio.mode_for(*self._grey_cover("lined"), "silhouette"), "threshold")
        self.assertEqual(factorio.mode_for(*self._grey_cover("item"), "silhouette"), "threshold",
                         "coloured art on an opaque body is not a silhouette")
        m = self.draw("lined", "silhouette")
        self.assertFalse(m[m.shape[0] // 2, 3:-3].all(), "the dark line must stay dark")

    def test_threshold_has_no_dither_pattern(self):
        """On a shaded picture a dither lights scattered pixels across the
        whole body; a threshold splits it into one lit and one dark part."""
        def isolated(m):
            """Lit pixels with none of their eight neighbours lit."""
            p = np.pad(m, 1).astype(int)
            h, w = m.shape
            n = sum(p[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx)
            return int((m & (n == 0)).sum())
        self.assertEqual(isolated(self.draw("shaded", "threshold")), 0)
        self.assertGreater(isolated(self.draw("shaded", "dither")), 20)
        m = self.draw("shaded", "threshold")
        mid = m[m.shape[0] // 2, 2:-2]
        self.assertFalse(mid[:len(mid) // 3].any(), "the dark side stays dark")
        self.assertTrue(mid[-len(mid) // 3:].all(), "the light side is lit")

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            self.draw("item", "sepia")


class BuildTest(unittest.TestCase):
    """The whole build on the shipped Factorio overlays."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = make_data(Path(cls.tmp.name) / "Factorio" / "data")
        cls.cache = Path(cls.tmp.name) / "cache"
        cls.built = {t: cls.build_copy(t) for t in TEMPLATES}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def build_copy(cls, template, data=None, cache=None):
        settings = {"game_factorio_data_dir": str(data or cls.data)}
        return build.build(template, SPEC, settings.get, Path(cache or cls.cache))

    @staticmethod
    def _cells(path, mod):
        conv = ImageConverter(DeviceSettings())
        if not conv.open(str(path)):
            raise AssertionError(f"cannot open {path}")
        cells = conv.extract_overlays(mod) or {}
        return {kc: od.all_bytes for kc, od in cells.items()}, conv.no_legend

    # Keys drawn from the game on the primary file, per layer.
    DRAWN = {Modifier.NO_MOD: {"C", "ENTER", "G", "F1", "F2", "TAB", "M", "T", "P", "L", "B", "O"},
             Modifier.ALT: {"B", "D", "U", "T", "Y", "A", "E", "F", "L"},
             Modifier.CTRL: set(), Modifier.SHIFT: set()}

    def test_exactly_the_drawn_keys_change(self):
        for template in ("factorio_template.mods.png", "factorio_template_mac.mods.png"):
            path = self.built[template]
            self.assertIsNotNone(path, template)
            for mod, keys in self.DRAWN.items():
                shipped, shipped_nl = self._cells(build.RES / "overlays" / template, mod)
                patched, patched_nl = self._cells(path, mod)
                self.assertEqual(shipped_nl, patched_nl, "the no-legend list must carry over")
                want = {KeyCode[f"KC_{k}"].value for k in keys}
                for kc in set(shipped) | set(patched):
                    changed = shipped.get(kc) != patched.get(kc)
                    self.assertEqual(changed, kc in want,
                                     f"{template} {mod.name} keycode 0x{kc:02x}: "
                                     f"{'changed' if changed else 'unchanged'}")
                for kc in want:
                    self.assertIn(kc, patched, f"{template} {mod.name} 0x{kc:02x} drew nothing")

    def test_the_two_modifier_files_keep_the_shipped_art(self):
        """No recipe is on a two-modifier key; the copy equals the shipped cells."""
        for template in ("factorio_template.combo.mods.png", "factorio_template_mac.combo.mods.png"):
            for mod in (Modifier.CTRL_SHIFT, Modifier.CTRL_ALT, Modifier.ALT_SHIFT):
                shipped, _ = self._cells(build.RES / "overlays" / template, mod)
                patched, _ = self._cells(self.built[template], mod)
                self.assertEqual(shipped, patched, f"{template} {mod.name}")

    def test_a_drawn_key_stays_in_its_area(self):
        """F1 and F2 keep their legend: nothing is lit left of their 34 px area."""
        from polyhost.res.overlay_layout import CH, PRIMARY_CH, SLOT_H, SLOT_W, cell_for
        with Image.open(self.built["factorio_template.mods.png"]) as im:
            arr = np.array(im.convert("RGBA"))
        for key in ("F1", "F2"):
            row, col = cell_for(KeyCode[f"KC_{key}"])
            cell = arr[row * SLOT_H:(row + 1) * SLOT_H, col * SLOT_W:(col + 1) * SLOT_W]
            lit = np.nonzero(cell[..., CH[PRIMARY_CH[Modifier.NO_MOD]]])[1]
            self.assertTrue(lit.size)
            self.assertGreaterEqual(lit.min(), SLOT_W - 34, key)

    def test_a_missing_icon_costs_only_its_key(self):
        with tempfile.TemporaryDirectory() as d:
            data = make_data(Path(d) / "data", skip={"pistol.png", "side-menu-buttons.png"})
            with self.assertLogs("PolyHost", "WARNING") as logs:
                path = self.build_copy("factorio_template.mods.png", data, Path(d) / "cache")
            shipped, _ = self._cells(build.RES / "overlays" / "factorio_template.mods.png", Modifier.NO_MOD)
            patched, _ = self._cells(path, Modifier.NO_MOD)
        self.assertEqual(len(logs.output), 7, logs.output)    # pistol and the six side-menu icons
        for key in ("C", "T", "M", "B"):
            kc = KeyCode[f"KC_{key}"].value
            self.assertEqual(shipped[kc], patched[kc], key)
        kc = KeyCode.KC_ENTER.value
        self.assertNotEqual(shipped[kc], patched[kc])

    def test_the_old_32_px_shortcut_icons_are_read(self):
        with tempfile.TemporaryDirectory() as d:
            data = make_data(Path(d) / "data", shortcut_px=32)
            self.assertFalse(any(data.rglob("*-x56.png")))
            path = self.build_copy("factorio_template.mods.png", data, Path(d) / "cache")
            shipped, _ = self._cells(build.RES / "overlays" / "factorio_template.mods.png", Modifier.ALT)
            patched, _ = self._cells(path, Modifier.ALT)
        for key in self.DRAWN[Modifier.ALT]:
            kc = KeyCode[f"KC_{key}"].value
            self.assertNotEqual(shipped[kc], patched[kc], key)

    def test_without_an_install_there_is_no_copy(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(self.build_copy("factorio_template.mods.png", Path(d), Path(d)))

    def test_a_cached_copy_is_not_rebuilt(self):
        path = self.built["factorio_template.mods.png"]
        stamp = os.stat(path).st_mtime_ns
        self.assertEqual(self.build_copy("factorio_template.mods.png"), path)
        self.assertEqual(os.stat(path).st_mtime_ns, stamp)
        self.assertIn(".all.", path.name, "no variant setting: the copy is named 'all'")


class SpecTest(unittest.TestCase):

    def test_every_recipe_replaces_a_bound_icon(self):
        spec = build.load_spec(SPEC)
        stems = {Path(b["icon"]).stem for b in build.bindings(spec) if "icon" in b}
        got = build.recipes(spec, "")
        self.assertEqual(set(got) - stems, set(), "a recipe for no key")
        for stem, recipe in got.items():
            self.assertIn(recipe.get("mode", "dither"), ("dither", "threshold", "silhouette"), stem)

    def test_every_file_is_named_as_the_game_names_it(self):
        """Paths are relative to the data folder: <mod>/graphics/..., forward slashes."""
        for stem, recipe in build.recipes(build.load_spec(SPEC), "").items():
            files = recipe["file"] if isinstance(recipe["file"], list) else [recipe["file"]]
            for f in files:
                self.assertRegex(f, r"^(base|core)/graphics/[a-z0-9/_-]+\.png$", stem)

    def test_the_mapping_registers_both_template_sets(self):
        import yaml
        with open(build.RES / "overlay-mapping.poly.yaml", encoding="utf-8") as f:
            mapping = yaml.safe_load(f)
        with mock.patch.dict(game_assets._specs, clear=True):
            game_assets.register_mapping(mapping)
            for template in (*TEMPLATES, "factorio_template_mac.extra.mods.png"):
                self.assertEqual(game_assets._specs.get(template), SPEC, template)


if __name__ == "__main__":
    unittest.main()
