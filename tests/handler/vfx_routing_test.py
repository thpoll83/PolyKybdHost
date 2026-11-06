"""The SHIPPED routing of the 3D and VFX sets in `overlay-mapping.poly.yaml`.

Substance 3D Painter, Nuke and Cinema 4D bind Ctrl on Windows/Linux and Cmd on
macOS, so their entries have an `os: macos` branch. 3ds Max is Windows only.
What it pins:

* each app, under the name the window handler reports on each OS it runs on,
  loads that OS's set;
* Nuke's versioned process names (`nuke17` on Windows after the first-dot cut,
  `nuke17.1` on Linux, `nuke17.1v3` on macOS) reach the `nuke` entry;
* every file a route names exists.

The names are the expected process / app names; none was checked on an
install (see each set's SOURCES.md).
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

PAINTER = ["substancepainter_template.mods.png", "substancepainter_template.combo.mods.png"]
PAINTER_MAC = ["substancepainter_template_mac.mods.png",
               "substancepainter_template_mac.combo.mods.png",
               "substancepainter_template_mac.extra.mods.png"]
NUKE = ["nuke_template.mods.png", "nuke_template.combo.mods.png",
        "nuke_template.extra.mods.png"]
NUKE_MAC = ["nuke_template_mac.mods.png", "nuke_template_mac.combo.mods.png",
            "nuke_template_mac.extra.mods.png", "nuke_template_mac.gui.mods.png"]
MAX = ["3dsmax_template.mods.png", "3dsmax_template.combo.mods.png",
       "3dsmax_template.extra.mods.png"]
C4D = ["cinema4d_template.mods.png", "cinema4d_template.combo.mods.png"]
C4D_MAC = ["cinema4d_template_mac.mods.png", "cinema4d_template_mac.combo.mods.png",
           "cinema4d_template_mac.extra.mods.png"]

# (reported app name, os, expected overlay list)
ROUTES = [
    ("adobe substance 3d painter", "windows", PAINTER),
    ("adobe substance 3d painter", "linux", PAINTER),
    ("adobe substance 3d painter", "macos", PAINTER_MAC),
    ("nuke17", "windows", NUKE),
    ("nuke15", "windows", NUKE),
    ("nuke17.1", "linux", NUKE),
    ("nuke17.1v3", "macos", NUKE_MAC),
    ("nukex17.1v3", "macos", NUKE_MAC),
    ("3dsmax", "windows", MAX),
    ("cinema 4d", "windows", C4D),
    ("cinema 4d", "macos", C4D_MAC),
    ("cinema 4d 2026", "macos", C4D_MAC),
]


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as capcut_routing_test)."""
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}") from e
    except Exception as e:
        # Skip only for a missing third-party backend or an Xlib display error.
        # A missing polyhost module is a real failure.
        if not ((isinstance(e, ModuleNotFoundError)
                 and not (e.name or "").startswith("polyhost"))
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}") from e
    return OverlayHandler


class VfxRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry("Untitled", self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_each_app_loads_its_set_on_each_os(self):
        for app, os_name, expected in ROUTES:
            with self.subTest(app=app, os=os_name):
                self.assertEqual(self._route(app, os_name), expected)

    def test_every_named_file_exists(self):
        named = {f for _, _, files in ROUTES for f in files}
        missing = sorted(f for f in named if not (RES / "overlays" / f).is_file())
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
