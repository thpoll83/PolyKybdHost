"""The SHIPPED arena shooter routing in `overlay-mapping.poly.yaml`.

Each game uses the same keys on every OS, so each entry has one set and no
`os:` branch. What it pins:

* every process name of a game loads that game's set, on all three platforms
  and whatever the window title is, including no title;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

XONOTIC = "xonotic_template.mods.png"
XONOTIC_NAMES = (
    "xonotic", "xonotic-sdl", "xonotic-glx", "xonotic-linux64-sdl", "xonotic-linux64-glx",
    "xonotic-linux-sdl", "xonotic-linux-glx", "xonotic.exe", "xonotic-x86.exe",
    "xonotic-wgl.exe", "xonotic-x86-wgl.exe", "xonotic-x64.exe", "xonotic-sdl.exe",
    "xonotic-x64-sdl.exe", "xonotic-osx-sdl-bin", "org.xonotic.xonotic")

UNVANQUISHED = "unvanquished_template.mods.png"
UNVANQUISHED_NAMES = ("daemon", "daemon.exe", "daemon-vulkan", "unvanquished",
                      "net.unvanquished.unvanquished")

REDECLIPSE = "redeclipse_template.mods.png"
REDECLIPSE_NAMES = (
    "redeclipse", "redeclipse.exe", "redeclipse_linux", "redeclipse_universal",
    "redeclipse_bsd", "redeclipse_osx", "redeclipse_windows.exe", "redeclipse_native",
    "net.redeclipse.redeclipse")

# (set, process names, a window title of the game)
GAMES = (
    (XONOTIC, XONOTIC_NAMES, "Xonotic"),
    (UNVANQUISHED, UNVANQUISHED_NAMES, "Unvanquished"),
    (REDECLIPSE, REDECLIPSE_NAMES, "Red Eclipse"),
)


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as qutebrowser_routing_test)."""
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


class ArenaShooterRoutingTest(unittest.TestCase):

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
        for overlay, names, title in GAMES:
            for app in names:
                for os_name in ("windows", "macos", "linux"):
                    with self.subTest(app=app, os=os_name):
                        self.assertEqual(self._route(app, os_name, title), overlay)

    def test_title_does_not_reroute(self):
        for overlay, names, _ in GAMES:
            for title in ("", None, "some other title"):
                with self.subTest(app=names[0], title=title):
                    self.assertEqual(self._route(names[0], "linux", title), overlay)

    def test_every_named_file_exists(self):
        files = []
        for overlay, _, _ in GAMES:
            files += [overlay] if isinstance(overlay, str) else overlay
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
