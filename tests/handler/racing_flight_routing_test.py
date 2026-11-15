"""The SHIPPED routing of the racing, artillery, flight and simulation games in
`overlay-mapping.poly.yaml`.

Each game uses the same keys on every OS, so each entry has one set and no
`os:` branch. What it pins:

* every process name of a game loads that game's set on all three platforms;
* a window title does not reroute it;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

# overlay -> (process names as the window handler reports them, a window title)
GAMES = {
    "supertuxkart_template.mods.png": (
        ("supertuxkart", "supertuxkart.exe", "net.supertuxkart.supertuxkart"),
        "SuperTuxKart"),
    "hedgewars_template.mods.png": (
        ("hwengine", "hwengine.exe", "hedgewars", "hedgewars.exe", "org.hedgewars.hedgewars"),
        "Hedgewars"),
    "flightgear_template.mods.png": (
        ("fgfs", "fgfs.exe", "flightgear", "org.flightgear.flightgear"),
        "FlightGear"),
    "thrive_template.mods.png": (
        ("thrive", "thrive.exe", "thrive.x86_64"),
        "Thrive"),
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


def _files(overlay):
    return [overlay] if isinstance(overlay, str) else list(overlay)


class RacingFlightRoutingTest(unittest.TestCase):

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
        for overlay, (apps, title) in GAMES.items():
            for app in apps:
                for os_name in ("windows", "macos", "linux"):
                    for shown in (title, ""):
                        with self.subTest(app=app, os=os_name, title=shown):
                            routed = self._route(app, os_name, shown)
                            self.assertIsNotNone(routed)
                            self.assertEqual(_files(routed)[0], overlay)

    def test_every_named_file_exists(self):
        missing = []
        for overlay, (apps, title) in GAMES.items():
            for f in _files(self._route(apps[0], "linux", title)):
                if not (RES / "overlays" / f).is_file():
                    missing.append(f)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
