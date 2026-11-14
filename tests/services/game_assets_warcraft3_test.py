"""The Warcraft III key-assignment reader (game_assets/warcraft3) and the
Warcraft III overlay it remaps. Synthetic game files only.

Blizzard's files may not be committed, so the tests write small MPQ archives
(the StarCraft tests' encoder) holding the three text files the reader reads,
with lines in the format of the German 1.22 files. The reader was also run on
the German 1.22 archives (war3.mpq, War3x.mpq, War3Patch.mpq); that run is not
part of the suite.
"""
import os
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from polyhost.device.keys import KeyCode, Modifier
from polyhost.services import game_assets
from polyhost.services.game_assets import build
from polyhost.services.game_assets.readers import READERS, reader_defaults
from polyhost.services.game_assets.warcraft3 import reader as wc3
from tests.services.game_assets_ra_test import cells
from tests.services.game_assets_starcraft_test import write_mpq

SPEC = build.RES / "overlay_sources" / "warcraft3" / "warcraft3.yaml"
OVERLAYS = build.RES / "overlays"
TEMPLATE = "warcraft3_template.mods.png"


def menu_fdf(keys: dict) -> str:
    """EscMenuMainPanel.fdf with one button per entry of `keys` ({frame: key})."""
    frames = "".join(f'''
        Frame "GLUETEXTBUTTON" "{name}" INHERITS WITHCHILDREN "EscMenuButtonTemplate" {{
            UseActiveContext,
            ControlShortcutKey "{key}",
            ButtonText "{name}Text",
            Frame "TEXT" "{name}Text" INHERITS "EscMenuButtonTextTemplate" {{
                Text "KEY_X",
            }}
        }}''' for name, key in keys.items())
    return f'Frame "FRAME" "EscMenuMainPanel" {{{frames}\n}}\n'


def strings_fdf(keys: dict) -> str:
    """GlobalStrings.fdf with one tooltip per entry of `keys` ({name: letter})."""
    body = "".join(f'    {name:<32}"Text (|Cfffed312ALT-{key}|R)",\n' for name, key in keys.items())
    return 'StringList {\n    FORMATION_TOGGLE                "ALT-Z is not a tooltip",\n' + body + "}\n"


def commands_txt(keys: dict, bom: bool = True) -> str:
    """CommandStrings.txt with one section per entry of `keys` ({section: Hotkey})."""
    body = "".join(f"[{name}]\nTip=|cffffcc00{name}|r\nHotkey={key}\n\n" for name, key in keys.items())
    return ("﻿" if bom else "") + body


GERMAN_MENU = {"SaveGameButton": "S", "LoadGameButton": "L", "OptionsButton": "O",
               "HelpButton": "H", "QuitButton": "B", "ExitButton": "P"}
GERMAN_TIPS = {"MINIMAPSIGNALTOOLTIP": "G", "MINIMAPTERRAINTOOLTIP": "K",
               "MINIMAPALLYCOLORTOOLTIP": "A", "MINIMAPCREEPCOLORTOOLTIP": "R", "FORMATION_TOOLTIP": "F"}
GERMAN_COMMANDS = {"CmdMove": "B", "CmdAttack": "A", "CmdStop": "S", "CmdHoldPos": "H",
                   "CmdPatrol": "P", "CmdCancel": "512", "CmdRally": "K"}


def make_install(root: Path, menu=None, tips=None, commands=None, patch=None, custom=None):
    """war3.mpq with the three text files (an argument of None leaves its file
    out), and War3Patch.mpq with `patch` ({name: text}) when given."""
    root.mkdir(parents=True, exist_ok=True)
    files = {}
    if menu is not None:
        files[wc3.MENU_FILE] = menu_fdf(menu)
    if tips is not None:
        files[wc3.STRINGS_FILE] = strings_fdf(tips)
    if commands is not None:
        files[wc3.COMMANDS_FILE] = commands_txt(commands)
    (root / "War3.mpq").write_bytes(write_mpq(
        {n: (t.encode("utf-8"), "zlib", set()) for n, t in files.items()}, hash_size=16))
    if patch:
        (root / "War3Patch.mpq").write_bytes(write_mpq(
            {n: (t.encode("utf-8"), "stored", set()) for n, t in patch.items()}, hash_size=16))
    if custom is not None:
        (root / "CustomKeys.txt").write_text(custom, encoding="utf-8")


def german(root: Path, **kw):
    make_install(root, GERMAN_MENU, GERMAN_TIPS, GERMAN_COMMANDS, **kw)

# --------------------------------------------------------------------------- #
# the parsers
# --------------------------------------------------------------------------- #


class ParseTest(unittest.TestCase):

    def test_menu_keys_take_each_button_s_own_shortcut(self):
        got = wc3.menu_keys(menu_fdf(GERMAN_MENU))
        self.assertEqual(got, {"SaveGameButton": "ALT+S", "LoadGameButton": "ALT+L",
                               "OptionsButton": "ALT+O", "HelpButton": "ALT+H", "QuitButton": "ALT+B"})

    def test_tooltip_keys_read_the_alt_key_in_the_text(self):
        got = wc3.tooltip_keys(strings_fdf(GERMAN_TIPS))
        self.assertEqual(got["MINIMAPTERRAINTOOLTIP"], "ALT+K")
        self.assertEqual(got["FORMATION_TOOLTIP"], "ALT+F")
        self.assertNotIn("FORMATION_TOGGLE", got)

    def test_command_keys(self):
        text = commands_txt({"CmdMove": "b", "CmdCancel": "512", "CmdOdd": "120"})
        text += "[CmdAttack]\nHotkey=A,Q\nHotkey=Z\n[AHbz]\nHotkey=Z\n"
        self.assertEqual(wc3.command_keys(text), {"CmdMove": "B", "CmdCancel": "ESCAPE", "CmdAttack": "A"})


class FindTest(unittest.TestCase):

    def test_the_install_folder_in_any_case(self):
        with tempfile.TemporaryDirectory() as d:
            german(Path(d), patch={wc3.MENU_FILE: menu_fdf({"QuitButton": "Q"})}, custom="")
            (Path(d) / "War3.mpq").rename(Path(d) / "WAR3.MPQ")
            self.assertEqual(set(wc3.find(d)), {"war3.mpq", "war3patch.mpq", "customkeys.txt"})

    def test_from_the_running_game_s_folder(self):
        with tempfile.TemporaryDirectory() as d:
            german(Path(d) / "Warcraft III")
            with mock.patch.object(wc3, "install_candidates", return_value=[]):
                self.assertIsNotNone(wc3.find("", hint=str(Path(d) / "Warcraft III")))
                self.assertIsNone(wc3.find("", hint=d))

    def test_a_reforged_install_is_logged_once(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".build.info").write_text("")
            with self.assertLogs("PolyHost", "INFO") as log:
                self.assertIsNone(wc3.find(d))
                self.assertIsNone(wc3.find(d))
            self.assertEqual(sum("CASC" in line for line in log.output), 1)

    def test_the_wine_prefix_is_searched(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "drive_c" / "Program Files (x86)" / "Warcraft III"
            target.mkdir(parents=True)
            with mock.patch.dict(os.environ, {"WINEPREFIX": d}):
                self.assertIn(target, wc3.install_candidates())


class BindingsTest(unittest.TestCase):

    def test_all_three_files(self):
        with tempfile.TemporaryDirectory() as d:
            german(Path(d))
            got = wc3.bindings(wc3.find(d))
        self.assertEqual(got["QuitButton"], ["ALT+B"])
        self.assertEqual(got["MINIMAPSIGNALTOOLTIP"], ["ALT+G"])
        self.assertEqual(got["CmdMove"], ["B"])
        self.assertEqual(got["CmdCancel"], ["ESCAPE"])

    def test_the_patch_archive_and_customkeys_take_priority(self):
        with tempfile.TemporaryDirectory() as d:
            german(Path(d), patch={wc3.MENU_FILE: menu_fdf({"QuitButton": "Q"})},
                   custom="[CmdMove]\nHotkey=M\n")
            got = wc3.bindings(wc3.find(d))
        self.assertEqual(got["QuitButton"], ["ALT+Q"])
        self.assertEqual(got["CmdMove"], ["M"])
        self.assertEqual(got["CmdStop"], ["S"], "a section CustomKeys.txt leaves out keeps the game's key")

    def test_an_archive_without_the_files_gives_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            make_install(Path(d))
            self.assertIsNone(wc3.bindings(wc3.find(d)))

    def test_a_huge_customkeys_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            german(Path(d), custom="[CmdMove]\nHotkey=M\n")
            with mock.patch.object(wc3, "MAX_TEXT", 4), self.assertRaises(ValueError):
                wc3.bindings(wc3.find(d))

    def test_no_pictures(self):
        with self.assertRaises(ValueError):
            wc3.draw(None, {}, (40, 40))

# --------------------------------------------------------------------------- #
# the overlay
# --------------------------------------------------------------------------- #


def kc(name):
    return KeyCode[f"KC_{name}"].value


class BuildTest(unittest.TestCase):
    """The shipped overlay remapped to the German keys."""

    def built(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            make_install(Path(d) / "wc3", **kw)
            out = build.build(TEMPLATE, SPEC, {"game_wc3_dir": str(Path(d) / "wc3")}.get, Path(d) / "c")
            self.assertIsNotNone(out)
            return {m: cells(out, m) for m in (Modifier.NO_MOD, Modifier.CTRL, Modifier.ALT, Modifier.SHIFT)}

    @classmethod
    def setUpClass(cls):
        cls.shipped = {m: cells(OVERLAYS / TEMPLATE, m)
                       for m in (Modifier.NO_MOD, Modifier.CTRL, Modifier.ALT, Modifier.SHIFT)}

    def changed(self, got):
        return {(m, k) for m in got for k in set(got[m]) | set(self.shipped[m])
                if got[m].get(k) != self.shipped[m].get(k)}

    def test_german_keys_move_move_and_quit(self):
        got = self.built(menu=GERMAN_MENU, tips=GERMAN_TIPS, commands=GERMAN_COMMANDS)
        plain, alt = Modifier.NO_MOD, Modifier.ALT
        self.assertEqual(self.changed(got), {(plain, kc("M")), (plain, kc("B")),
                                             (alt, kc("Q")), (alt, kc("B"))})
        self.assertEqual(got[plain][kc("B")], self.shipped[plain][kc("M")])
        self.assertEqual(got[alt][kc("B")], self.shipped[alt][kc("Q")])

    def test_english_keys_move_nothing(self):
        got = self.built(menu=dict(GERMAN_MENU, QuitButton="Q"), tips=GERMAN_TIPS,
                         commands=dict(GERMAN_COMMANDS, CmdMove="M"))
        self.assertEqual(self.changed(got), set())

    def test_a_missing_file_leaves_its_keys_alone(self):
        """The game's files are not a full list: a command the reader did not
        find keeps its default key (BINDINGS_COMPLETE is False)."""
        got = self.built(menu=GERMAN_MENU)
        self.assertEqual(self.changed(got), {(Modifier.ALT, kc("Q")), (Modifier.ALT, kc("B"))})

    def test_customkeys_follows_the_player(self):
        got = self.built(menu=dict(GERMAN_MENU, QuitButton="Q"), tips=GERMAN_TIPS,
                         commands=dict(GERMAN_COMMANDS, CmdMove="M"), custom="[CmdPatrol]\nHotkey=Y\n")
        plain = Modifier.NO_MOD
        self.assertEqual(self.changed(got), {(plain, kc("P")), (plain, kc("Y"))})
        self.assertEqual(got[plain][kc("Y")], self.shipped[plain][kc("P")])


class RemapTiersTest(unittest.TestCase):

    def test_a_key_in_a_tier_the_file_does_not_hold_is_left_alone(self):
        import numpy as np

        from polyhost.res.overlay_layout import PRIMARY_CH, SLOT_H, SLOT_W
        spec = {"bindings": [{"key": "Q", "mods": ["ALT"], "command": "Quit", "icon": "q.png"}]}
        arr = np.zeros((10 * SLOT_H, 12 * SLOT_W, 4), np.uint8)
        tiers = PRIMARY_CH
        self.assertEqual(build.remap(arr, spec, tiers, {"Quit": ["CTRL+SHIFT+Q"]}), 0)
        self.assertEqual(build.remap(arr, spec, tiers, {"Quit": ["ALT+B"]}), 1)

    def test_key_tokens(self):
        self.assertEqual(build.key_token("ALT+B"), (KeyCode.KC_B, Modifier.ALT))
        self.assertEqual(build.key_token("ctrl + shift + f1"), (KeyCode.KC_F1, Modifier.CTRL_SHIFT))
        with self.assertRaises(ValueError):
            build.key_token("GUI+B")


class SpecTest(unittest.TestCase):

    def test_every_command_is_one_the_reader_reads(self):
        known = set(wc3.MENU_BUTTONS) | set(wc3.TOOLTIPS)
        for b in build.bindings(build.load_spec(SPEC)):
            if "command" in b:
                self.assertTrue(b["command"] in known or b["command"].startswith("Cmd"), b["command"])

    def test_the_mapping_registers_the_overlay(self):
        import yaml
        with open(build.RES / "overlay-mapping.poly.yaml", encoding="utf-8") as f:
            mapping = yaml.safe_load(f)
        with mock.patch.dict(game_assets._specs, clear=True):
            game_assets.register_mapping(mapping)
            self.assertEqual(game_assets._specs.get(TEMPLATE), SPEC)

    def test_the_reader_and_its_setting_are_registered(self):
        self.assertIn("warcraft3", READERS)
        self.assertEqual(reader_defaults()["game_wc3_dir"], "")


if __name__ == "__main__":
    unittest.main()
