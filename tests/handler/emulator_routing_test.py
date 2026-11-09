"""The SHIPPED RetroArch and MAME routing in `overlay-mapping.poly.yaml`.

Both use the same keys on every OS, so each entry has one set and no `os:`
branch. What it pins:

* `retroarch` loads the RetroArch set on all three platforms;
* `mame` and `mame64` (releases before 0.237) load the MAME set;
* a game title in the window does not reroute either;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

RETROARCH = "retroarch_template.mods.png"
MAME = ["mame_template.mods.png", "mame_template.combo.mods.png"]


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


class EmulatorRoutingTest(unittest.TestCase):

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

    def test_retroarch_on_every_platform(self):
        for os_name in ("windows", "macos", "linux"):
            with self.subTest(os=os_name):
                self.assertEqual(
                    self._route("retroarch", os_name, "RetroArch Snes9x 1.62 || Super Metroid"),
                    RETROARCH)

    def test_mame_and_mame64(self):
        for app in ("mame", "mame64"):
            for os_name in ("windows", "macos", "linux"):
                with self.subTest(app=app, os=os_name):
                    self.assertEqual(
                        self._route(app, os_name, "MAME: Pac-Man (Midway) [pacman]"), MAME)

    def test_every_named_file_exists(self):
        missing = [f for f in [RETROARCH, *MAME] if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
