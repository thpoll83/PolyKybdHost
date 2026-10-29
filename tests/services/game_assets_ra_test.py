"""The Red Alert reader (westwood_ra), the OpenRA content folders, and the
OpenRA overlays drawn from them. Synthetic game files only."""
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
from polyhost.services.game_assets import build, dither, openra
from polyhost.services.game_assets.westwood_ra import mix
from polyhost.services.game_assets.westwood_ra import reader as westwood_ra
from polyhost.services.game_assets.westwood_td import reader as westwood_td
from polyhost.services.game_assets.westwood_td import westwood
from tests.services.game_assets_test import blob_frame, make_game_files, write_d2, write_shp

SOURCES = build.RES / "overlay_sources" / "openra"
RA_SPEC, TD_SPEC = SOURCES / "openra_ra.yaml", SOURCES / "openra_cnc.yaml"
OVERLAYS = build.RES / "overlays"

# Every sprite the Red Alert spec draws, with enough frames for its facings.
RA_SPRITES = {
    "jeep": (64, 24, 24), "v2rl": (32, 24, 24), "apc": (32, 24, 24), "3tnk": (64, 24, 24),
    "1tnk": (64, 24, 24), "4tnk": (64, 24, 24), "2tnk": (64, 24, 24), "ss": (16, 24, 24),
    "arty": (32, 24, 24), "truk": (32, 24, 24), "dd": (16, 24, 48), "mig": (16, 24, 24),
    "yak": (16, 24, 24), "heli": (32, 29, 46), "hind": (32, 29, 46), "lrotor": (12, 15, 29),
    "harv": (32, 24, 24), "fact": (1, 48, 72), "dome": (1, 48, 48),
}
INFANTRY = {"e1": (6, 20, 10), "spy": (6, 20, 10)}


def encrypt(key: bytes, data: bytes) -> bytes:
    bf = mix.Blowfish(key)
    out = bytearray()
    for i in range(0, len(data), 8):
        out += struct.pack(">II", *bf._encrypt(*struct.unpack_from(">II", data, i)))
    return bytes(out)


def ra_mix(files: dict, encrypted: bool = True) -> bytes:
    """A Red Alert MIX. The key bytes are arbitrary: the reader derives the
    Blowfish key from them with the public key, and so does this encoder."""
    body, entries = bytearray(), []
    for name, data in files.items():
        entries.append((westwood.td_hash(name), len(body), len(data)))
        body += data
    head = struct.pack("<HI", len(entries), len(body))
    for e in sorted(entries):
        head += struct.pack("<III", *e)
    if not encrypted:
        return struct.pack("<I", 0) + head + bytes(body)
    source = key_source()
    head += b"\0" * (-len(head) % 8)
    return (struct.pack("<I", mix.ENCRYPTED) + source
            + encrypt(mix.blowfish_key(source), head) + bytes(body))


def key_source() -> bytes:
    """80 bytes whose two blocks decrypt to 39 bytes, as the game's own do."""
    for seed in range(1000):
        source = bytes((i * 37 + seed) % 256 for i in range(mix.KEY_SOURCE))
        try:
            mix.blowfish_key(source)
            return source
        except ValueError:
            continue
    raise AssertionError("no key source found")


def make_ra_files(folder: Path) -> None:
    """CONQUER.MIX (plain), HIRES.MIX and LOCAL.MIX (encrypted)."""
    conquer = {f"{n}.shp": write_shp([blob_frame(h, w, k + i) for i in range(c)])
               for k, (n, (c, h, w)) in enumerate(RA_SPRITES.items())}
    hires = {f"{n}.shp": write_shp([blob_frame(h, w, k + i) for i in range(c)])
             for k, (n, (c, h, w)) in enumerate(INFANTRY.items())}
    hires["mouse.shp"] = write_d2([blob_frame(24, 24, i, colour=60) for i in range(120)])
    pal = bytes(min(63, i // 2) for i in range(256) for _ in range(3))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "conquer.mix").write_bytes(ra_mix(conquer, encrypted=False))
    (folder / "hires.mix").write_bytes(ra_mix(hires))
    (folder / "local.mix").write_bytes(ra_mix({"temperat.pal": pal}))


def cells(path, mod):
    conv = ImageConverter(DeviceSettings())
    if not conv.open(str(path)):
        raise AssertionError(f"cannot open {path}")
    return {kc: od.all_bytes for kc, od in (conv.extract_overlays(mod) or {}).items()}


class BlowfishTest(unittest.TestCase):

    def test_the_published_test_vectors(self):
        """Eric Young's Blowfish vectors (key, plaintext -> ciphertext)."""
        for key, plain, want in ((b"\0" * 8, (0, 0), (0x4EF99745, 0x6198DD78)),
                                 (b"\xff" * 8, (0xFFFFFFFF, 0xFFFFFFFF), (0x51866FD5, 0xB85ECB8A))):
            bf = mix.Blowfish(key)
            self.assertEqual(bf._encrypt(*plain), want)
            self.assertEqual(bf._decrypt(*want), plain)


class RaMixTest(unittest.TestCase):

    FILES = {"a.shp": b"first", "temperat.pal": b"\1" * 768, "b.shp": b"x" * 37}

    def test_encrypted_and_plain_archives_round_trip(self):
        for encrypted in (True, False):
            m = mix.Mix(ra_mix(self.FILES, encrypted))
            for name, data in self.FILES.items():
                self.assertEqual(m.get(name), data, f"{name}, encrypted={encrypted}")
            self.assertIsNone(m.get("missing.shp"))

    def test_a_tiberian_dawn_archive_is_read_too(self):
        with tempfile.TemporaryDirectory() as d:
            from tests.services.game_assets_test import write_mix
            write_mix(Path(d, "t.mix"), self.FILES)
            self.assertEqual(mix.Mix(Path(d, "t.mix").read_bytes()).get("a.shp"), b"first")

    def test_a_key_that_does_not_decrypt_is_refused(self):
        source = next(bytes([b]) * mix.KEY_SOURCE for b in range(1, 256)
                      if self._raises(bytes([b]) * mix.KEY_SOURCE))
        with self.assertRaises(ValueError):
            mix.Mix(struct.pack("<I", mix.ENCRYPTED) + source + bytes(16))

    @staticmethod
    def _raises(source):
        try:
            mix.blowfish_key(source)
        except ValueError:
            return True
        return False

    def test_a_header_longer_than_the_file_is_refused(self):
        data = ra_mix(self.FILES)
        with self.assertRaises(ValueError):
            mix.Mix(data[:4 + mix.KEY_SOURCE + 4])
        # A count that claims more entries than the file holds.
        source = key_source()
        head = encrypt(mix.blowfish_key(source), struct.pack("<HI", 5000, 0) + b"\0\0")
        with self.assertRaises(ValueError):
            mix.Mix(struct.pack("<I", mix.ENCRYPTED) + source + head)


class OpenRaFoldersTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        for p in (mock.patch.object(Path, "home", return_value=self.home),
                  mock.patch.dict(os.environ, {"APPDATA": "", "XDG_CONFIG_HOME": ""}),
                  mock.patch.object(westwood_td, "_steam_libraries", return_value=[]),
                  mock.patch.dict(os.environ, {"PROGRAMFILES": "", "PROGRAMFILES(X86)": ""})):
            p.start()
            self.addCleanup(p.stop)

    def test_red_alert_is_found_in_the_content_folder(self):
        self.assertIsNone(westwood_ra.find(""))
        ra = self.home / ".config" / "openra" / "Content" / "ra" / "v2"
        make_ra_files(ra)
        self.assertEqual(westwood_ra.find("")["hires.mix"].parent, ra)

    def test_a_flatpak_install_and_an_unknown_mod_folder_are_searched(self):
        ca = self.home / ".var" / "app" / "net.openra.OpenRA" / "config" / "openra" / "Content" / "ca" / "v1"
        make_ra_files(ca)
        self.assertEqual(westwood_ra.find("")["conquer.mix"].parent, ca)

    def test_a_portable_install_beside_the_game_comes_first(self):
        make_ra_files(self.home / ".config" / "openra" / "Content" / "ra" / "v2")
        game = self.home / "OpenRA"
        make_ra_files(game / "Support" / "Content" / "ra" / "v2")
        self.assertEqual(westwood_ra.find("", hint=game)["local.mix"].parents[3], game / "Support")

    def test_tiberian_dawn_is_found_in_the_content_folder(self):
        self.assertIsNone(westwood_td.find(""))
        cnc = self.home / ".openra" / "Content" / "cnc"
        cnc.mkdir(parents=True)
        make_game_files(cnc, upper=False)
        self.assertEqual(westwood_td.find("")["conquer.mix"].parent, cnc)

    def test_the_support_folders_are_listed_once(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.home / ".config")}):
            dirs = openra.support_dirs()
        self.assertEqual(len(dirs), len(set(dirs)))


class OpenRaBuildTest(unittest.TestCase):
    """Both OpenRA overlays drawn from synthetic files: the keys the spec
    redraws change on every tier, in both files, and no other key does."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.ra, cls.td, cls.cache = root / "ra", root / "td", root / "cache"
        make_ra_files(cls.ra)
        cls.td.mkdir()
        make_game_files(cls.td)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _check(self, spec_path, app, settings):
        spec = build.load_spec(spec_path)
        stems = set(spec["game_assets"]["icons"])
        want = {}
        for b in build.bindings(spec):
            if Path(b["icon"]).stem in stems:
                want.setdefault(build.modifier(b.get("mods")), set()).add(KeyCode[f"KC_{str(b['key']).upper()}"].value)
        self.assertEqual(set(want), {Modifier.NO_MOD, Modifier.CTRL, Modifier.ALT, Modifier.SHIFT,
                                     Modifier.CTRL_SHIFT})
        for template in (f"{app}_template.mods.png", f"{app}_template.combo.mods.png"):
            out = build.build(template, spec_path, settings.get, self.cache)
            self.assertIsNotNone(out, template)
            for mod, keys in want.items():
                if (mod == Modifier.CTRL_SHIFT) != (".combo." in template):
                    continue
                shipped, patched = cells(OVERLAYS / template, mod), cells(out, mod)
                for kc in set(shipped) | set(patched):
                    changed = shipped.get(kc) != patched.get(kc)
                    self.assertEqual(changed, kc in keys, f"{template} {mod.name} 0x{kc:02x}")

    def test_red_alert_for_both_factions(self):
        for faction in ("allies", "soviets"):
            with self.subTest(faction):
                self._check(RA_SPEC, "openra_ra",
                            {"game_ra_data_dir": str(self.ra), "game_ra_faction": faction})

    def test_tiberian_dawn_for_both_factions(self):
        for faction in ("gdi", "nod"):
            with self.subTest(faction):
                self._check(TD_SPEC, "openra_cnc",
                            {"game_cnc_data_dir": str(self.td), "game_cnc_faction": faction})


class OpenRaSpecTest(unittest.TestCase):

    def test_every_recipe_replaces_a_bound_icon(self):
        for spec_path, variants in ((RA_SPEC, ("allies", "soviets")), (TD_SPEC, ("gdi", "nod"))):
            spec = build.load_spec(spec_path)
            stems = {Path(b["icon"]).stem for b in build.bindings(spec)}
            for variant in variants:
                got = build.recipes(spec, variant)
                self.assertEqual(set(got) - stems, set(), f"{spec_path.name} {variant}")
                for stem, recipe in got.items():
                    base = recipe.get("plus", recipe.get("of"))
                    if base is not None:
                        self.assertIn(base, got, f"{stem} marks nothing")

    def test_the_tiberian_dawn_spec_is_generated_from_the_current_files(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("gen_mods", SOURCES / "gen_mods.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        self.assertEqual(gen.render(), TD_SPEC.read_text(encoding="utf-8"),
                         "run overlay_sources/openra/gen_mods.py")

    def test_the_mapping_registers_both_overlays_and_the_nested_one(self):
        import yaml
        with open(build.RES / "overlay-mapping.poly.yaml", encoding="utf-8") as f:
            mapping = yaml.safe_load(f)
        with mock.patch.dict(game_assets._specs, clear=True):
            game_assets.register_mapping(mapping)
            for app, spec in (("openra_ra", RA_SPEC), ("openra_cnc", TD_SPEC)):
                for template in (f"{app}_template.mods.png", f"{app}_template.combo.mods.png"):
                    self.assertEqual(game_assets._specs.get(template), spec, template)


class MarkTest(unittest.TestCase):

    def test_each_mark_stays_inside_the_cell_and_clears_around_itself(self):
        full, empty = np.ones((40, 48), bool), np.zeros((40, 48), bool)
        for kind in ("ring", "box", "sight"):
            m = dither.with_mark(full, kind)
            self.assertEqual(m.shape, full.shape)
            self.assertTrue(m[0, 0], "the group outside the mark stays")
            alone = dither.with_mark(empty, kind)
            self.assertTrue(alone.any())
            self.assertFalse(alone[-1].any() or alone[:, -1].any(),
                             f"{kind}: the mark must be whole inside the cell")
            ys, xs = np.nonzero(alone)
            top, left = xs[ys == ys.min()], ys[xs == xs.min()]
            self.assertFalse(m[ys.min() - 2:ys.min(), top].any(), f"{kind}: no seam above the mark")
            self.assertFalse(m[left, xs.min() - 2:xs.min()].any(), f"{kind}: no seam left of the mark")
        with self.assertRaises(ValueError):
            dither.with_mark(full, "star")

    def test_a_copy_keeps_the_file_kind_the_converter_reads(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "x")
            f.write_bytes(b"x")
            combo = build.cache_name("a_template.combo.mods.png", [f], "allies", "r")
            plain = build.cache_name("a_template.mods.png", [f], "allies", "r")
        self.assertTrue(combo.endswith(".combo.mods.png"), combo)
        self.assertNotIn(".combo.", plain)
        self.assertTrue(plain.startswith("a_template.allies.") and plain.endswith(".mods.png"), plain)

    def test_binding_modifiers(self):
        self.assertEqual(build.modifier(None), Modifier.NO_MOD)
        self.assertEqual(build.modifier(["shift", "CTRL"]), Modifier.CTRL_SHIFT)
        self.assertEqual(build.modifier(["ALT"]), Modifier.ALT)
        self.assertIsNone(build.modifier(["GUI"]))


if __name__ == "__main__":
    unittest.main()
