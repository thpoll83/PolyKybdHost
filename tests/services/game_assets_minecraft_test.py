"""The Minecraft: Java Edition reader (polyhost/services/game_assets/minecraft_java)
on a synthetic game folder.

Mojang's files may not be committed, so the tests write a small client jar (a
zip) with 16x16 PNGs and the version json beside it. They check which version
is chosen, how a picture is read and scaled, and that a build through every
mapping route to the Java set replaces exactly the keys the spec has art for.
"""
import io
import json
import os
import tempfile
import unittest
import unittest.mock as mock
import zipfile
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.services import game_assets
from polyhost.services.game_assets import build
from polyhost.services.game_assets.minecraft_java import reader as mc

TEMPLATE = "minecraft_java_template.mods.png"
COMBO = "minecraft_java_template.combo.mods.png"
SPEC = build.RES / "overlay_sources" / "minecraft" / "minecraft_java.yaml"
SHIPPED = build.RES / "overlays" / TEMPLATE
MAPPING = build.RES / "overlay-mapping.poly.yaml"

# The keys the spec redraws, all on the plain layer.
DRAWN = {"E", "T", "L", "F2", "F5"}
CTRL_SHIFT = Modifier(Modifier.CTRL.value | Modifier.SHIFT.value)


def texture(seed: int, w: int = 16, h: int = 16) -> bytes:
    """A 16x16 item picture: a dark outline round a bright body with a darker
    stripe, its size and stripe different per seed, on a transparent ground."""
    a = np.zeros((h, w, 4), np.uint8)
    x0, y0 = 1 + seed % 3, 2 + seed % 2
    x1, y1 = w - 2, h - 1 - seed % 3
    a[y0:y1, x0:x1] = (30, 20, 10, 255)                     # the outline
    a[y0 + 1:y1 - 1, x0 + 1:x1 - 1] = (200, 180, 90, 255)   # the body
    a[y0 + 1 + seed % 5, x0 + 1:x1 - 1] = (60, 50, 30, 255)  # a stripe of shading
    buf = io.BytesIO()
    Image.fromarray(a, "RGBA").save(buf, format="PNG")
    return buf.getvalue()


ITEMS = ("bundle", "writable_book", "nether_star", "painting", "armor_stand", "apple")


def write_jar(path: Path, items=ITEMS, extra=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for i, name in enumerate(items):
            z.writestr(f"{mc.TEXTURES}item/{name}.png", texture(i))
        z.writestr("net/minecraft/client/Main.class", b"\xca\xfe\xba\xbe")
        for name, data in (extra or {}).items():
            z.writestr(name, data)


def add_version(game: Path, vid: str, vtype: str = "release", time: str = "2025-10-07T09:17:23+00:00",
                jar: bool = True, inherits: str | None = None, items=ITEMS) -> Path:
    d = game / "versions" / vid
    d.mkdir(parents=True, exist_ok=True)
    info = {"id": vid, "type": vtype, "releaseTime": time, "time": time}
    if inherits:
        info["inheritsFrom"] = inherits
    (d / f"{vid}.json").write_text(json.dumps(info), encoding="utf-8")
    if jar:
        write_jar(d / f"{vid}.jar", items)
    return d


class NoInstallsMixin:
    """No real game folder on this machine may answer for these tests."""

    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        p = mock.patch.object(Path, "home", return_value=Path(self.home.name))
        p.start()
        self.addCleanup(p.stop)
        e = mock.patch.dict(os.environ, {"APPDATA": ""})
        e.start()
        self.addCleanup(e.stop)


class FindTest(NoInstallsMixin, unittest.TestCase):

    def test_the_newest_release_is_chosen_and_a_snapshot_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            game = Path(d)
            add_version(game, "1.21.4", time="2024-12-03T10:12:57+00:00")
            add_version(game, "1.21.10", time="2025-10-07T09:17:23+00:00")
            add_version(game, "25w41a", "snapshot", time="2025-10-08T12:00:00+00:00")
            # A mod-loader profile reuses the vanilla jar; a version without its
            # jar was never started.
            add_version(game, "fabric-loader-0.17-1.21.10", time="2025-10-09T00:00:00Z",
                        inherits="1.21.10")
            add_version(game, "1.21.11", time="2025-12-09T00:00:00Z", jar=False)
            (game / "versions" / "broken").mkdir()
            (game / "versions" / "broken" / "broken.json").write_text("{", encoding="utf-8")
            (game / "versions" / "broken" / "broken.jar").write_bytes(b"")
            files = mc.find(d)
            self.assertEqual(files["id"], "1.21.10")
            self.assertEqual(files["jar"], game / "versions" / "1.21.10" / "1.21.10.jar")

    def test_a_snapshot_is_used_when_no_release_is_installed(self):
        with tempfile.TemporaryDirectory() as d:
            add_version(Path(d), "25w40a", "snapshot", time="2025-10-01T10:00:00Z")
            add_version(Path(d), "25w41a", "snapshot", time="2025-10-08T10:00:00Z")
            add_version(Path(d), "old_alpha", "old_alpha", time="2010-07-02T00:00:00+00:00")
            self.assertEqual(mc.find(d)["id"], "25w41a")

    def test_a_folder_without_versions_is_not_used(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(mc.find(d))
            add_version(Path(d), "1.21.10", jar=False)
            self.assertIsNone(mc.find(d))

    def test_the_standard_game_folder_is_searched(self):
        game = Path(self.home.name) / ".minecraft"
        add_version(game, "1.21.10")
        self.assertEqual(mc.find("")["jar"].parent, game / "versions" / "1.21.10")

    def test_windows_appdata_is_searched_first(self):
        with tempfile.TemporaryDirectory() as d:
            add_version(Path(d) / ".minecraft", "26.3")
            add_version(Path(self.home.name) / ".minecraft", "1.21.10")
            with mock.patch.dict(os.environ, {"APPDATA": d}):
                self.assertEqual(mc.find("")["id"], "26.3")

    def test_the_game_folder_above_the_running_java_is_searched_first(self):
        """A game folder in no standard place is found from the launcher's Java
        runtime inside it."""
        with tempfile.TemporaryDirectory() as d:
            game = Path(d) / "Games" / "mc"
            add_version(game, "1.21.4")
            runtime = game / "runtime" / "java-runtime-delta" / "linux" / "bin"
            runtime.mkdir(parents=True)
            self.assertIsNone(mc.find(""))
            self.assertEqual(mc.find("", hint=runtime)["id"], "1.21.4")


class TextureTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        strip = io.BytesIO()
        frames = np.zeros((64, 16, 4), np.uint8)
        frames[:16, :8] = (250, 250, 250, 255)                # frame 0: the left half
        frames[16:, 8:] = (250, 250, 250, 255)
        Image.fromarray(frames, "RGBA").save(strip, format="PNG")
        big = io.BytesIO()
        Image.new("RGBA", (128, 128), (255, 255, 255, 255)).save(big, format="PNG")
        self.jar = Path(self.tmp.name) / "1.21.10.jar"
        write_jar(self.jar, extra={f"{mc.TEXTURES}block/sea_lantern.png": strip.getvalue(),
                                   f"{mc.TEXTURES}item/huge.png": big.getvalue(),
                                   f"{mc.TEXTURES}item/not_a_png.png": b"not a picture"})
        self.src = mc.Textures(self.jar)

    def test_a_picture_is_read_with_or_without_png(self):
        a = self.src.rgba("item/bundle")
        self.assertEqual(a.shape, (16, 16, 4))
        np.testing.assert_array_equal(a, self.src.rgba("item/bundle.png"))

    def test_a_missing_or_broken_picture_raises_what_render_skips(self):
        with self.assertRaises(KeyError):
            self.src.rgba("item/shield")
        with self.assertRaises(ValueError):
            self.src.rgba("item/huge")
        with self.assertRaises(ValueError):
            self.src.rgba("item/not_a_png")

    def test_an_animation_strip_gives_its_first_frame(self):
        a = self.src.rgba("block/sea_lantern")
        self.assertEqual(a.shape, (16, 16, 4))
        self.assertTrue((a[:, :8, 3] == 1).all() and (a[:, 8:, 3] == 0).all())

    def test_one_bit_keeps_the_bright_body_and_drops_the_dark_outline(self):
        m = mc.one_bit(self.src.rgba("item/bundle"))
        # Texture 0: outline rows 2 and 14, columns 1 and 13 -> cropped 13 x 13.
        self.assertEqual(m.shape, (13, 13))
        self.assertFalse(m[0].any() or m[-1].any() or m[:, 0].any() or m[:, -1].any())
        self.assertTrue(m[2, 1:-1].all())
        self.assertFalse(m[1, 1:-1].any(), "the stripe of shading stays dark")
        self.assertTrue(mc.one_bit(self.src.rgba("item/bundle"), silhouette=True).all())

    def test_a_picture_that_would_be_mostly_dark_is_drawn_as_its_silhouette(self):
        a = np.zeros((16, 16, 4))
        a[4:12, 4:12] = (0.1, 0.1, 0.1, 1)
        a[7, 7] = (0.9, 0.9, 0.9, 1)
        self.assertTrue(mc.one_bit(a).all())

    def test_fit_scales_by_a_whole_number_at_the_right_edge(self):
        m = np.zeros((13, 12), bool)
        m[0, 0] = m[-1, -1] = True
        out = mc.fit(m, (40, 40))
        self.assertEqual(out.shape, (40, 40))
        ys, xs = np.nonzero(out)
        # 3x: 39 x 36, at the right edge, centred from top to bottom.
        self.assertEqual((ys.min(), ys.max(), xs.min(), xs.max()), (0, 38, 4, 39))
        self.assertEqual(out.sum(), 2 * 9)
        two = mc.fit(m, (34, 40))
        ys, xs = np.nonzero(two)
        self.assertEqual((ys.max() - ys.min() + 1, xs.max() - xs.min() + 1), (26, 24))
        self.assertEqual(xs.max(), 33)
        ys, xs = np.nonzero(mc.fit(m, (40, 40), scale=1))
        self.assertEqual((ys.min(), ys.max(), xs.max()), (13, 25, 39))

    def test_a_mask_larger_than_the_area_is_shrunk(self):
        out = mc.fit(np.ones((60, 30), bool), (34, 40))
        self.assertEqual(out.shape, (40, 34))
        self.assertTrue(out.any())

    def test_one_bad_recipe_costs_only_its_own_key(self):
        spec = {"game_assets": {"reader": "minecraft_java", "icons": {
                    "chat": {"texture": "item/no_such_item"}, "inventory": {"texture": "item/huge"},
                    "advancements": {"texture": "item/nether_star"}}},
                "bindings": [{"key": k, "icon": f"{s}.png"}
                             for k, s in (("T", "chat"), ("E", "inventory"), ("L", "advancements"))]}
        with self.assertLogs("PolyHost", "WARNING") as logs:
            icons = build.render(mc, self.src, spec, "")
        self.assertEqual(set(icons), {"advancements"})
        self.assertEqual(len(logs.output), 2)

    def test_draw_refuses_an_unknown_recipe(self):
        with self.assertRaises(ValueError):
            mc.draw(self.src, {"item": "bundle"}, (40, 40))


def _cells(path, mod):
    conv = ImageConverter(DeviceSettings())
    if not conv.open(str(path)):
        raise AssertionError(f"cannot open {path}")
    cells = conv.extract_overlays(mod) or {}
    return {kc: od.all_bytes for kc, od in cells.items()}, conv.no_legend


def _walk(entry, path=()):
    """(path, sub-entry) of every dict in a mapping entry that has an overlay."""
    if not isinstance(entry, dict):
        return
    if entry.get("overlay"):
        yield path, entry
    for k, v in entry.items():
        if isinstance(v, dict):
            for sk, sv in v.items():
                yield from _walk(sv, path + (k, sk))


class MappingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(MAPPING, encoding="utf-8") as f:
            cls.mapping = yaml.safe_load(f)

    def test_every_route_to_the_java_set_opts_in(self):
        routes = 0
        for key, entry in self.mapping.items():
            for path, sub in _walk(entry, (key,)):
                overlay = sub["overlay"] if isinstance(sub["overlay"], list) else [sub["overlay"]]
                if TEMPLATE in overlay:
                    routes += 1
                    with self.subTest(route=path):
                        self.assertEqual(sub.get("game_assets"), "minecraft/minecraft_java.yaml")
        self.assertGreaterEqual(routes, 8)

    def test_the_mapping_registers_both_files_with_the_spec(self):
        with mock.patch.dict(game_assets._specs, clear=True):
            game_assets.register_mapping(self.mapping)
            self.assertEqual(game_assets._specs.get(TEMPLATE), SPEC)
            self.assertEqual(game_assets._specs.get(COMBO), SPEC)

    def test_every_recipe_replaces_a_bound_icon_on_the_plain_layer(self):
        spec = build.load_spec(SPEC)
        got = build.recipes(spec, "")
        bound = {}
        for b in build.bindings(spec):
            bound.setdefault(Path(b["icon"]).stem, []).append(b)
        self.assertEqual(set(got) - set(bound), set(), "a recipe for no key")
        keys = {str(b["key"]).upper() for s in got for b in bound[s]}
        self.assertEqual(keys, DRAWN)
        for stem, recipe in got.items():
            self.assertTrue(str(recipe["texture"]).startswith(("item/", "block/")), stem)


try:  # the matcher needs the mapping annotated by OverlayHandler (pywinctl)
    from polyhost.handler.active_window import OverlayHandler
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - headless/no-display env
    _IMPORT_ERR = e


class BuildTest(NoInstallsMixin, unittest.TestCase):
    """End to end: a route through the mapping, then build.build() with the spec
    the matched entry names, read back as the device path reads it."""

    ROUTES = (  # (app name, window title, OS)
        ("javaw", "Minecraft 1.21.10 - Singleplayer", "WINDOWS"),
        ("java", "Minecraft* 1.21.10", "WINDOWS"),
        ("java", "Minecraft 1.21.10", "LINUX"),
        ("java", "Minecraft 1.21.10", "MACOS"),
        ("minecraft", "", "LINUX"),
        ("minecraft 1.21.10", "Minecraft 1.21.10", "LINUX"),
        ("minecraft* 1.21.10", "Minecraft* 1.21.10", "LINUX"),
        ("minecraft", "Minecraft 1.21.10", "MACOS"),
    )

    @classmethod
    def setUpClass(cls):
        with open(MAPPING, encoding="utf-8") as f:
            cls.mapping = yaml.safe_load(f)
        cls.annotated = OverlayHandler(yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping \
            if _IMPORT_ERR is None else None

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.game = Path(self.tmp.name) / "game"
        add_version(self.game, "1.21.10")
        self.settings = {"game_minecraft_dir": str(self.game)}

    def _route(self, app, title, os_name):
        from polyhost.device.command_ids import OsType
        from polyhost.handler.common import find_matching_entry, mapping_key
        key = mapping_key(app, self.annotated)
        self.assertIsNotNone(key, app)
        return find_matching_entry(title, self.annotated[key], None, OsType[os_name], title_known=True)

    @unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
    def test_every_route_builds_the_drawn_keys_and_only_those(self):
        shipped = {mod: _cells(SHIPPED, mod) for mod in (Modifier.NO_MOD, Modifier.CTRL, Modifier.SHIFT)}
        want = {KeyCode[f"KC_{k}"].value for k in DRAWN}
        for app, title, os_name in self.ROUTES:
            with self.subTest(app=app, title=title, os=os_name):
                entry = self._route(app, title, os_name)
                self.assertIsNotNone(entry)
                self.assertIn(TEMPLATE, entry["overlay"])
                spec = build.RES / "overlay_sources" / entry["game_assets"]
                self.assertEqual(spec, SPEC)
                cache = Path(self.tmp.name) / f"cache-{app}-{os_name}"
                path = build.build(TEMPLATE, spec, self.settings.get, cache)
                self.assertIsNotNone(path)
                self.assertIn(".mods.", path.name)
                for mod, (ship_cells, ship_nl) in shipped.items():
                    cells, nl = _cells(path, mod)
                    self.assertEqual(nl, ship_nl, "the no-legend list must carry over")
                    expected = want if mod == Modifier.NO_MOD else set()
                    for kc in set(ship_cells) | set(cells):
                        changed = ship_cells.get(kc) != cells.get(kc)
                        self.assertEqual(changed, kc in expected, f"{mod.name} 0x{kc:02x}")
                # The combo file has no art; its copy keeps every cell.
                combo = build.build(COMBO, spec, self.settings.get, cache)
                self.assertEqual(_cells(combo, CTRL_SHIFT)[0],
                                 _cells(build.RES / "overlays" / COMBO, CTRL_SHIFT)[0])

    def test_without_a_client_jar_there_is_no_copy(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(build.build(TEMPLATE, SPEC, {"game_minecraft_dir": d}.get, Path(d)))
            self.assertIsNone(build.build(TEMPLATE, SPEC, {"game_minecraft_dir": ""}.get, Path(d)))

    def test_a_jar_without_some_pictures_keeps_the_shipped_art_there(self):
        add_version(self.game, "26.3", time="2026-09-01T00:00:00Z", items=("bundle", "painting"))
        with self.assertLogs("PolyHost", "INFO") as logs:
            path = build.build(TEMPLATE, SPEC, self.settings.get, Path(self.tmp.name) / "c")
        self.assertTrue(any("2 keys" in line for line in logs.output), logs.output)
        ship, got = _cells(SHIPPED, Modifier.NO_MOD)[0], _cells(path, Modifier.NO_MOD)[0]
        changed = {kc for kc in ship if ship[kc] != got.get(kc)}
        self.assertEqual(changed, {KeyCode.KC_E.value, KeyCode.KC_F2.value})

    def test_a_newer_release_builds_a_new_copy(self):
        cache = Path(self.tmp.name) / "c"
        first = build.build(TEMPLATE, SPEC, self.settings.get, cache)
        self.assertEqual(build.build(TEMPLATE, SPEC, self.settings.get, cache), first)
        add_version(self.game, "26.3", time="2026-09-01T00:00:00Z")
        self.assertNotEqual(build.build(TEMPLATE, SPEC, self.settings.get, cache), first)

    def test_a_damaged_jar_is_reported_and_the_shipped_overlay_stays(self):
        """request() logs and keeps the shipped file for a jar that is not a zip."""
        bad = add_version(Path(self.tmp.name) / "bad", "1.21.10", jar=False)
        (bad / "1.21.10.jar").write_bytes(b"not a zip")
        settings = {"game_assets_enabled": True, "game_minecraft_dir": str(bad.parents[1])}
        with mock.patch.dict(game_assets._specs, {TEMPLATE: SPEC}, clear=True), \
                mock.patch.dict(game_assets._overrides, clear=True), \
                mock.patch.dict(game_assets._started, clear=True), \
                mock.patch.object(game_assets, "_seen", set()), \
                mock.patch.object(game_assets, "cache_dir", return_value=Path(self.tmp.name) / "c"):
            with self.assertLogs("PolyHost", "WARNING") as logs:
                t = game_assets.request(TEMPLATE, settings.get)
                t.join(60)
            self.assertIsNone(game_assets.override_for(TEMPLATE))
        game_assets.take_changed()
        self.assertTrue(any("BadZipFile" in line for line in logs.output), logs.output)


if __name__ == "__main__":
    unittest.main()
