"""The Command & Conquer Generals key-assignment reader (game_assets/generals)
and the Generals overlay it remaps. Synthetic game files only.

EA's archives may not be committed, so the tests write small BIG archives and
a csf file holding the files the reader reads, with lines in the format of
the English files of the Steam release of Zero Hour (EnglishZH.big,
INIZH.big). The reader was also run on those two archives: the stock files
move no icon, and a loose Data/English/CommandMap.ini with STOP on K moves
the stop icon to K. That run is not part of the suite.
"""
import struct
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from polyhost.device.keys import KeyCode, Modifier
from polyhost.services import game_assets
from polyhost.services.game_assets import build
from polyhost.services.game_assets.generals import big, strings
from polyhost.services.game_assets.generals import reader as gen
from polyhost.services.game_assets.readers import READERS, reader_defaults
from tests.services.game_assets_ra_test import cells

SPEC = build.RES / "overlay_sources" / "generals" / "generals.yaml"
OVERLAYS = build.RES / "overlays"
TEMPLATE = "generals_template.mods.png"
MODS = (Modifier.NO_MOD, Modifier.CTRL, Modifier.ALT, Modifier.SHIFT)


def write_big(files: dict) -> bytes:
    """A BIGF archive holding `files` ({path: bytes})."""
    names = [n.encode("latin-1") + b"\0" for n in files]
    first = 16 + sum(8 + len(n) for n in names)
    index, data, offset = b"", b"", first
    for name, body in zip(names, files.values()):
        index += struct.pack(">II", offset, len(body)) + name
        data += body
        offset += len(body)
    total = first + len(data)
    return b"BIGF" + struct.pack("<I", total) + struct.pack(">II", len(files), first) + index + data


def write_csf(labels: dict) -> bytes:
    """A csf file with one string per label ({label: text})."""
    body = b""
    for label, text in labels.items():
        raw = bytes(~b & 0xFF for b in text.encode("utf-16-le"))
        body += b" LBL" + struct.pack("<II", 1, len(label)) + label.encode("latin-1")
        body += b" RTS" + struct.pack("<I", len(text)) + raw
    return b" FSC" + struct.pack("<IIIII", 3, len(labels), len(labels), 0, 0) + body


def command_map(keys: dict, crlf: bool = True) -> bytes:
    """CommandMap.ini with one block per entry ({command: (key, modifiers)})."""
    nl = "\r\n" if crlf else "\n"
    out = [";FILE: CommandMap.ini (DEFAULT)"]
    for command, (key, mods) in keys.items():
        out += [f"CommandMap {command}", f"  Key = {key}", "  Transition = DOWN",
                f"  Modifiers = {mods}", "  UseableIn = GAME", "End", ""]
    return nl.join(out).encode("latin-1")


ENGLISH = {"STOP": ("KEY_S", "NONE"), "SELECT_ALL": ("KEY_Q", "NONE"), "SCATTER": ("KEY_X", "NONE"),
           "SELECT_TEAM1": ("KEY_1", "NONE"), "CREATE_TEAM1": ("KEY_1", "CTRL"),
           "SAVE_VIEW1": ("KEY_F1", "CTRL"), "OPTIONS": ("KEY_ESC", "NONE")}
CARD = {"CONTROLBAR:AttackMove": "&Attack Move", "CONTROLBAR:Guard": "&Guard",
        "GUI:SelectAll": "Select All"}


def make_install(folder: Path, language="English", keys=None, card=None, ini=b"", zh=True) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    lang = {f"Data\\{language}\\CommandMap.ini": command_map(ENGLISH if keys is None else keys),
            f"Data\\{language}\\generals.csf": write_csf(CARD if card is None else card)}
    suffix = "ZH" if zh else ""
    (folder / f"{language}{suffix}.big").write_bytes(write_big(lang))
    (folder / f"INI{suffix}.big").write_bytes(write_big({"Data\\INI\\CommandMap.ini": ini}))
    (folder / "Game.dat").write_bytes(b"MZ")
    return folder


def kc(name):
    return KeyCode[f"KC_{name}"].value


class ArchiveTest(unittest.TestCase):

    def test_names_in_any_case_and_either_slash(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.big"
            p.write_bytes(write_big({"Data\\INI\\CommandMap.ini": b"x", "Data/English/a.txt": b"yz"}))
            a = big.Archive.open(p)
            self.assertEqual(a.get("data/ini/commandmap.ini"), b"x")
            self.assertEqual(a.get("DATA\\ENGLISH\\A.TXT"), b"yz")
            self.assertIsNone(a.get("Data\\INI\\Other.ini"))
            with self.assertRaises(ValueError):
                a.get("Data\\English\\a.txt", limit=1)

    def test_not_an_archive(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.big"
            p.write_bytes(b"MZ" + bytes(40))
            with self.assertRaises(ValueError):
                big.Archive.open(p)
            p.write_bytes(b"BIGF" + struct.pack("<I", 0) + struct.pack(">II", 10**7, 16))
            with self.assertRaises(ValueError):
                big.Archive.open(p)


class TextTest(unittest.TestCase):

    def test_csf_strings_and_the_hotkey_letter(self):
        text = strings.csf(write_csf(CARD))
        self.assertEqual(text["CONTROLBAR:AttackMove"], "&Attack Move")
        self.assertEqual(strings.hotkey(text["CONTROLBAR:Guard"]), "G")
        self.assertIsNone(strings.hotkey(text["GUI:SelectAll"]))
        self.assertIsNone(strings.hotkey("Trailing &"))
        with self.assertRaises(ValueError):
            strings.csf(b"not a csf file at all....")

    def test_a_str_file(self):
        text = strings.str_file('CONTROLBAR:Guard\n"G&uard"\nEND\n// note\nCONTROLBAR:Stop\n"&Halt"\nEND\n')
        self.assertEqual(text, {"CONTROLBAR:Guard": "G&uard", "CONTROLBAR:Stop": "&Halt"})


class ParseTest(unittest.TestCase):

    def test_blocks_comments_and_case(self):
        text = (";CommandMap STOP\n;  Key = KEY_Z\nCommandMap stop\n  Key = KEY_S ; the stop key\n"
                "  Modifiers = NONE\nEND\nCommandMap SELECT_ALL\n  Key = KEY_Q\nEnd\n")
        self.assertEqual(gen.command_map(text), {"STOP": {"key": "KEY_S", "modifiers": "NONE"},
                                                 "SELECT_ALL": {"key": "KEY_Q"}})

    def test_tokens(self):
        self.assertEqual(gen.token({"key": "KEY_1", "modifiers": "SHIFT_CTRL"}), "CTRL+SHIFT+1")
        self.assertEqual(gen.token({"key": "KEY_TICK"}), "GRAVE")
        self.assertEqual(gen.token({"key": "KEY_DEL", "modifiers": "SHIFT_ALT_CTRL"}), "ALT+CTRL+SHIFT+DELETE")
        for fields in ({"key": "KEY_NONE"}, {"key": "KEY_KP5"}, {"key": "KEY_S", "modifiers": "META"}, {}):
            self.assertIsNone(gen.token(fields), fields)

    def test_every_key_name_has_a_keycap_cell(self):
        from polyhost.res.overlay_layout import resolve_key
        for ours in gen.KEYS.values():
            resolve_key(ours)                    # raises for a key with no cell


class FindTest(unittest.TestCase):

    def test_the_language_archive_names_the_language(self):
        with tempfile.TemporaryDirectory() as d:
            make_install(Path(d), "German")
            files = gen.find(d)
            self.assertEqual(files["lang.big"].name, "GermanZH.big")
            self.assertEqual(files["ini.big"].name, "INIZH.big")

    def test_no_language_archive_is_no_install(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "W3DZH.big").write_bytes(write_big({}))
            self.assertIsNone(gen.find(d))

    def test_the_registry_language_picks_among_several(self):
        with tempfile.TemporaryDirectory() as d:
            make_install(Path(d), "German")
            make_install(Path(d), "English")
            self.assertEqual(gen.data_files(Path(d))["lang.big"].name, "EnglishZH.big")
            self.assertEqual(gen.data_files(Path(d), "german")["lang.big"].name, "GermanZH.big")

    def test_loose_files_in_any_case(self):
        with tempfile.TemporaryDirectory() as d:
            make_install(Path(d))
            (Path(d) / "data" / "english").mkdir(parents=True)
            (Path(d) / "data" / "english" / "commandmap.ini").write_bytes(b"")
            (Path(d) / "data" / "Generals.str").write_bytes(b"")
            files = gen.find(d)
            self.assertIn("lang/commandmap.ini", files)
            self.assertIn("generals.str", files)
            self.assertNotIn("ini/commandmap.ini", files)

    def test_from_the_running_game_s_folder_and_steam(self):
        with tempfile.TemporaryDirectory() as d:
            game = make_install(Path(d) / "steamapps" / "common" / "Command & Conquer Generals - Zero Hour")
            with mock.patch.object(gen, "_steam_libraries", return_value=[]):
                self.assertEqual(gen.find("", str(game))["lang.big"].parent, game)
            with mock.patch.object(gen, "_steam_libraries", return_value=[Path(d)]):
                self.assertEqual(gen.find("")["lang.big"].parent, game)

    def test_zero_hour_is_preferred_to_generals(self):
        with tempfile.TemporaryDirectory() as d:
            make_install(Path(d) / "Command and Conquer Generals", zh=False)
            zh = make_install(Path(d) / "Command and Conquer Generals Zero Hour")
            with mock.patch.object(gen, "_steam_libraries", return_value=[]), \
                 mock.patch.dict("os.environ", {"PROGRAMFILES": d, "PROGRAMFILES(X86)": "", "WINEPREFIX": d}):
                self.assertEqual(gen.find("")["lang.big"].parent, zh)


class BindingsTest(unittest.TestCase):

    def bindings(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            make_install(Path(d), **{k: v for k, v in kw.items() if k != "loose"})
            for parts, body in (kw.get("loose") or {}).items():
                p = Path(d).joinpath(*parts)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(body)
            return gen.bindings(gen.find(d))

    def test_command_map_and_command_card(self):
        got = self.bindings()
        self.assertEqual(got["STOP"], ["S"])
        self.assertEqual(got["CREATE_TEAM1"], ["CTRL+1"])
        self.assertEqual(got["CONTROLBAR:AttackMove"], ["A"])
        self.assertNotIn("GUI:SelectAll", got)

    def test_the_ini_file_replaces_only_the_fields_it_sets(self):
        got = self.bindings(ini=b"CommandMap CREATE_TEAM1\r\n  Key = KEY_2\r\nEnd\r\n"
                                b"CommandMap STOP\r\n  Key = KEY_NONE\r\nEnd\r\n")
        self.assertEqual(got["CREATE_TEAM1"], ["CTRL+2"], "Modifiers stays from the language file")
        self.assertEqual(got["STOP"], [])

    def test_loose_files_replace_the_archives(self):
        got = self.bindings(loose={("Data", "English", "CommandMap.ini"): command_map({"STOP": ("KEY_K", "NONE")}),
                                   ("Data", "English", "Generals.csf"): write_csf({"CONTROLBAR:Guard": "&Wache"})})
        self.assertEqual(got["STOP"], ["K"])
        self.assertNotIn("SELECT_ALL", got, "the loose file replaces the whole archive copy")
        self.assertEqual(got["CONTROLBAR:Guard"], ["W"])
        self.assertNotIn("CONTROLBAR:AttackMove", got)

    def test_a_str_file_replaces_the_csf(self):
        got = self.bindings(loose={("Data", "Generals.str"): b'CONTROLBAR:AttackMove\r\n"Attack &Move"\r\nEND\r\n'})
        self.assertEqual(got["CONTROLBAR:AttackMove"], ["M"])
        self.assertNotIn("CONTROLBAR:Guard", got)

    def test_a_german_install(self):
        got = self.bindings(language="German", keys={"STOP": ("KEY_H", "NONE")},
                            card={"CONTROLBAR:AttackMove": "&Angriffsbewegung"})
        self.assertEqual(got, {"STOP": ["H"], "CONTROLBAR:AttackMove": ["A"]})

    def test_a_huge_loose_file_is_refused(self):
        with mock.patch.object(gen, "MAX_TEXT", 4), self.assertRaises(ValueError):
            self.bindings(loose={("Data", "INI", "CommandMap.ini"): b"; too long"})

    def test_no_pictures(self):
        with self.assertRaises(ValueError):
            gen.draw(None, {}, (40, 40))


class BuildTest(unittest.TestCase):
    """The shipped overlay remapped to the keys of a synthetic install."""

    @classmethod
    def setUpClass(cls):
        cls.shipped = {m: cells(OVERLAYS / TEMPLATE, m) for m in MODS}

    def built(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            make_install(Path(d) / "zh", **kw)
            out = build.build(TEMPLATE, SPEC, {"game_generals_dir": str(Path(d) / "zh")}.get, Path(d) / "c")
            self.assertIsNotNone(out)
            return {m: cells(out, m) for m in MODS}

    def changed(self, got):
        return {(m, k) for m in got for k in set(got[m]) | set(self.shipped[m])
                if got[m].get(k) != self.shipped[m].get(k)}

    def test_the_stock_keys_move_nothing(self):
        self.assertEqual(self.changed(self.built()), set())

    def test_a_rebind_moves_the_icon(self):
        keys = dict(ENGLISH, STOP=("KEY_K", "NONE"), SAVE_VIEW1=("KEY_F1", "ALT"))
        got = self.built(keys=keys, card=dict(CARD, **{"CONTROLBAR:Guard": "&Wache"}))
        plain, ctrl, alt = Modifier.NO_MOD, Modifier.CTRL, Modifier.ALT
        self.assertEqual(self.changed(got), {(plain, kc("S")), (plain, kc("K")), (plain, kc("G")),
                                             (plain, kc("W")), (ctrl, kc("F1")), (alt, kc("F1"))})
        self.assertEqual(got[plain][kc("K")], self.shipped[plain][kc("S")])
        self.assertEqual(got[alt][kc("F1")], self.shipped[ctrl][kc("F1")])

    def test_a_command_the_files_do_not_name_keeps_its_key(self):
        self.assertEqual(self.changed(self.built(keys={}, card={})), set())


class SpecTest(unittest.TestCase):

    def test_every_binding_names_a_command(self):
        for b in build.bindings(build.load_spec(SPEC)):
            self.assertIn("command", b, b["key"])

    def test_the_mapping_registers_the_overlay(self):
        import yaml
        with open(build.RES / "overlay-mapping.poly.yaml", encoding="utf-8") as f:
            mapping = yaml.safe_load(f)
        with mock.patch.dict(game_assets._specs, clear=True):
            game_assets.register_mapping(mapping)
            self.assertEqual(game_assets._specs.get(TEMPLATE), SPEC)

    def test_the_reader_and_its_setting_are_registered(self):
        self.assertIn("generals", READERS)
        self.assertEqual(reader_defaults()["game_generals_dir"], "")


if __name__ == "__main__":
    unittest.main()
