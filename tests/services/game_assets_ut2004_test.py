"""The Unreal Tournament 2004 reader (game_assets/unreal2) and the UT2004
overlay drawn from it. Synthetic game files only.

Epic's files may not be committed, so the tests write small packages with
the encoder below: a name, import and export table, a texture with one mip,
and weapon classes whose defaults hold IconCoords and IconMaterial. The
reader was also run on the UT2004 3369 files (HudContent.utx, XWeapons.u,
Onslaught.u); that run is not part of the suite.
"""
import os
import struct
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

import numpy as np

from polyhost.device.keys import KeyCode, Modifier
from polyhost.services import game_assets
from polyhost.services.game_assets import build, dither
from polyhost.services.game_assets.readers import READERS, reader_defaults
from polyhost.services.game_assets.unreal2 import bindings as ut_bindings
from polyhost.services.game_assets.unreal2 import dxt
from polyhost.services.game_assets.unreal2 import reader as ut
from polyhost.services.game_assets.unreal2.package import Package, compact, encode_compact
from tests.services.game_assets_ra_test import cells

SPEC = build.RES / "overlay_sources" / "ut2004" / "ut2004.yaml"
OVERLAYS = build.RES / "overlays"
TEMPLATE = "ut2004_template.mods.png"

# The stock weapon classes of XWeapons.u that the spec draws, in key order 1..0.
WEAPONS = ("ShieldGun", "AssaultRifle", "BioRifle", "ShockRifle", "LinkGun", "Minigun",
           "FlakCannon", "RocketLauncher", "SniperRifle", "Redeemer")

# --------------------------------------------------------------------------- #
# encoder (test-only)
# --------------------------------------------------------------------------- #


class PackageWriter:
    """Builds a package: names are added as used, imports and exports in order."""

    def __init__(self):
        self.names, self.imports, self.exports = ["None"], [], []

    def name(self, n: str) -> int:
        if n not in self.names:
            self.names.append(n)
        return self.names.index(n)

    def ci(self, n: str) -> bytes:
        return encode_compact(self.name(n))

    def add_import(self, cls_pkg, cls, outer, name) -> int:
        self.imports.append((self.name(cls_pkg), self.name(cls), outer, self.name(name)))
        return -len(self.imports)

    def add_export(self, cls: int, outer: int, name: str, data: bytes) -> int:
        self.exports.append((cls, outer, self.name(name), data))
        return len(self.exports)

    # -- properties --
    def prop_int(self, name, v):
        return self.ci(name) + bytes([0x22]) + struct.pack("<i", v)

    def prop_byte(self, name, v):
        return self.ci(name) + bytes([0x01, v])

    def prop_object(self, name, ref):
        raw = encode_compact(ref)
        code = {1: 0x00, 2: 0x10, 4: 0x20}[len(raw)] if len(raw) in (1, 2, 4) else None
        if code is None:
            return self.ci(name) + bytes([0x55, len(raw)]) + raw
        return self.ci(name) + bytes([0x05 | code]) + raw

    def prop_box(self, name, x1, y1, x2, y2):
        inner = b"".join(self.prop_int(k, v) for k, v in zip(("X1", "Y1", "X2", "Y2"), (x1, y1, x2, y2)))
        inner += self.ci("None")
        return self.ci(name) + bytes([0x5A]) + self.ci("IntBox") + bytes([len(inner)]) + inner

    def end(self):
        return self.ci("None")

    def bytes(self) -> bytes:
        head_size = 36 + 16 + 4
        body = bytearray()
        offsets = []
        for _cls, _outer, _name, data in self.exports:
            offsets.append(head_size + len(body))
            body += data
        name_off = head_size + len(body)
        names = b"".join(encode_compact(len(n) + 1) + n.encode("latin-1") + b"\0" + struct.pack("<I", 0)
                         for n in self.names)
        imp_off = name_off + len(names)
        imps = b"".join(encode_compact(a) + encode_compact(b) + struct.pack("<i", c) + encode_compact(d)
                        for a, b, c, d in self.imports)
        exp_off = imp_off + len(imps)
        exps = b""
        for (cls, outer, name, data), off in zip(self.exports, offsets):
            exps += (encode_compact(cls) + encode_compact(0) + struct.pack("<i", outer)
                     + encode_compact(name) + struct.pack("<I", 0) + encode_compact(len(data)))
            if data:
                exps += encode_compact(off)
        head = struct.pack("<IHHIiiiiii", 0x9E2A83C1, 128, 29, 0, len(self.names), name_off,
                           len(self.exports), exp_off, len(self.imports), imp_off)
        return head + bytes(16) + struct.pack("<i", 0) + bytes(body) + names + imps + exps


def texture_package(rgba: np.ndarray, path=("Generic", "HUD")) -> bytes:
    """A .utx with one RGBA8 texture at Group.Name."""
    w = PackageWriter()
    core = w.add_import("Core", "Package", 0, "Engine")
    tex_cls = w.add_import("Core", "Class", core, "Texture")
    group = w.add_export(w.add_import("Core", "Class", 0, "Package"), 0, path[0], b"")
    h, wd = rgba.shape[:2]
    mip = rgba[:, :, [2, 1, 0, 3]].tobytes()
    data = w.prop_byte("Format", 5) + w.prop_int("USize", wd) + w.prop_int("VSize", h) + w.end()
    start = 0                                   # the skip offset is not checked by the reader
    data += encode_compact(1) + struct.pack("<i", start) + encode_compact(len(mip)) + mip
    data += struct.pack("<ii", wd, h) + bytes([wd.bit_length() - 1, h.bit_length() - 1])
    w.add_export(tex_cls, group, path[1], data)
    return w.bytes()


def weapons_package(boxes: dict, script=b"\x1b\x01\x02\x03") -> bytes:
    """A .u with one class per entry of `boxes` ({class: (x1, y1, x2, y2)}),
    each with a short fake script and then its defaults."""
    w = PackageWriter()
    hud = w.add_import("Core", "Package", 0, "HUDContent")
    gen = w.add_import("Core", "Package", hud, "Generic")
    mat = w.add_import("Engine", "Texture", gen, "HUD")
    for i, (cls, box) in enumerate(boxes.items()):
        data = script + w.prop_box("IconCoords", *box) + w.prop_object("IconMaterial", mat)
        data += w.prop_byte("InventoryGroup", (i + 1) % 10) + w.end()
        w.add_export(0, 0, cls, data)
    return w.bytes()


def hud_texture(n=10, cell=(64, 32)):
    """A 512x512 texture with `n` weapon pictures in a column: a lit bar with a
    darker band, a dim glow ring (alpha 0.3) round it. Returns (rgba, boxes)."""
    tex = np.zeros((512, 512, 4), np.uint8)
    boxes = {}
    for i in range(n):
        x0, y0 = 8 + (i % 2) * 200, 8 + (i // 2) * 48
        cw, ch = cell
        tex[y0:y0 + ch, x0:x0 + cw] = (200, 200, 200, 80)       # the glow
        bar = tex[y0 + 3:y0 + ch - 3, x0 + 3:x0 + cw - 3 - i]
        bar[:] = (220, 220, 220, 255)
        bar[::4] = (60, 60, 60, 255)
        boxes[WEAPONS[i] if i < len(WEAPONS) else f"W{i}"] = (x0, y0, x0 + cw, y0 + ch)
    return tex, boxes


def make_install(root: Path, boxes=None, tex=None, system="System", textures="Textures",
                 user_ini=None):
    if tex is None or boxes is None:
        tex, boxes = hud_texture()
    (root / system).mkdir(parents=True, exist_ok=True)
    (root / textures).mkdir(parents=True, exist_ok=True)
    (root / textures / "HudContent.utx").write_bytes(texture_package(tex))
    (root / system / "XWeapons.u").write_bytes(weapons_package(boxes))
    if user_ini is not None:
        (root / system / "User.ini").write_text(user_ini, encoding="latin-1")
    return boxes


def default_user_ini(overrides=None) -> str:
    """A User.ini with the spec's default bindings, in UT2004's key names,
    with `overrides` ({UT key name: command}) applied."""
    names = {v: k for k, v in ut_bindings.KEY_NAMES.items()}
    lines = {}
    for b in build.bindings(build.load_spec(SPEC)):
        if "command" in b:
            lines[names[str(b["key"]).upper()]] = b["command"]
    lines.update({k.lower(): v for k, v in (overrides or {}).items()})
    body = "\n".join(f"{k}={v}" for k, v in lines.items())
    return f"[DefaultPlayer]\nName=Player\n\n[Engine.Input]\nLeftMouse=Fire\n{body}\n\n[Engine.HUD]\nT=Talk\n"

# --------------------------------------------------------------------------- #
# the file formats
# --------------------------------------------------------------------------- #


class CompactIndexTest(unittest.TestCase):

    def test_round_trips(self):
        for v in (0, 1, 63, 64, 127, 128, 8191, 8192, 1 << 20, (1 << 27) + 5, -1, -64, -100000):
            raw = encode_compact(v)
            self.assertEqual(compact(raw + b"\xff", 0), (v, len(raw)), v)

    def test_known_encodings(self):
        """The Unreal Wiki's examples: 0x40 continues, 0x80 is the sign."""
        self.assertEqual(encode_compact(5), b"\x05")
        self.assertEqual(encode_compact(-5), b"\x85")
        self.assertEqual(encode_compact(64), b"\x40\x01")


class PackageTest(unittest.TestCase):

    def test_texture_and_class_defaults(self):
        tex, boxes = hud_texture(3)
        pkg = Package(texture_package(tex), "hud")
        fmt, w, h, data = pkg.texture("Generic.HUD")
        self.assertEqual((fmt, w, h), ("RGBA8", 512, 512))
        np.testing.assert_array_equal(dxt.decode(fmt, w, h, data), tex)
        self.assertEqual(pkg.texture("generic.hud")[1:3], (512, 512), "case is ignored")
        with self.assertRaises(KeyError):
            pkg.texture("Generic.Nope")

        weapons = Package(weapons_package(boxes), "weapons")
        for i, (cls, box) in enumerate(boxes.items()):
            self.assertEqual(weapons.class_default(cls, "IconCoords"),
                             dict(zip(("X1", "Y1", "X2", "Y2"), box)))
            self.assertEqual(weapons.class_default(cls, "IconMaterial"), "HUDContent.Generic.HUD")
            self.assertEqual(weapons.class_default(cls, "InventoryGroup"), (i + 1) % 10)
        self.assertIsNone(weapons.class_default("NoSuchClass", "IconCoords"))
        self.assertIsNone(weapons.class_default("ShieldGun", "NoSuchProperty"))

    def test_a_name_byte_in_the_script_is_not_taken_for_the_tag(self):
        """The script before the defaults may hold the IconCoords name index as
        a plain byte; the search goes on to the tag that reads whole."""
        w = PackageWriter()
        idx = w.name("IconCoords")
        _tex, boxes = hud_texture(1)
        # A byte-sized tag of an unread kind (0) that reads whole, then garbage.
        data = weapons_package(boxes, script=bytes([idx, 0x00, 0x09, 0x00, idx, 0x07, idx, 0xFF, 0x00]))
        pkg = Package(data, "weapons")
        self.assertEqual(pkg.class_default("ShieldGun", "IconCoords")["X1"], boxes["ShieldGun"][0])

    def test_damaged_packages_are_refused(self):
        good = texture_package(hud_texture(1)[0])
        for bad, why in ((b"", "empty"), (b"\0" * 64, "no tag"), (good[:60], "cut"),
                         (good[:8] + struct.pack("<ii", 5, 1 << 30) + good[16:], "names outside")):
            with self.subTest(why), self.assertRaises(ValueError):
                Package(bad, "bad")

    def test_open_refuses_a_huge_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "big.utx"
            p.write_bytes(b"x")
            with mock.patch("os.path.getsize", return_value=1 << 31), self.assertRaises(ValueError):
                Package.open(p)


class DxtTest(unittest.TestCase):

    def test_dxt1_colours_and_cut_out(self):
        red, blue = 0xF800, 0x001F
        four = struct.pack("<HHI", red, blue, 0b10_00_01_00)             # c0 > c1: four colours
        three = struct.pack("<HHI", blue, red, 0b10_00_11)               # c0 <= c1: index 3 is clear
        img = dxt.decode("DXT1", 8, 4, four + three)
        self.assertEqual(tuple(img[0, 0]), (255, 0, 0, 255))
        self.assertEqual(tuple(img[0, 1]), (0, 0, 255, 255))
        self.assertEqual(tuple(img[0, 3]), (170, 0, 85, 255), "2/3 c0 + 1/3 c1")
        self.assertEqual(tuple(img[0, 4]), (0, 0, 0, 0))
        self.assertEqual(tuple(img[0, 5]), (0, 0, 255, 255))
        self.assertEqual(tuple(img[0, 6]), (127, 0, 127, 255), "half way with three colours")

    def test_dxt3_and_dxt5_alpha(self):
        colour = struct.pack("<HHI", 0xFFFF, 0, 0)
        dxt3 = bytes([0x0F] + [0xFF] * 7) + colour
        img = dxt.decode("DXT3", 4, 4, dxt3)
        self.assertEqual((img[0, 0, 3], img[0, 1, 3], img[1, 0, 3]), (255, 0, 255))
        # a0 = 200, a1 = 100: index 0 is 200, 1 is 100, 2 is (6*200 + 100)/7.
        bits = 0 | (1 << 3) | (2 << 6)
        dxt5 = bytes([200, 100]) + bits.to_bytes(6, "little") + colour
        img = dxt.decode("DXT5", 4, 4, dxt5)
        self.assertEqual(list(img[0, :3, 3]), [200, 100, (6 * 200 + 100) // 7])
        self.assertEqual(tuple(img[0, 0, :3]), (255, 255, 255))

    def test_short_data_and_other_formats_are_refused(self):
        with self.assertRaises(ValueError):
            dxt.decode("DXT5", 8, 8, b"\0" * 16)
        with self.assertRaises(ValueError):
            dxt.decode("P8", 4, 4, b"\0" * 16)
        with self.assertRaises(ValueError):
            dxt.decode("RGBA8", 4, 4, b"\0" * 8)

# --------------------------------------------------------------------------- #
# the reader
# --------------------------------------------------------------------------- #


class FindTest(unittest.TestCase):

    def test_the_install_folder_or_its_system_folder_in_any_case(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "UT2004"
            make_install(root, system="SYSTEM", textures="textures")
            for folder in (root, root / "SYSTEM"):
                files = ut.find(str(folder))
                self.assertEqual(set(files), {"hudcontent.utx", "xweapons.u"}, folder)
            (root / "SYSTEM" / "Onslaught.u").write_bytes(b"")
            self.assertIn("onslaught.u", ut.find(str(root)))

    def test_from_the_running_game_s_folder(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "Games" / "UT2004"
            make_install(root)
            with mock.patch.object(ut, "install_candidates", return_value=[]):
                self.assertIsNotNone(ut.find("", hint=str(root / "System")))
                self.assertIsNone(ut.find("", hint=str(Path(d))))

    def test_without_the_hud_package_there_is_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            make_install(root)
            (root / "Textures" / "HudContent.utx").unlink()
            self.assertIsNone(ut.find(str(root)))

    def test_the_wine_prefix_and_c_drive_are_searched(self):
        with tempfile.TemporaryDirectory() as d:
            prefix = Path(d) / "pfx"
            (prefix / "drive_c" / "UT2004").mkdir(parents=True)
            with mock.patch.dict(os.environ, {"WINEPREFIX": str(prefix)}):
                self.assertIn(prefix / "drive_c" / "UT2004", ut.install_candidates())


class DrawTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.boxes = make_install(cls.root)
        cls.src = ut.open_source(ut.find(str(cls.root)))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_picture_is_the_class_s_box(self):
        x1, y1, x2, y2 = self.boxes["ShockRifle"]
        self.assertEqual(ut.picture(self.src, {"weapon": "ShockRifle"}).shape[:2], (y2 - y1, x2 - x1))

    def test_drawn_right_aligned_and_centred_in_height(self):
        m = ut.draw(self.src, {"weapon": "ShieldGun"}, (48, 40))
        self.assertEqual(m.shape, (40, 48))
        ys, xs = np.nonzero(m)
        self.assertEqual(xs.max(), 47)
        self.assertLessEqual(abs((39 - ys.max()) - ys.min()), 1)

    def test_the_glow_is_left_out_and_erode_thins_the_shape(self):
        """The alpha 0.3 glow is not part of the weapon; each eroded px takes
        a px off every side of the fitted picture."""
        widths = []
        for n in (0, 1, 2):
            ys, xs = np.nonzero(ut.draw(self.src, {"weapon": "ShieldGun", "erode": n}, (48, 40)))
            widths.append((xs.max() - xs.min() + 1, ys.max() - ys.min() + 1))
        np.testing.assert_array_equal(ut.draw(self.src, {"weapon": "ShieldGun"}, (48, 40)),
                                      ut.draw(self.src, {"weapon": "ShieldGun", "erode": 1}, (48, 40)),
                                      "1 px is the default")
        self.assertEqual(widths[0][0], 48)
        # The bar is 58 x 26 inside a 64 x 32 glow: fitted 48 wide, the bar is
        # 22 px high and the glow would be 24.
        self.assertEqual(widths[0][1], round(26 * 48 / 58))
        self.assertEqual([w for w, _ in widths], [48, 46, 44])
        self.assertEqual(widths[0][1] - widths[1][1], 2)

    def test_unknown_weapons_and_recipes_are_refused(self):
        with self.assertRaises(KeyError):
            ut.draw(self.src, {"weapon": "Translauncher"}, (48, 40))
        with self.assertRaises(KeyError):
            ut.draw(self.src, {"weapon": "ONSAVRiL", "package": "Onslaught.u"}, (48, 40))
        with self.assertRaises(ValueError):
            ut.draw(self.src, {"wireframe": 3}, (48, 40))

    def test_a_tiny_box_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            tex, boxes = hud_texture(1)
            boxes = {"Translauncher": (0, 0, 2, 2)}
            make_install(Path(d), boxes, tex)
            src = ut.open_source(ut.find(d))
            with self.assertRaises(ValueError):
                ut.draw(src, {"weapon": "Translauncher"}, (48, 40))


class ErodeTest(unittest.TestCase):

    def test_erode_0_draws_what_keycap_drew_before(self):
        """The new parameter leaves every existing render byte for byte."""
        rng = np.random.default_rng(3)
        img = rng.random((30, 50))
        cover = np.zeros((30, 50), bool)
        cover[4:26, 3:47] = True
        np.testing.assert_array_equal(dither.keycap(img, cover, (40, 40)),
                                      dither.keycap(img, cover, (40, 40), erode=0))

    def test_eroding_everything_is_refused(self):
        cover = np.zeros((10, 10), bool)
        cover[4:6, 2:8] = True
        with self.assertRaises(ValueError):
            dither.keycap(np.ones((10, 10)), cover, (10, 10), erode=3)

# --------------------------------------------------------------------------- #
# the overlay
# --------------------------------------------------------------------------- #


class BuildTest(unittest.TestCase):
    """The UT2004 overlay drawn from synthetic files: the ten weapon keys
    change and no other key does."""

    def test_the_weapon_keys_change_and_nothing_else(self):
        spec = build.load_spec(SPEC)
        stems = set(spec["game_assets"]["icons"])
        keys = {KeyCode[f"KC_{str(b['key']).upper()}"].value
                for b in build.bindings(spec) if Path(b["icon"]).stem in stems}
        self.assertEqual(len(keys), 10)
        with tempfile.TemporaryDirectory() as d:
            make_install(Path(d) / "ut")
            settings = {"game_ut2004_dir": str(Path(d) / "ut")}
            out = build.build(TEMPLATE, SPEC, settings.get, Path(d) / "cache")
            self.assertIsNotNone(out)
            shipped, patched = cells(OVERLAYS / TEMPLATE, Modifier.NO_MOD), cells(out, Modifier.NO_MOD)
            for kc in set(shipped) | set(patched):
                self.assertEqual(shipped.get(kc) != patched.get(kc), kc in keys, f"0x{kc:02x}")

    def test_a_missing_class_costs_only_its_key(self):
        with tempfile.TemporaryDirectory() as d:
            tex, boxes = hud_texture()
            del boxes["Redeemer"]
            make_install(Path(d) / "ut", boxes, tex)
            settings = {"game_ut2004_dir": str(Path(d) / "ut")}
            with self.assertLogs("PolyHost", "WARNING") as log:
                out = build.build(TEMPLATE, SPEC, settings.get, Path(d) / "cache")
            self.assertTrue(any("superweapon" in line for line in log.output))
            shipped, patched = cells(OVERLAYS / TEMPLATE, Modifier.NO_MOD), cells(out, Modifier.NO_MOD)
            self.assertEqual(shipped[KeyCode.KC_0.value], patched[KeyCode.KC_0.value])
            self.assertNotEqual(shipped[KeyCode.KC_1.value], patched[KeyCode.KC_1.value])

    def test_without_game_files_there_is_no_copy(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(ut, "install_candidates", return_value=[]):
                self.assertIsNone(build.build(TEMPLATE, SPEC, {"game_ut2004_dir": d}.get, Path(d)))


class BindingsTest(unittest.TestCase):

    def test_parse_reads_only_the_input_section(self):
        text = ("[DefaultPlayer]\nName=Space\n[Engine.Input]\nAliases[0]=(Command=\"Jump\",Alias=Jump)\n"
                "Space=Jump\nbackspace=Jump\nE=Use\nH=\nLeftMouse=Fire\nNumPad8=MoveForward\n"
                "Ctrl=Jump\n; Q=Talk\nTilde=ConsoleToggle\n4=SwitchWeapon  4\n"
                "[Engine.HUD]\nT=Talk\n")
        got = ut_bindings.parse(text)
        self.assertEqual(got, {"Jump": ["SPACE", "BSPC"], "Use": ["E"], "ConsoleToggle": ["GRAVE"],
                               "SwitchWeapon  4": ["4"]})

    def test_every_key_name_has_a_keycap_cell(self):
        from polyhost.res.overlay_layout import resolve_key
        for ut_name, name in ut_bindings.KEY_NAMES.items():
            self.assertNotEqual(resolve_key(name), KeyCode.KC_LEFT_CTRL, ut_name)


class RemapTest(unittest.TestCase):
    """The icons follow the player's User.ini."""

    def built(self, user_ini):
        with tempfile.TemporaryDirectory() as d:
            make_install(Path(d) / "ut", user_ini=user_ini)
            out = build.build(TEMPLATE, SPEC, {"game_ut2004_dir": str(Path(d) / "ut")}.get, Path(d) / "c")
            return cells(out, Modifier.NO_MOD)

    def test_the_default_bindings_move_nothing(self):
        self.assertEqual(self.built(default_user_ini()), self.built(None))

    def test_rebound_keys_take_the_icon_and_the_old_keys_are_cleared(self):
        plain = self.built(None)
        got = self.built(default_user_ini({"Q": "", "H": "SwitchWeapon 10", "Space": "Use",
                                           "T": "", "Y": "talk", "Escape": "Jump"}))
        kc = {k: KeyCode[f"KC_{k}"].value for k in ("Q", "H", "SPACE", "E", "T", "Y", "BACKSPACE",
                                                     "ESCAPE", "R")}
        blank = got.get(kc["Q"])
        self.assertEqual(got[kc["H"]], plain[kc["Q"]], "the Translocator moved to H")
        self.assertNotEqual(plain[kc["Q"]], blank, "and left Q")
        self.assertEqual(got[kc["SPACE"]], plain[kc["E"]], "Space shows Use")
        self.assertEqual(got[kc["BACKSPACE"]], plain[kc["BACKSPACE"]], "Jump stays on Backspace")
        self.assertEqual(got[kc["Y"]], plain[kc["T"]], "a command in another case still matches")
        self.assertEqual(got.get(kc["T"]), blank)
        self.assertEqual(got[kc["ESCAPE"]], plain[kc["ESCAPE"]], "ESC keeps the program mark")
        self.assertEqual(got[kc["R"]], plain[kc["R"]], "an untouched key is unchanged")

    def test_an_unreadable_user_ini_leaves_the_defaults(self):
        plain = self.built(None)
        with mock.patch.object(ut, "MAX_INI", 4), self.assertLogs("PolyHost", "WARNING"):
            got = self.built(default_user_ini({"Q": "", "H": "SwitchWeapon 10"}))
        self.assertEqual(got, plain)

    def test_a_reader_without_bindings_is_not_remapped(self):
        self.assertIsNone(build.player_bindings(object(), {}))


class SpecTest(unittest.TestCase):

    def test_every_binding_but_esc_names_its_command(self):
        for b in build.bindings(build.load_spec(SPEC)):
            self.assertIn("command", b, b["key"])


    def test_every_recipe_replaces_a_bound_weapon_key(self):
        spec = build.load_spec(SPEC)
        by_stem = {Path(b["icon"]).stem: b for b in build.bindings(spec)}
        got = build.recipes(spec, "")
        self.assertEqual(set(got) - set(by_stem), set())
        self.assertEqual([got[Path(by_stem[s]["icon"]).stem]["weapon"]
                          for s in sorted(got, key=lambda s: "1234567890".index(str(by_stem[s]["key"])))],
                         list(WEAPONS))
        for stem in got:
            self.assertEqual(by_stem[stem]["region"], [48, 40], stem)

    def test_the_mapping_registers_the_overlay(self):
        import yaml
        with open(build.RES / "overlay-mapping.poly.yaml", encoding="utf-8") as f:
            mapping = yaml.safe_load(f)
        with mock.patch.dict(game_assets._specs, clear=True):
            game_assets.register_mapping(mapping)
            self.assertEqual(game_assets._specs.get(TEMPLATE), SPEC)

    def test_the_reader_and_its_setting_are_registered(self):
        self.assertIn("ut2004", READERS)
        self.assertEqual(reader_defaults()["game_ut2004_dir"], "")
        self.assertIsNone(READERS["ut2004"].variant)


if __name__ == "__main__":
    unittest.main()
