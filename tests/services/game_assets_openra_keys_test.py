"""The player's OpenRA hotkeys (game_assets/openra_keys.py) and the OpenRA
overlays remapped to them. Synthetic settings.yaml files only, in the format
OpenRA's HotkeyManager writes (commit cd20761)."""
import os
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from polyhost.device.keys import KeyCode, Modifier
from polyhost.res.overlay_layout import resolve_key
from polyhost.services.game_assets import build
from polyhost.services.game_assets import openra_keys as keys
from tests.services.game_assets_ra_test import RA_SPEC, cells, make_ra_files

SOURCES = build.RES / "overlay_sources" / "openra"


def settings_yaml(hotkeys: dict) -> str:
    body = "".join(f"\t{k}: {v}\n" for k, v in hotkeys.items())
    return f"Player:\n\tName: Commander\nKeys:\n{body}Graphics:\n\tMode: Windowed\n"


class ParseTest(unittest.TestCase):

    def test_only_the_keys_section(self):
        text = ("Player:\n\tName: Commander\nKeys:\n\tAttackMove: B\n\tStop:\n"
                "\tControlGroupCreate01: NUMBER_1 Ctrl, Shift\n\tOdd: C\n\t\tDeep: D\n"
                "Server:\n\tAttackMove: Q\n")
        self.assertEqual(keys.parse(text), {"AttackMove": ["B"], "Stop": [],
                                            "ControlGroupCreate01": ["CTRL+SHIFT+1"], "Odd": ["C"]})

    def test_spaces_instead_of_tabs(self):
        self.assertEqual(keys.parse("Keys:\n    Sell: Z Alt\n"), {"Sell": ["ALT+Z"]})

    def test_keys_the_overlay_cannot_show_give_nothing(self):
        got = keys.parse(settings_yaml({"Sell": "KP_1", "ZoomIn": "RIGHTBRACKET Meta",
                                        "Repair": "c"}))
        self.assertEqual(got, {"Sell": [], "ZoomIn": [], "Repair": ["C"]})

    def test_every_keycode_name_has_a_keycap_cell(self):
        for name, ours in keys.KEYCODES.items():
            resolve_key(ours)                               # raises for a key with no cell
            self.assertTrue(keys.token(name), name)

    def test_a_huge_settings_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.yaml"
            p.write_text(settings_yaml({"Stop": "Q"}))
            with mock.patch.object(keys, "MAX_SETTINGS", 4), self.assertRaises(ValueError):
                keys.bindings(p)


class FindTest(unittest.TestCase):

    def test_the_first_support_folder_with_a_settings_file(self):
        with tempfile.TemporaryDirectory() as d:
            appdata, xdg = Path(d) / "appdata", Path(d) / "xdg"
            for folder in (appdata / "OpenRA", xdg / "openra"):
                folder.mkdir(parents=True)
            (xdg / "openra" / "settings.yaml").write_text("Keys:\n")
            env = {"APPDATA": str(appdata), "XDG_CONFIG_HOME": str(xdg), "HOME": d, "USERPROFILE": d}
            with mock.patch.dict(os.environ, env):
                self.assertEqual(keys.find(), xdg / "openra" / "settings.yaml")
                (appdata / "OpenRA" / "settings.yaml").write_text("Keys:\n")
                self.assertEqual(keys.find(), appdata / "OpenRA" / "settings.yaml")


class RemapTest(unittest.TestCase):
    """The Red Alert overlay remapped to a settings.yaml."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.ra = Path(cls.tmp.name) / "ra"
        make_ra_files(cls.ra)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def built(self, template, hotkeys):
        with tempfile.TemporaryDirectory() as d:
            path = None
            if hotkeys is not None:
                path = Path(d) / "settings.yaml"
                path.write_text(settings_yaml(hotkeys), encoding="utf-8")
            with mock.patch.object(keys, "find", return_value=path):
                out = build.build(template, RA_SPEC, {"game_ra_data_dir": str(self.ra),
                                                      "game_ra_faction": "allies"}.get, Path(d) / "c")
                return {m: cells(out, m) for m in Modifier}

    def changed(self, a, b):
        return {(m, KeyCode(k).name) for m in a for k in set(a[m]) | set(b[m]) if a[m].get(k) != b[m].get(k)}

    def test_moved_unbound_and_untouched_hotkeys(self):
        template = "openra_ra_template.mods.png"
        plain, moved = self.built(template, None), self.built(template, {
            "AttackMove": "G", "Sell": "", "ControlGroupJumpTo01": "NUMBER_1 Ctrl, Alt"})
        nm, alt = Modifier.NO_MOD, Modifier.ALT
        self.assertEqual(self.changed(plain, moved), {(nm, "KC_A"), (nm, "KC_G"), (nm, "KC_Z")},
                         "Ctrl+Alt is in the other file, so the jump keeps its key")
        self.assertEqual(moved[nm][KeyCode.KC_G.value], plain[nm][KeyCode.KC_A.value])
        self.assertEqual(moved[alt], plain[alt])

    def test_the_combo_file_follows_too(self):
        template = "openra_ra_template.combo.mods.png"
        plain = self.built(template, None)
        moved = self.built(template, {"ControlGroupAddTo01": "NUMBER_1 Alt, Shift"})
        cs, as_ = Modifier.CTRL_SHIFT, Modifier.ALT_SHIFT
        self.assertEqual(self.changed(plain, moved), {(cs, "KC_1"), (as_, "KC_1")})
        self.assertEqual(moved[as_][KeyCode.KC_1.value], plain[cs][KeyCode.KC_1.value])

    def test_a_changed_settings_file_is_a_new_copy(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.yaml"
            settings = {"game_ra_data_dir": str(self.ra), "game_ra_faction": "allies"}.get
            with mock.patch.object(keys, "find", return_value=path):
                path.write_text(settings_yaml({"AttackMove": "G"}))
                first = build.build("openra_ra_template.mods.png", RA_SPEC, settings, Path(d) / "c")
                path.write_text(settings_yaml({"AttackMove": "G", "Stop": "K", "Guard": "L"}))
                second = build.build("openra_ra_template.mods.png", RA_SPEC, settings, Path(d) / "c")
            self.assertNotEqual(first, second)

    def test_an_unreadable_settings_file_leaves_the_defaults(self):
        template = "openra_ra_template.mods.png"
        plain = self.built(template, None)
        with mock.patch.object(keys, "MAX_SETTINGS", 4), self.assertLogs("PolyHost", "WARNING"):
            got = self.built(template, {"AttackMove": "G"})
        self.assertEqual(got, plain)


class SpecTest(unittest.TestCase):

    def test_every_binding_names_its_hotkey_and_reads_openra(self):
        for name in ("openra_ra", "openra_cnc", "openra_d2k"):
            spec = build.load_spec(SOURCES / f"{name}.yaml")
            self.assertEqual(spec["game_assets"].get("bindings"), "openra", name)
            for b in build.bindings(spec):
                self.assertIn("command", b, f"{name} {b['key']}")

    def test_known_defaults(self):
        """A few defaults from OpenRA's mods/common/hotkeys and mods/<mod>/hotkeys.yaml
        (commit cd20761); the full comparison is in SOURCES.md."""
        want = {"openra_ra": {"AttackMove": "A", "ControlGroupAddTo10": "CTRL+SHIFT+0",
                              "MapBookmarkRestore04": "ALT+R", "ProductionTypeNaval": "I"},
                "openra_cnc": {"NextProductionTab": "PGDN", "OpenGeneralChat": "SHIFT+ENTER"},
                "openra_d2k": {"ProductionTypeMerchant": "O", "PowerDown": "X"}}
        for name, table in want.items():
            spec = build.load_spec(SOURCES / f"{name}.yaml")
            got = {b["command"]: build.key_token("+".join([*map(str, b.get("mods") or []), str(b["key"])]))
                   for b in build.bindings(spec)}
            for command, token in table.items():
                self.assertEqual(got[command], build.key_token(token), f"{name} {command}")


if __name__ == "__main__":
    unittest.main()
