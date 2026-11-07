"""The SHIPPED routing of the Autodesk Maya set in `overlay-mapping.poly.yaml`.

Maya keeps Ctrl on all three platforms (Autodesk: Ctrl = Control on macOS), but
its File and Edit keys also take Cmd on macOS, so the entry has an
`os: macos` branch with a set that adds those Cmd keys. What it pins:

* `maya` (Windows `maya.exe`, the macOS app "Maya"), `maya 2026` (the
  macOS app with its release year, which the matcher drops) and `maya.bin`
  (the Linux process) load the Maya set, and macOS loads the `_mac` set;
* the Windows and Linux sets carry no Cmd key, and the macOS set has Cmd+S;
* every file a route names exists.

The names are the expected process / app names; none was checked on an
install (see overlay_sources/maya/SOURCES.md).
"""

import unittest
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

MAYA = ["maya_template.mods.png", "maya_template.combo.mods.png"]
MAYA_MAC = ["maya_template_mac.mods.png", "maya_template_mac.combo.mods.png",
            "maya_template_mac.extra.mods.png"]

# (reported app name, os, expected overlay list)
ROUTES = [
    ("maya", "windows", MAYA),
    ("maya.bin", "linux", MAYA),
    ("maya", "macos", MAYA_MAC),
    ("maya 2026", "macos", MAYA_MAC),
    ("maya 2025", "macos", MAYA_MAC),
]


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as vfx_routing_test)."""
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


class MayaRoutingTest(unittest.TestCase):

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

    def test_each_name_loads_its_set_on_each_os(self):
        for app, os_name, expected in ROUTES:
            with self.subTest(app=app, os=os_name):
                self.assertEqual(self._route(app, os_name), expected)

    def test_every_named_file_exists(self):
        named = {f for _, _, files in ROUTES for f in files}
        missing = sorted(f for f in named if not (RES / "overlays" / f).is_file())
        self.assertEqual(missing, [])


class MayaCmdKeysTest(unittest.TestCase):
    """The Cmd (GUI) keys exist on macOS only. GUI alone is the combo file's
    alpha channel (overlay_specification.md). The ESC mark is drawn on every
    layer, so its cell is cleared before counting."""

    @staticmethod
    def _gui_keys(name):
        from polyhost.device.keys import KeyCode
        from polyhost.res.overlay_layout import SLOT_H, SLOT_W, cell_for
        a = np.asarray(Image.open(RES / "overlays" / name).convert("RGBA"))[..., 3].copy()
        row, col = cell_for(KeyCode.KC_ESCAPE)
        a[row * SLOT_H:(row + 1) * SLOT_H, col * SLOT_W:(col + 1) * SLOT_W] = 0
        return int((a > 0).sum())

    def test_windows_set_has_no_cmd_key(self):
        self.assertEqual(self._gui_keys("maya_template.combo.mods.png"), 0)

    def test_macos_set_has_cmd_keys(self):
        self.assertGreater(self._gui_keys("maya_template_mac.combo.mods.png"), 0)


if __name__ == "__main__":
    unittest.main()
