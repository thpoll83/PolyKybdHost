"""The SHIPPED routing of the turn-based strategy game sets in
`overlay-mapping.poly.yaml`.

What it pins:

* every process name of a set loads that set, on all three platforms;
* a set with a macOS branch loads its macOS files there;
* a window title does not reroute a set that is matched by process name;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

WESNOTH = ["wesnoth_template.mods.png", "wesnoth_template.combo.mods.png"]
WESNOTH_MAC = ["wesnoth_template_mac.mods.png", "wesnoth_template_mac.combo.mods.png",
               "wesnoth_template_mac.extra.mods.png"]

OSES = ("windows", "macos", "linux")

# (process names, window title, {os: overlay}); an os that is not listed uses
# the "windows" value.
BY_PROCESS = [
    (("wesnoth", "wesnoth.exe", "org.wesnoth.wesnoth", "the battle for wesnoth"),
     "The Battle for Wesnoth - 1.18.8", {"windows": WESNOTH, "macos": WESNOTH_MAC}),
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


class TbsGamesRoutingTest(unittest.TestCase):

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
        for apps, title, expected in BY_PROCESS:
            for app in apps:
                for os_name in OSES:
                    with self.subTest(app=app, os=os_name):
                        self.assertEqual(self._route(app, os_name, title),
                                         expected.get(os_name, expected["windows"]))

    def test_title_does_not_reroute_a_process_match(self):
        for apps, _title, expected in BY_PROCESS:
            for title in ("", "CodeBrowser: project:/program", "Minecraft 1.21.4"):
                with self.subTest(app=apps[0], title=title):
                    self.assertEqual(self._route(apps[0], "windows", title),
                                     expected["windows"])

    def test_every_named_file_exists(self):
        named = [f for _apps, _title, expected in BY_PROCESS
                 for overlay in expected.values() for f in _files(overlay)]
        missing = [f for f in named if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
