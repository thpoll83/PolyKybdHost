"""The SHIPPED Doom and Quake source port routing in `overlay-mapping.poly.yaml`.

Every port uses the same keys on every OS, so each entry has one set and no
`os:` branch. What it pins:

* every process name of a port loads that port's set on all three platforms;
* a window title (the game or level name) does not reroute a port;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

# overlay -> (process names as the handler reports them, a window title)
PORTS = {
    "gzdoom_template.mods.png": (
        ("gzdoom", "gzdoom.exe", "org.zdoom.gzdoom"), "DOOM 2: Hell on Earth"),
    "uzdoom_template.mods.png": (
        ("uzdoom", "uzdoom.exe", "org.zdoom.uzdoom"), "The Ultimate DOOM"),
    "chocolate_doom_template.mods.png": (
        ("chocolate-doom", "chocolate-doom.exe", "org.chocolate_doom.doom"),
        "The Ultimate DOOM - Chocolate Doom 3.1.1"),
    "crispy_doom_template.mods.png": (
        ("crispy-doom", "crispy-doom.exe", "io.github.fabiangreffrath.doom"),
        "DOOM 2: Hell on Earth - Crispy Doom 7.2"),
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


class DoomQuakeRoutingTest(unittest.TestCase):

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
        for overlay, (apps, title) in PORTS.items():
            for app in apps:
                for os_name in ("windows", "macos", "linux"):
                    with self.subTest(app=app, os=os_name):
                        self.assertEqual(self._route(app, os_name, title), overlay)

    def test_no_title_and_empty_title(self):
        for overlay, (apps, _) in PORTS.items():
            for title in (None, ""):
                with self.subTest(app=apps[0], title=title):
                    self.assertEqual(self._route(apps[0], "linux", title), overlay)

    def test_no_process_name_is_shared(self):
        names = [app for apps, _ in PORTS.values() for app in apps]
        self.assertEqual(len(names), len(set(names)))

    def test_every_named_file_exists(self):
        missing = [f for f in PORTS if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
