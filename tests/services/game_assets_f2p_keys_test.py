"""The key-binding sources of the free-to-play game overlays (game_assets
tf2_keys, apex_keys, poe_keys, poe2_keys, the `keys` reader) and the shipped
overlays remapped to them.

Synthetic files in the formats of Team Fortress 2's config_default.cfg
(SteamDatabase/GameTracking-TF2), the Apex Legends settings.cfg files and the
Path of Exile config files players published on GitHub. The specs' defaults
were also compared with those files: TF2 39 of 39 keys, Apex 24 of 24 (one
file), Path of Exile 47 of 47 (majority of 26 files) and Path of Exile 2 42 of
42 (3 files). That run is not part of the suite."""
import os
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from polyhost.device.keys import KeyCode, Modifier
from polyhost.services.game_assets import apex_keys, build, key_files, poe2_keys, poe_keys, tf2_keys
from polyhost.services.game_assets.readers import READERS
from tests.services.game_assets_ra_test import cells

SOURCES = build.RES / "overlay_sources"
OVERLAYS = build.RES / "overlays"

TF2_STOCK = """unbindall
bind "1" "slot1"
bind "2" "slot2"
bind "q" "lastinv"
bind "r" "+reload"
bind "e" "voicemenu 0 0"
bind "t" "impulse 201"
bind "MOUSE1" "+attack"
bind "KP_END" "slot1"
"""


class SourceBindTest(unittest.TestCase):

    def test_tf2_lines(self):
        got = tf2_keys.parse("﻿" + TF2_STOCK + 'bind "SEMICOLON" "say"\nbind "\\" "say_team"\n'
                             'bind SPACE "+jump; +duck"\nbind "UPARROW" "+forward"\n// bind "z" "x"\n')
        self.assertEqual(got["slot1"], ["1"])                       # KP_END has no keycap cell
        self.assertEqual(got["voicemenu 0 0"], ["E"])
        self.assertEqual(got["impulse 201"], ["T"])
        self.assertEqual(got["say"], ["SEMICOLON"])
        self.assertEqual(got["say_team"], ["BACKSLASH"])
        self.assertEqual(got["+jump"], ["SPACE"])                   # each command of a ; list
        self.assertEqual(got["+duck"], ["SPACE"])
        self.assertEqual(got["+forward"], ["UP"])
        self.assertNotIn("+attack", got)                            # mouse only
        self.assertNotIn("x", got)

    def test_apex_lines(self):
        got = apex_keys.parse('bind_US_standard "q" "+offhand1" 0\n'
                              'bind_held_US_standard "q" "+strafe" 0\n'
                              'bind_US_standard "TAB" "toggle_inventory" 0\n'
                              'bind_US_standard "i" "toggle_inventory" 1\n'
                              'bind_US_standard "e" "+use; +use_long" 0\n'
                              'bind_US_standard "\\\\" "exec" 0\n'
                              'bind_US_standard "]" "+ping" 0 //mouse 6\n'
                              'bind_US_standard "LSHIFT" "+speed" 0\n'
                              'bind "z" "+offhand4"\n')
        self.assertEqual(got, {"+offhand1": ["Q"], "toggle_inventory": ["TAB", "I"], "+use": ["E"],
                               "+use_long": ["E"], "exec": ["BACKSLASH"], "+ping": ["RBRACKET"]})

    def test_every_source_key_has_a_keycap_cell(self):
        from polyhost.res.overlay_layout import resolve_key
        for name, ours in key_files.SOURCE_KEYS.items():
            resolve_key(ours)
            self.assertEqual(key_files.source_token(name.lower()), ours)

    def test_a_huge_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.cfg"
            p.write_text(TF2_STOCK, encoding="utf-8")
            with mock.patch.object(tf2_keys, "MAX_FILE", 4), self.assertRaises(ValueError):
                tf2_keys.bindings(p)
            self.assertIsNone(tf2_keys.bindings(None))


def poe_config(actions: dict, section="ACTION_KEYS", extra="") -> str:
    body = "".join(f"{k}={v}\n" for k, v in actions.items())
    return f"﻿[DISPLAY]\nfullscreen=true\n{extra}\n[{section}]\n{body}\n[UI]\nuse_bound_skill4=1\n"


class PoeParseTest(unittest.TestCase):

    def test_tokens(self):
        self.assertEqual(poe_keys.token("81"), "Q")
        self.assertEqual(poe_keys.token("81 2"), "CTRL+Q")
        self.assertEqual(poe_keys.token("49 1"), "SHIFT+1")
        self.assertEqual(poe_keys.token("112"), "F1")
        self.assertEqual(poe_keys.token("186"), "SEMICOLON")
        for unknown in ("0", "", "1", "4", "18", "81 3", "81 4", "x"):
            self.assertIsNone(poe_keys.token(unknown), unknown)

    def test_only_the_action_keys_section(self):
        got = poe_keys.parse(poe_config({"use_bound_skill4": "87", "use_bound_skill9": "69 2",
                                         "take_screenshot": "", "use_bound_skill1": "1"}))
        self.assertEqual(got, {"use_bound_skill4": ["W"], "use_bound_skill9": ["CTRL+E"],
                               "take_screenshot": [], "use_bound_skill1": []})

    def test_poe2_follows_the_input_mode(self):
        text = poe_config({"use_bound_skill5": "87"}) + "[WASD_ACTION_KEYS]\nuse_bound_skill5=69\n"
        self.assertEqual(poe2_keys.parse(text)["use_bound_skill5"], ["W"])
        wasd = text.replace("fullscreen=true", "fullscreen=true\n[GENERAL]\nuser_input_mode=wasd")
        self.assertEqual(poe2_keys.input_mode(wasd), "wasd")
        self.assertEqual(poe2_keys.parse(wasd)["use_bound_skill5"], ["E"])


class FindTest(unittest.TestCase):

    def test_tf2_in_a_steam_library(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d)
            cfg = lib / "steamapps" / "common" / "Team Fortress 2" / "tf" / "cfg" / "config.cfg"
            with mock.patch.object(key_files, "steam_libraries", return_value=[lib / "none", lib]):
                self.assertIsNone(tf2_keys.find())
                cfg.parent.mkdir(parents=True)
                cfg.write_text(TF2_STOCK, encoding="utf-8")
                self.assertEqual(tf2_keys.find(), cfg)

    def test_the_newest_of_several_installs(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.ini", Path(d) / "b.ini"
            for p, when in ((a, 2_000_000_000), (b, 1_000_000_000)):
                p.write_text("x", encoding="utf-8")
                os.utime(p, (when, when))
            self.assertEqual(key_files.newest([b, a, Path(d) / "none"]), a)

    def test_windows_user_folders(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            lib = home / "lib"
            pfx_user = lib / "steamapps" / "compatdata" / "238960" / "pfx" / "drive_c" / "users" / "steamuser"
            pfx_user.mkdir(parents=True)
            (pfx_user.parent / "Public").mkdir()
            with mock.patch.object(Path, "home", return_value=home), \
                 mock.patch.object(key_files, "steam_libraries", return_value=[lib]), \
                 mock.patch.dict(os.environ, {"USERPROFILE": "", "WINEPREFIX": ""}):
                homes = key_files.windows_homes(238960)
                paths = poe_keys.candidates()
            self.assertEqual(homes, [home, pfx_user])
            self.assertIn(pfx_user / "Documents" / "My Games" / "Path of Exile" / "production_Config.ini", paths)
            self.assertIn(home / "OneDrive" / "Documents" / "My Games" / "Path of Exile"
                          / "garena_tw_production_Config.ini", paths)
            self.assertIn(home / "Library" / "Application Support" / "Path of Exile" / "Preferences"
                          / "production_Config.ini", paths)

    def test_the_keys_reader_finds_no_art(self):
        from polyhost.services.game_assets.keys import reader
        self.assertEqual(READERS["keys"].settings, ())
        self.assertIsNone(reader.find("anything", "hint"))
        self.assertEqual(reader.searched(), [])


class RemapTest(unittest.TestCase):
    """The shipped overlay with the icons moved to the player's keys
    (build.keys_only through the `keys` reader)."""

    MODS = (Modifier.NO_MOD, Modifier.CTRL, Modifier.ALT, Modifier.SHIFT)

    def built(self, source, spec, template, text):
        with tempfile.TemporaryDirectory() as d:
            path = None
            if text is not None:
                path = Path(d) / "binds.cfg"
                path.write_text(text, encoding="utf-8")
            with mock.patch.object(source, "find", return_value=path):
                out = build.build(template, spec, {}.get, Path(d) / "c")
                return None if out is None else {m: cells(out, m) for m in self.MODS}

    def changed(self, a, b):
        return {(m, KeyCode(k).name) for m in a for k in set(a[m]) | set(b[m]) if a[m].get(k) != b[m].get(k)}

    def test_tf2_the_stock_file_moves_nothing_the_full_list_unbinds_the_rest(self):
        spec, template = SOURCES / "tf2" / "tf2.yaml", "tf2_template.mods.png"
        shipped = {m: cells(OVERLAYS / template, m) for m in self.MODS}
        # A config.cfg with every default bind of the spec, as the game writes it.
        names = {"MINUS": "-", "DOT": ".", "COMMA": ",", "GRAVE": "`"}
        stock = "unbindall\n" + "".join(
            f'bind "{names.get(str(b["key"]), str(b["key"]).lower())}" "{b["command"]}"\n'
            for b in build.bindings(build.load_spec(spec)))
        got = self.built(tf2_keys, spec, template, stock)
        self.assertEqual(self.changed(shipped, got), set())
        # A config.cfg that binds only a few keys: every other command is unbound.
        got = self.built(tf2_keys, spec, template, TF2_STOCK.replace('"q" "lastinv"', '"F3" "lastinv"'))
        nm = Modifier.NO_MOD
        self.assertEqual(got[nm][KeyCode.KC_F3.value], shipped[nm][KeyCode.KC_Q.value])
        self.assertNotIn(KeyCode.KC_Q.value, got[nm])
        self.assertNotIn(KeyCode.KC_TAB.value, got[nm], "+showscores has no line: unbound")
        self.assertEqual(got[nm][KeyCode.KC_1.value], shipped[nm][KeyCode.KC_1.value])
        self.assertEqual(got[nm][KeyCode.KC_ESCAPE.value], shipped[nm][KeyCode.KC_ESCAPE.value])

    def test_without_a_file_there_is_no_copy(self):
        self.assertIsNone(self.built(tf2_keys, SOURCES / "tf2" / "tf2.yaml", "tf2_template.mods.png", None))

    def test_apex_a_rebind_moves_one_icon_and_keeps_the_others(self):
        spec, template = SOURCES / "apex" / "apex.yaml", "apex_template.mods.png"
        shipped = {m: cells(OVERLAYS / template, m) for m in self.MODS}
        got = self.built(apex_keys, spec, template, 'bind_US_standard "f" "+offhand1" 0\n'
                                                     'bind_US_standard "ESCAPE" "+offhand4" 0\n')
        nm = Modifier.NO_MOD
        self.assertEqual(self.changed(shipped, got), {(nm, "KC_Q"), (nm, "KC_F"), (nm, "KC_Z")})
        self.assertEqual(got[nm][KeyCode.KC_F.value], shipped[nm][KeyCode.KC_Q.value])
        self.assertEqual(got[nm][KeyCode.KC_ESCAPE.value], shipped[nm][KeyCode.KC_ESCAPE.value],
                         "ESC keeps the program mark")

    def test_poe_ctrl_skills_move_and_missing_actions_keep_their_keys(self):
        spec, template = SOURCES / "poe" / "poe.yaml", "poe_template.mods.png"
        shipped = {m: cells(OVERLAYS / template, m) for m in self.MODS}
        got = self.built(poe_keys, spec, template, poe_config({"use_bound_skill9": "65 2",
                                                               "use_flask_in_slot5": "0"}))
        nm, ctrl = Modifier.NO_MOD, Modifier.CTRL
        self.assertEqual(self.changed(shipped, got), {(ctrl, "KC_Q"), (ctrl, "KC_A"), (nm, "KC_5")})
        self.assertEqual(got[ctrl][KeyCode.KC_A.value], shipped[ctrl][KeyCode.KC_Q.value])

    def test_poe2_wasd_mode_moves_the_skill_bar(self):
        spec, template = SOURCES / "poe" / "poe2.yaml", "poe2_template.mods.png"
        shipped = {m: cells(OVERLAYS / template, m) for m in self.MODS}
        text = ("[GENERAL]\nuser_input_mode=wasd\n" + poe_config({"use_bound_skill4": "81"})
                + "[WASD_ACTION_KEYS]\nuse_bound_skill5=69\nuse_bound_skill6=82\nuse_bound_skill7=84\n"
                  "use_bound_skill8=70\nmove_up=87\n")
        got = self.built(poe2_keys, spec, template, text)
        nm = Modifier.NO_MOD
        self.assertEqual(got[nm][KeyCode.KC_E.value], shipped[nm][KeyCode.KC_W.value])
        self.assertEqual(got[nm][KeyCode.KC_F.value], shipped[nm][KeyCode.KC_T.value])
        self.assertNotIn(KeyCode.KC_W.value, got[nm])

    def test_a_changed_file_is_a_new_copy(self):
        spec, template = SOURCES / "apex" / "apex.yaml", "apex_template.mods.png"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.cfg"
            with mock.patch.object(apex_keys, "find", return_value=path):
                path.write_text('bind_US_standard "f" "+offhand1" 0\n', encoding="utf-8")
                first = build.build(template, spec, {}.get, Path(d) / "c")
                path.write_text('bind_US_standard "h" "+offhand1" 0\n', encoding="utf-8")
                second = build.build(template, spec, {}.get, Path(d) / "c")
            self.assertNotEqual(first, second)

    def test_an_unreadable_file_leaves_the_defaults(self):
        spec, template = SOURCES / "poe" / "poe.yaml", "poe_template.mods.png"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "production_Config.ini"
            path.write_text(poe_config({"use_bound_skill4": "87"}), encoding="utf-8")
            with mock.patch.object(poe_keys, "find", return_value=path), \
                 mock.patch.object(poe_keys, "MAX_FILE", 4), \
                 self.assertLogs("PolyHost", "WARNING"):
                self.assertIsNone(build.build(template, spec, {}.get, Path(d) / "c"))


if __name__ == "__main__":
    unittest.main()
