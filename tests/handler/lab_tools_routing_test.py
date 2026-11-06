"""The SHIPPED routing of the lab and engineering sets in `overlay-mapping.poly.yaml`.

What it pins:

* NI LabVIEW: `labview` loads the Windows set, "LabVIEW 2026" on macOS the
  macOS (Cmd) set, `labview` on Linux the Linux (Alt) set;
* COMSOL Multiphysics: `comsol` on Windows and Linux, "COMSOL Multiphysics 6.4"
  on macOS, each to its own set;
* OriginPro: `origin64` loads the Origin set; `origin` (EA's game launcher)
  matches nothing;
* Simulink runs in the MATLAB process: a Simulink Editor title
  ("<model> - Simulink") inside the MATLAB entry loads the Simulink set on
  Windows, Linux and macOS, while the MATLAB desktop and Editor titles keep the
  MATLAB set;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"


def _set(name, *tiers):
    return [f"{name}.mods.png"] + [f"{name}.{t}.mods.png" for t in tiers]


LABVIEW = _set("labview_template", "combo")
LABVIEW_MAC = _set("labview_template_mac", "combo", "extra")
LABVIEW_LINUX = _set("labview_template_linux", "combo")
COMSOL = _set("comsol_template", "combo")
COMSOL_MAC = _set("comsol_template_mac", "combo", "extra")
COMSOL_LINUX = _set("comsol_template_linux", "combo")
ORIGIN = _set("origin_template", "combo")
SIMULINK = _set("simulink_template", "combo")
SIMULINK_MAC = _set("simulink_template_mac", "combo", "extra")
MATLAB = _set("matlab_template", "combo")
MATLAB_MAC = _set("matlab_template_mac", "combo", "extra")

ALL = [LABVIEW, LABVIEW_MAC, LABVIEW_LINUX, COMSOL, COMSOL_MAC, COMSOL_LINUX,
       ORIGIN, SIMULINK, SIMULINK_MAC]


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


class LabToolsRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name, title="untitled"):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_labview_routes_per_os(self):
        title = "Untitled 1 Block Diagram"
        self.assertEqual(self._route("labview", "windows", title), LABVIEW)
        self.assertEqual(self._route("labview 2026", "macos", title), LABVIEW_MAC)
        self.assertEqual(self._route("labview 2025 q3", "macos", title), LABVIEW_MAC)
        self.assertEqual(self._route("labview", "linux", title), LABVIEW_LINUX)

    def test_comsol_routes_per_os(self):
        title = "busbar.mph - COMSOL Multiphysics"
        self.assertEqual(self._route("comsol", "windows", title), COMSOL)
        self.assertEqual(self._route("comsol", "linux", title), COMSOL_LINUX)
        self.assertEqual(self._route("comsol multiphysics 6.4", "macos", title),
                         COMSOL_MAC)

    def test_origin_routes_and_ea_origin_does_not(self):
        self.assertEqual(self._route("origin64", "windows", "Origin 2025b - UNTITLED"),
                         ORIGIN)
        self.assertIsNone(self._route("origin", "windows", "Origin"))

    def test_simulink_title_routes_inside_matlab(self):
        for title in ("vdp - Simulink", "vdp* - Simulink",
                      "untitled - Simulink academic use"):
            with self.subTest(title=title):
                self.assertEqual(self._route("matlab", "windows", title), SIMULINK)
                self.assertEqual(self._route("matlab", "linux", title), SIMULINK)
                self.assertEqual(self._route("matlab_r2026b", "macos", title),
                                 SIMULINK_MAC)

    def test_matlab_desktop_keeps_the_matlab_set(self):
        for title in ("MATLAB R2026b - academic use",
                      "Editor - C:\\work\\simulink_setup.m", "Simulink Start Page"):
            with self.subTest(title=title):
                self.assertEqual(self._route("matlab", "windows", title), MATLAB)
                self.assertEqual(self._route("matlab_r2026b", "macos", title),
                                 MATLAB_MAC)

    def test_every_named_file_exists(self):
        missing = [f for files in ALL for f in files
                   if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
