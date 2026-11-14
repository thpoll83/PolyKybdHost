"""The SHIPPED routing of the sandbox and RPG game sets in
`overlay-mapping.poly.yaml`.

Every set uses the same keys on every OS, so each entry has one set and no
`os:` branch. What it pins:

* every process name of each game loads that game's set on all three platforms;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
PLATFORMS = ("windows", "macos", "linux")

LUANTI = "luanti_template.mods.png"

# (overlay, window title, process names)
GAMES = [
    (LUANTI, "Luanti 5.18.0 [Singleplayer]",
     ("luanti", "minetest", "org.luanti.luanti", "net.minetest.minetest")),
]


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


def _files(overlay):
    return [overlay] if isinstance(overlay, str) else list(overlay)


class SandboxRpgRoutingTest(unittest.TestCase):

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
        for overlay, title, apps in GAMES:
            for app in apps:
                for os_name in PLATFORMS:
                    with self.subTest(app=app, os=os_name):
                        self.assertEqual(self._route(app, os_name, title), overlay)

    def test_no_title_still_routes(self):
        """A platform that reports no window title still gets the set: the
        entries match on the process name alone."""
        for overlay, _title, apps in GAMES:
            for app in apps:
                with self.subTest(app=app):
                    self.assertEqual(self._route(app, "linux", ""), overlay)

    def test_every_named_file_exists(self):
        names = [f for overlay, _title, _apps in GAMES for f in _files(overlay)]
        missing = [f for f in names if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
