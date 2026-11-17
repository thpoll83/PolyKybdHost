"""In each free-to-play game overlay, two keys show the same picture only when
they run the same action: a numbered slot (weapon, flask, party member, quick
chat) carries its number in the icon. Compared on the generated cells, so a
picture the shared concept renderer draws counts too."""
import unittest

import yaml

from polyhost.res.overlay_layout import resolve_key
from polyhost.services.game_assets.build import RES, modifier
from tests.services.game_assets_ra_test import cells

SPECS = ("tf2/tf2", "apex/apex", "rocketleague/rocketleague", "poe/poe", "poe/poe2",
         "overwatch/overwatch", "genshin/genshin")
FIRST_PERSON = ("tf2/tf2", "apex/apex", "overwatch/overwatch")


def spec(name):
    with open(RES / "overlay_sources" / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


class DistinctIconsTest(unittest.TestCase):

    def test_one_picture_per_action(self):
        for name in SPECS:
            s = spec(name)
            png = RES / "overlays" / f"{s['output']}.mods.png"
            by_picture = {}
            for b in s["bindings"]:
                data = cells(png, modifier(b.get("mods"))).get(resolve_key(b["key"]).value)
                self.assertIsNotNone(data, f"{name}: {b['key']} has no picture")
                by_picture.setdefault(data, set()).add(b.get("command", b["label"]))
            shared = [sorted(a) for a in by_picture.values() if len(a) > 1]
            self.assertEqual(shared, [], f"{name}: one picture for different actions")

    def test_first_person_games_draw_the_movement_keys(self):
        for name in FIRST_PERSON:
            keys = {str(b["key"]) for b in spec(name)["bindings"] if not b.get("mods")}
            self.assertLessEqual({"W", "A", "S", "D"}, keys, name)


if __name__ == "__main__":
    unittest.main()
