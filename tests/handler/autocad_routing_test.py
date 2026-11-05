"""The SHIPPED Autodesk AutoCAD routing in `overlay-mapping.poly.yaml`.

AutoCAD for Mac binds other keys than AutoCAD on Windows, so the `acad,autocad`
entry has a default (Windows) set and an `os: macos` branch. What it pins:

* `acad` (acad.exe) on Windows loads the Windows set;
* "AutoCAD 2026" on macOS, through the trailing-year rule, loads the macOS set;
* AutoCAD LT (`acadlt`, "AutoCAD LT 2026") matches nothing: it lacks several
  of the keys the set draws;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

WIN = ["autocad_template.mods.png", "autocad_template.combo.mods.png"]
MAC = ["autocad_template_mac.mods.png", "autocad_template_mac.combo.mods.png",
       "autocad_template_mac.extra.mods.png", "autocad_template_mac.gui.mods.png"]


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as nano_routing_test)."""
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}")
    except Exception as e:
        if not (isinstance(e, ModuleNotFoundError)
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}")
    return OverlayHandler


class AutocadRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry("Drawing1.dwg", self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_acad_on_windows_loads_the_windows_set(self):
        self.assertEqual(self._route("acad", "windows"), WIN)

    def test_autocad_with_year_on_macos_loads_the_macos_set(self):
        self.assertEqual(self._route("autocad 2026", "macos"), MAC)
        self.assertEqual(self._route("autocad", "macos"), MAC)

    def test_autocad_lt_matches_nothing(self):
        self.assertIsNone(self._route("acadlt", "windows"))
        self.assertIsNone(self._route("autocad lt 2026", "macos"))

    def test_every_named_file_exists(self):
        missing = [f for f in WIN + MAC if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
