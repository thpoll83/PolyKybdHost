"""The player's StarCraft II hotkeys (game_assets/sc2_keys.py) and the
StarCraft II overlay remapped to them, with or without a StarCraft install.
Synthetic profiles only, in the format of TheCoreLite's Defaults.ini and its
user profile (github.com/supercowz/TheCoreLite). The spec's defaults were
also compared with that Defaults.ini: all 90 commands matched. That run is
not part of the suite."""
import os
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from polyhost.device.keys import KeyCode, Modifier
from polyhost.res.overlay_layout import resolve_key
from polyhost.services.game_assets import build
from polyhost.services.game_assets import sc2_keys as keys
from polyhost.services.game_assets.starcraft import reader as sc
from tests.services.game_assets_ra_test import cells
from tests.services.game_assets_starcraft_test import make_game_files

SPEC = build.RES / "overlay_sources" / "starcraft2" / "starcraft2.yaml"
OVERLAYS = build.RES / "overlays"
PRIMARY = "starcraft2_template.mods.png"
COMBO = "starcraft2_template.combo.mods.png"


def profile(hotkeys: dict, commands: dict | None = None) -> str:
    body = "".join(f"{k}={v}\n" for k, v in hotkeys.items())
    cmds = "".join(f"{k}={v}\n" for k, v in (commands or {"Attack/Marine": "Q"}).items())
    return f"[Settings]\nAllowSetConflicts=1\n\n[Hotkeys]\n{body}\n[Commands]\n{cmds}"


def make_user_dir(root: Path, active: str, profiles: dict) -> Path:
    """A StarCraft II user folder: Variables.txt naming `active`, and
    {(account, name): text} profile files."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "Variables.txt").write_text(f"displaymode=1\nhotkeyprofile={active}\nsoundvolume=0.5\n",
                                        encoding="utf-8")
    for (account, name), text in profiles.items():
        p = root / "Accounts" / account / "Hotkeys" / f"{name}.SC2Hotkeys"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


class ParseTest(unittest.TestCase):

    def test_only_the_hotkeys_section(self):
        got = keys.parse(profile({"ControlGroupRecall1": "Q", "CameraSave0": "Shift+Control+F5",
                                  "ChatAll": ""}, {"ControlGroupRecall2": "W"}))
        self.assertEqual(got, {"ControlGroupRecall1": ["Q"], "CameraSave0": ["CTRL+SHIFT+F5"],
                               "ChatAll": []})

    def test_alternates_and_keys_with_no_cell(self):
        got = keys.parse("﻿[Hotkeys]\r\nPauseGame=Pause,NumPad5,MediaPause\r\n"
                         "QuickPing=Control+Alt+LeftMouseButton\r\nStatusAll=Alt\r\n"
                         "PTT=Grave,Grave\r\nIdleWorker=Alt+Shift+BracketOpen,F1\r\n")
        self.assertEqual(got, {"PauseGame": ["PAUSE"], "QuickPing": [], "StatusAll": [],
                               "PTT": ["GRAVE"], "IdleWorker": ["ALT+SHIFT+LBRACKET", "F1"]})

    def test_every_key_name_has_a_keycap_cell(self):
        for name, ours in keys.KEYS.items():
            resolve_key(ours)                      # raises for a key with no cell
            self.assertTrue(keys.token(name.title()), name)

    def test_a_huge_profile_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.SC2Hotkeys"
            p.write_text(profile({"PTT": "T"}), encoding="utf-8")
            with mock.patch.object(keys, "MAX_FILE", 4), self.assertRaises(ValueError):
                keys.bindings(p)


class FindTest(unittest.TestCase):

    def found(self, root, active, profiles):
        user = make_user_dir(Path(root) / "Documents" / "StarCraft II", active, profiles)
        with mock.patch.object(keys, "user_dirs", return_value=[Path(root) / "nothing", user]):
            return keys.find()

    def test_the_active_profile_of_the_newest_account(self):
        with tempfile.TemporaryDirectory() as d:
            user = make_user_dir(Path(d), "Mine", {("111", "Mine"): profile({}), ("222", "Mine"): profile({}),
                                                   ("222", "Other"): profile({})})
            hotkeys = user / "Accounts"
            for account, when in (("111", 2_000_000_000), ("222", 1_000_000_000)):
                os.utime(hotkeys / account / "Hotkeys" / "Mine.SC2Hotkeys", (when, when))
            with mock.patch.object(keys, "user_dirs", return_value=[user]):
                self.assertEqual(keys.find().parent.parent.name, "111")
                os.utime(hotkeys / "222" / "Hotkeys" / "Mine.SC2Hotkeys", (2_100_000_000, 2_100_000_000))
                self.assertEqual(keys.find().parent.parent.name, "222")

    def test_a_region_folder_and_any_case(self):
        with tempfile.TemporaryDirectory() as d:
            got = self.found(d, "mine", {("111/1-S2-1-42", "MINE"): profile({})})
            self.assertEqual(got.name, "MINE.SC2Hotkeys")

    def test_a_built_in_profile_has_no_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(self.found(d, "0_Default", {("111", "0_Default"): profile({})}))

    def test_a_missing_profile_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(self.found(d, "Gone", {}))

    def test_the_user_folders(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Games" / "starcraft-ii" / "drive_c" / "users" / "me" / "Documents" / "StarCraft II").mkdir(
                parents=True)
            with mock.patch.object(Path, "home", return_value=Path(d)), \
                 mock.patch.dict(os.environ, {"USERPROFILE": d, "WINEPREFIX": ""}):
                dirs = keys.user_dirs()
            self.assertEqual(dirs[0], Path(d) / "Documents" / "StarCraft II")
            self.assertIn(Path(d) / "Library" / "Application Support" / "Blizzard" / "StarCraft II", dirs)
            self.assertIn(Path(d) / "Games" / "starcraft-ii" / "drive_c" / "users" / "me" / "Documents"
                          / "StarCraft II", dirs)
            self.assertEqual(len(dirs), len(set(dirs)))


class RemapTest(unittest.TestCase):

    MODS = (Modifier.NO_MOD, Modifier.CTRL, Modifier.ALT, Modifier.SHIFT, Modifier.ALT_SHIFT,
            Modifier.CTRL_SHIFT, Modifier.CTRL_ALT)

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.sc = Path(cls.tmp.name) / "sc"
        make_game_files(cls.sc)
        cls.shipped = {t: {m: cells(OVERLAYS / t, m) for m in cls.MODS} for t in (PRIMARY, COMBO)}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def built(self, template, hotkeys, art=True):
        with tempfile.TemporaryDirectory() as d:
            path = None
            if hotkeys is not None:
                path = Path(d) / "Mine.SC2Hotkeys"
                path.write_text(profile(hotkeys), encoding="utf-8")
            settings = {"game_sc1_data_dir": str(self.sc if art else Path(d) / "none"),
                        "game_sc1_race": "terran"}.get
            with mock.patch.object(keys, "find", return_value=path), \
                 mock.patch.object(sc, "install_candidates", return_value=[]):
                out = build.build(template, SPEC, settings, Path(d) / "c")
                return None if out is None else {m: cells(out, m) for m in self.MODS}

    def changed(self, a, b):
        return {(m, KeyCode(k).name) for m in a for k in set(a[m]) | set(b[m]) if a[m].get(k) != b[m].get(k)}

    def test_without_starcraft_the_shipped_overlay_follows_the_profile(self):
        got = self.built(PRIMARY, {"IdleWorker": "F3", "PTT": "", "CameraSave0": "Control+F9"}, art=False)
        shipped = self.shipped[PRIMARY]
        nm, ctrl = Modifier.NO_MOD, Modifier.CTRL
        self.assertEqual(self.changed(shipped, got), {(nm, "KC_F1"), (nm, "KC_F3"), (nm, "KC_GRAVE"),
                                                      (ctrl, "KC_F5"), (ctrl, "KC_F9")})
        self.assertEqual(got[nm][KeyCode.KC_F3.value], shipped[nm][KeyCode.KC_F1.value])

    def test_without_starcraft_or_a_profile_there_is_no_copy(self):
        self.assertIsNone(self.built(PRIMARY, None, art=False))

    def test_a_profile_with_the_defaults_moves_nothing(self):
        got = self.built(COMBO, {"ControlGroupAppendAndSteal1": "Shift+Alt+1", "FPS": "Alt+Control+F"},
                         art=False)
        self.assertEqual(self.changed(self.shipped[COMBO], got), set())

    def test_with_starcraft_the_drawn_group_moves(self):
        plain = self.built(PRIMARY, None)
        moved = self.built(PRIMARY, {"ControlGroupRecall1": "Q", "ControlGroupRecall2": "Escape"})
        nm = Modifier.NO_MOD
        self.assertEqual(self.changed(plain, moved), {(nm, "KC_1"), (nm, "KC_2"), (nm, "KC_Q")})
        self.assertEqual(moved[nm][KeyCode.KC_Q.value], plain[nm][KeyCode.KC_1.value])
        self.assertEqual(moved[nm][KeyCode.KC_ESCAPE.value], plain[nm][KeyCode.KC_ESCAPE.value],
                         "ESC keeps the program mark")

    def test_a_changed_profile_is_a_new_copy(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "Mine.SC2Hotkeys"
            settings = {"game_sc1_data_dir": str(Path(d) / "none"), "game_sc1_race": "terran"}.get
            with mock.patch.object(keys, "find", return_value=path), \
                 mock.patch.object(sc, "install_candidates", return_value=[]):
                path.write_text(profile({"IdleWorker": "F3"}), encoding="utf-8")
                first = build.build(PRIMARY, SPEC, settings, Path(d) / "c")
                path.write_text(profile({"IdleWorker": "F3", "ArmySelect": "F4", "PTT": "T"}), encoding="utf-8")
                second = build.build(PRIMARY, SPEC, settings, Path(d) / "c")
            self.assertNotEqual(first, second)

    def test_an_edit_that_keeps_the_size_and_the_time_is_a_new_copy(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "Mine.SC2Hotkeys"
            settings = {"game_sc1_data_dir": str(Path(d) / "none"), "game_sc1_race": "terran"}.get
            with mock.patch.object(keys, "find", return_value=path), \
                 mock.patch.object(sc, "install_candidates", return_value=[]):
                path.write_text(profile({"IdleWorker": "F3"}), encoding="utf-8")
                os.utime(path, (1_700_000_000, 1_700_000_000))
                first = build.build(PRIMARY, SPEC, settings, Path(d) / "c")
                path.write_text(profile({"IdleWorker": "F4"}), encoding="utf-8")
                os.utime(path, (1_700_000_000, 1_700_000_000))
                second = build.build(PRIMARY, SPEC, settings, Path(d) / "c")
                nm = Modifier.NO_MOD
                self.assertNotEqual(first, second)
                self.assertEqual(cells(second, nm)[KeyCode.KC_F4.value],
                                 self.shipped[PRIMARY][nm][KeyCode.KC_F1.value])

    def test_the_hash_and_the_parse_use_one_read(self):
        """A save during the build cannot put one content's overlay under
        another content's key: the hash is of the bytes that were parsed."""
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "Mine.SC2Hotkeys"
            path.write_text(profile({"IdleWorker": "F3"}), encoding="utf-8")
            parse, seen = keys.bindings, []

            def saved_meanwhile(p, data=None):
                path.write_text(profile({"IdleWorker": "F4"}), encoding="utf-8")
                seen.append(data)
                return parse(p, data)
            spec = build.load_spec(SPEC)
            with mock.patch.object(keys, "find", return_value=path), \
                 mock.patch.object(keys, "bindings", side_effect=saved_meanwhile):
                player, _, _, digests = build.bindings_source(spec, None, {})
            self.assertEqual(player["IdleWorker"], ["F3"], "parsed from the bytes read before the save")
            self.assertEqual(digests, [hashlib.sha1(seen[0]).hexdigest()])

    def test_a_profile_saved_back_gets_its_own_copy(self):
        """A -> B -> A with the same size and second: each content has its own copy."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "Mine.SC2Hotkeys"
            settings = {"game_sc1_data_dir": str(Path(d) / "none"), "game_sc1_race": "terran"}.get
            outs = []
            with mock.patch.object(keys, "find", return_value=path), \
                 mock.patch.object(sc, "install_candidates", return_value=[]):
                for key in ("F3", "F4", "F3"):
                    path.write_text(profile({"IdleWorker": key}), encoding="utf-8")
                    os.utime(path, (1_700_000_000, 1_700_000_000))
                    outs.append(build.build(PRIMARY, SPEC, settings, Path(d) / "c"))
                nm = Modifier.NO_MOD
                self.assertEqual(outs[0], outs[2])
                self.assertNotEqual(outs[0], outs[1])
                self.assertEqual(cells(outs[2], nm)[KeyCode.KC_F3.value],
                                 self.shipped[PRIMARY][nm][KeyCode.KC_F1.value])

    def test_a_file_too_large_to_read_once_is_not_parsed(self):
        """The source never reads the file on its own: one too large for the
        snapshot is refused before the parse."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "Mine.SC2Hotkeys"
            path.write_text(profile({"IdleWorker": "F3"}), encoding="utf-8")
            spec = build.load_spec(SPEC)
            with mock.patch.object(keys, "find", return_value=path), \
                 mock.patch.object(build, "MAX_KEY_FILE", 4), \
                 mock.patch.object(keys, "bindings") as parse, self.assertLogs("PolyHost", "WARNING"):
                self.assertEqual(build.bindings_source(spec, None, {})[0], None)
            parse.assert_not_called()

    def test_an_unreadable_profile_leaves_the_defaults(self):
        with mock.patch.object(keys, "MAX_FILE", 4), self.assertLogs("PolyHost", "WARNING"):
            self.assertIsNone(self.built(PRIMARY, {"IdleWorker": "F3"}, art=False))


class SpecTest(unittest.TestCase):

    def test_the_spec_reads_sc2_and_names_its_hotkeys(self):
        spec = build.load_spec(SPEC)
        self.assertEqual(spec["game_assets"].get("bindings"), "sc2")
        unnamed = {str(b["key"]) for b in build.bindings(spec) if "command" not in b}
        self.assertEqual(unnamed, {"PGDN", "PGUP", "END", "HOME", "QUOTE", "PSCR", "ENTER"},
                         "keys TheCore's Defaults.ini does not list")

    def test_known_defaults(self):
        """A few defaults from TheCoreLite's Defaults.ini."""
        want = {"ControlGroupAppendAndSteal0": "ALT+SHIFT+0", "CameraSave3": "CTRL+F8",
                "TownCamera": "BSPC", "ChatIndividual": "CTRL+ALT+ENTER", "MenuSocial": "ALT+F11",
                "StatusAlly": "LBRACKET", "CameraTurnRight": "DELETE"}
        got = {b["command"]: build.key_token("+".join([*map(str, b.get("mods") or []), str(b["key"])]))
               for b in build.bindings(build.load_spec(SPEC)) if "command" in b}
        for command, token in want.items():
            self.assertEqual(got[command], build.key_token(token), command)


if __name__ == "__main__":
    unittest.main()
