"""The SHIPPED Avid Pro Tools routing in `overlay-mapping.poly.yaml`.

Pro Tools pairs Command with Control and Control with Start, so the
`protools,pro tools` entry has a Windows default and an `os: macos` branch.
What it pins:

* "protools" (ProTools.exe) on Windows loads the Windows set;
* "pro tools" (the macOS app) on macOS loads the macOS set;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

WIN = ["protools_template.mods.png", "protools_template.combo.mods.png",
       "protools_template.extra.mods.png", "protools_template.gui.mods.png"]
MAC = ["protools_template_mac.mods.png", "protools_template_mac.combo.mods.png",
       "protools_template_mac.extra.mods.png", "protools_template_mac.gui.mods.png"]


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as telegram_routing_test)."""
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


class ProToolsRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry("Edit: Session", self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_windows_loads_the_windows_set(self):
        self.assertEqual(self._route("protools", "windows"), WIN)

    def test_macos_loads_the_macos_set(self):
        self.assertEqual(self._route("pro tools", "macos"), MAC)

    def test_every_named_file_exists(self):
        missing = [f for f in WIN + MAC if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
