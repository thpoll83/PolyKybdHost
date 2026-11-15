"""C&C Generals and Zero Hour route to their overlay by window title.

Both run as Game.dat, which mapping_key reads as `game`, a name another
program may use, so the entry is gated on the two window titles seen in a log
of the Steam release (2026-11-14).
"""
import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key
from tests.handler.joplin_routing_test import _overlay_handler_class

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
OVERLAY = "generals_template.mods.png"


class GeneralsRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, title, title_known=True):
        # The window handler cuts the process name at the first dot and lowercases it.
        key = mapping_key("Game.dat".split(".")[0].lower(), self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, "windows", title_known=title_known)
        return None if m is None else m["overlay"]

    def test_both_games_load_the_overlay(self):
        for title in ("Command and Conquer Generals", "Command & Conquer (TM) Generals Zero Hour"):
            self.assertEqual(self._route(title), OVERLAY, title)

    def test_another_game_dat_does_not(self):
        self.assertIsNone(self._route("Some Other Game"))
        self.assertIsNone(self._route("", title_known=False))

    def test_the_overlay_exists(self):
        self.assertTrue((RES / "overlays" / OVERLAY).is_file())


if __name__ == "__main__":
    unittest.main()
