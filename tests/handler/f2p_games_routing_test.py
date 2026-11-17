"""The free-to-play game overlays route to their sets from the process name
the window handler reports (cut at the first dot and lower-cased), and Path of
Exile 2, which runs as the same executables as Path of Exile, by its window
title."""
import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key
from tests.handler.joplin_routing_test import _overlay_handler_class

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

ROUTES = {
    "tf2_template.mods.png": ("tf_win64.exe", "tf_linux64", "steam_app_440"),
    "apex_template.mods.png": ("r5apex.exe", "r5apex_dx12.exe", "steam_app_1172470"),
    "rocketleague_template.mods.png": ("RocketLeague.exe", "steam_app_252950"),
    "overwatch_template.mods.png": ("Overwatch.exe", "steam_app_2357570"),
    "genshin_template.mods.png": ("GenshinImpact.exe", "YuanShen.exe"),
    "poe2_template.mods.png": ("steam_app_2694490",),
}
POE_EXES = ("PathOfExile.exe", "PathOfExile_x64.exe", "PathOfExileSteam.exe",
            "PathOfExile_x64Steam.exe", "PathOfExile_KG.exe", "PathOfExile_x64_KG.exe")


class F2pGamesRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, process, title="", title_known=True):
        key = mapping_key(process.split(".")[0].lower(), self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, "windows", title_known=title_known)
        return None if m is None else m["overlay"]

    def test_each_process_loads_its_set(self):
        for overlay, processes in ROUTES.items():
            for process in processes:
                self.assertEqual(self._route(process, "Game"), overlay, process)

    def test_path_of_exile_1_and_2_by_title(self):
        for exe in POE_EXES:
            self.assertEqual(self._route(exe, "Path of Exile"), "poe_template.mods.png", exe)
            self.assertEqual(self._route(exe, "Path of Exile 2"), "poe2_template.mods.png", exe)

    def test_path_of_exile_without_a_title_gets_the_first_game(self):
        self.assertEqual(self._route("PathOfExile.exe", "", title_known=False), "poe_template.mods.png")


if __name__ == "__main__":
    unittest.main()
