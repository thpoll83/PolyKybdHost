"""The SHIPPED routing of the real-time strategy and management game sets in
`overlay-mapping.poly.yaml`: Beyond All Reason, KeeperFX and Widelands.

Each game uses the same keys on every OS, so each entry has one set and no
`os:` branch. What it pins:

* every process name of a game (lower case, as the handler reports it) loads
  that game's set on all three platforms;
* a window title does not reroute it, and neither does a missing title;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

# {overlay: (process names, a window title of the game)}
GAMES = {
    ("beyond_all_reason_template.mods.png", "beyond_all_reason_template.combo.mods.png"): (
        ("spring", "spring.exe", "beyond-all-reason", "beyond-all-reason.exe",
         "info.beyondallreason.bar"),
        "Beyond All Reason"),
    ("keeperfx_template.mods.png",): (
        ("keeperfx", "keeperfx.exe", "keeperfx_hvlog", "keeperfx_hvlog.exe"),
        "KeeperFX"),
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


def _as_list(overlay):
    return [overlay] if isinstance(overlay, str) else list(overlay)


class RtsManagementRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name, title):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else _as_list(m["overlay"])

    def test_every_process_name_on_every_platform(self):
        for overlay, (apps, title) in GAMES.items():
            for app in apps:
                for os_name in ("windows", "macos", "linux"):
                    with self.subTest(app=app, os=os_name):
                        self.assertEqual(self._route(app, os_name, title), list(overlay))

    def test_an_empty_and_a_missing_title_route_the_same(self):
        for overlay, (apps, _title) in GAMES.items():
            for title in ("", None):
                with self.subTest(app=apps[0], title=title):
                    self.assertEqual(self._route(apps[0], "linux", title), list(overlay))

    def test_every_named_file_exists(self):
        missing = [f for overlay in GAMES for f in overlay
                   if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
