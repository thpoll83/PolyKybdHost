"""The SHIPPED routing of the space game sets in `overlay-mapping.poly.yaml`.

Each game uses the same keys on every OS, so each entry has one set and no
`os:` branch. What it pins:

* every process name of a game loads that game's set on all three platforms;
* a window title, or no title, does not reroute it;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

# game -> (process names as the window handler reports them, a window title, overlay)
GAMES = {
    "Endless Sky": (
        ("endless-sky", "endless sky", "endless sky.exe", "io.github.endless_sky.endless_sky"),
        "Endless Sky",
        "endless_sky_template.mods.png"),
    "Naev": (
        ("naev", "naev.exe", "org.naev.naev"),
        "Naev - Sea of Darkness",
        "naev_template.mods.png"),
    "Oolite": (
        ("oolite", "oolite.exe", "space.oolite.oolite"),
        "Oolite v1.92.1",
        ["oolite_template.mods.png", "oolite_template.combo.mods.png"]),
}


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as emulator_routing_test)."""
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}") from e
    except Exception as e:
        if not ((isinstance(e, ModuleNotFoundError)
                 and not (e.name or "").startswith("polyhost"))
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}") from e
    return OverlayHandler


class SpaceGamesRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name, title):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_every_process_name_on_every_platform(self):
        for game, (apps, title, overlay) in GAMES.items():
            for app in apps:
                for os_name in ("windows", "macos", "linux"):
                    with self.subTest(game=game, app=app, os=os_name):
                        self.assertEqual(self._route(app, os_name, title), overlay)

    def test_an_empty_title_routes_the_same(self):
        for game, (apps, _title, overlay) in GAMES.items():
            for app in apps:
                with self.subTest(game=game, app=app):
                    self.assertEqual(self._route(app, "linux", ""), overlay)

    def test_every_named_file_exists(self):
        files = []
        for _apps, _title, overlay in GAMES.values():
            files += [overlay] if isinstance(overlay, str) else overlay
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
