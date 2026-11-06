"""The SHIPPED Winamp routing in `overlay-mapping.poly.yaml`.

Winamp 5.x is a Windows program, so the `winamp` entry has only an
`os: windows` branch and no default. What it pins:

* "Winamp" (winamp.exe) on Windows loads the Winamp set;
* a window named "winamp" on macOS or Linux loads nothing;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

WIN = ["winamp_template.mods.png", "winamp_template.combo.mods.png"]


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


class WinampRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry("Winamp", self.mapping[key], None, os_name)
        return None if m is None else m.get("overlay")

    def test_windows_loads_the_winamp_set(self):
        self.assertEqual(self._route("winamp", "windows"), WIN)

    def test_other_platforms_load_nothing(self):
        for os_name in ("macos", "linux"):
            with self.subTest(os=os_name):
                self.assertIsNone(self._route("winamp", os_name))

    def test_every_named_file_exists(self):
        missing = [f for f in WIN if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
