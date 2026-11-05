"""The SHIPPED OBS Studio routing in `overlay-mapping.poly.yaml`.

OBS binds different keys per platform (Rename is F2 or Return, Exit is Ctrl+Q
only on Linux, macOS uses Cmd), so the `obs` entry has three sets. What it pins:

* `obs64` on Windows loads the Windows set;
* `obs` and the Flatpak id on Linux load the Linux set;
* "OBS" and "OBS Studio" on macOS load the macOS set;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

WIN = ["obs_template.mods.png", "obs_template.combo.mods.png"]
LINUX = ["obs_template_linux.mods.png", "obs_template_linux.combo.mods.png"]
MAC = ["obs_template_mac.mods.png", "obs_template_mac.combo.mods.png",
       "obs_template_mac.extra.mods.png"]


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


class ObsRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry("OBS 32.0.0 - Profile: Untitled - Scenes: Untitled",
                                self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_windows_loads_the_windows_set(self):
        self.assertEqual(self._route("obs64", "windows"), WIN)

    def test_linux_names_load_the_linux_set(self):
        for app, os_name in (("obs", "linux"), ("obs", "linux_gnome"),
                             ("com.obsproject.studio", "linux_kde")):
            self.assertEqual(self._route(app, os_name), LINUX, (app, os_name))

    def test_macos_names_load_the_macos_set(self):
        for app in ("obs", "obs studio"):
            self.assertEqual(self._route(app, "macos"), MAC, app)

    def test_obsidian_is_not_caught(self):
        self.assertNotIn("obs_template.mods.png", self._route("obsidian", "windows") or [])

    def test_every_named_file_exists(self):
        missing = [f for f in WIN + LINUX + MAC if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
