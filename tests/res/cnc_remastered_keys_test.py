"""The C&C Remastered overlay's keys against the game's own default table
(DATA\\XML\\INPUTTRANSLATORCONFIGURATIONS.XML in Data\\CONFIG.MEG of the Steam
release, read 2026-11-15). The archive may not be committed; the defaults
below were copied from it, and every one of the 78 named bindings matched it
when this test was written."""
import unittest

from polyhost.services.game_assets import build

SPEC = build.RES / "overlay_sources" / "cnc_remastered" / "cnc_remastered.yaml"

DEFAULTS = {
    "COMMAND_CNC_STRUCTURES_TAB": "W", "COMMAND_CNC_SIDEBAR_TOGGLE": "CTRL+S",
    "COMMAND_CNC_REPAIR_TOGGLE": "SHIFT+R", "COMMAND_CNC_SELL_TOGGLE": "SHIFT+S",
    "COMMAND_CNC_TOGGLE_BEACON_MODE": "SHIFT+X", "COMMAND_CNC_SIDEBAR_SCROLL_UP": "CTRL+PGUP",
    "COMMAND_CNC_QUICK_SAVE": "CTRL+N", "COMMAND_CNC_QUICK_LOAD": "CTRL+L",
    "COMMAND_CNC_SCATTER": "X", "COMMAND_CNC_NEXT_UNIT": "DOT", "COMMAND_CNC_PREVIOUS_UNIT": "COMMA",
    "COMMAND_CNC_SELECT_ALL_ON_SCREEN": "A", "COMMAND_CNC_SELECT_ALL_IN_WORLD": "SHIFT+A",
    "COMMAND_CNC_CAMERA_TO_SELECTION": "HOME", "COMMAND_CNC_FORMATION_TOGGLE": "ALT+F",
    "COMMAND_CNC_DEPLOY_SELECTED_MCV": "BACKSLASH", "COMMAND_CAMERA_ZOOM_OUT": "PGDN",
    "COMMAND_GROUP_7_ADD_TO_SELECTED_UNITS": "SHIFT+7", "COMMAND_GROUP_0_ASSIGN": "CTRL+0",
    "COMMAND_BEGIN_CHAT": "SHIFT+ENTER", "COMMAND_CNC_SEND_ALL_PRESET_MESSAGE_4": "CTRL+F8",
    "COMMAND_CNC_SEND_TEAM_PRESET_MESSAGE_1": "F5", "COMMAND_CNC_SET_MAP_LOCATION_BOOKMARK_2": "CTRL+F2",
    "COMMAND_MUSIC_NEXT_TRACK": "EQUAL", "COMMAND_CNC_LEGACY_RENDERING_TOGGLE": "SPACE",
}


def token(b):
    return build.key_token("+".join([*map(str, b.get("mods") or []), str(b["key"])]))


class CncRemasteredKeysTest(unittest.TestCase):

    def setUp(self):
        self.bindings = build.bindings(build.load_spec(SPEC))

    def test_known_defaults(self):
        got = {b["command"]: token(b) for b in self.bindings if "command" in b}
        for command, key in DEFAULTS.items():
            self.assertEqual(got.get(command), build.key_token(key), command)

    def test_every_key_but_alt_enter_names_its_command(self):
        unnamed = [token(b) for b in self.bindings if "command" not in b]
        self.assertEqual(unnamed, [build.key_token("ALT+ENTER")])

    def test_no_key_is_drawn_twice(self):
        keys = [token(b) for b in self.bindings]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_group_icon_has_its_game_art_recipe(self):
        recipes = build.recipes(build.load_spec(SPEC), "gdi")
        for d in "1234567890":
            self.assertEqual(recipes[f"groupadd{d}"], {"mark": "ring", "of": f"group{d}"})


if __name__ == "__main__":
    unittest.main()
