"""The SHIPPED routing of the Tekla Structures, SketchUp and Inventor sets in
`overlay-mapping.poly.yaml`.

What it pins:

* Tekla Structures (`TeklaStructures.exe`, Windows only) loads its set;
* Inventor (`Inventor.exe`, Windows only) loads its set;
* SketchUp loads the Windows set for `SketchUp.exe` and the macOS set for
  "SketchUp 2026" (through the trailing-year rule) and plain "SketchUp";
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

TEKLA = ["tekla_template.mods.png", "tekla_template.combo.mods.png"]
INVENTOR = ["inventor_template.mods.png", "inventor_template.combo.mods.png"]
SKETCHUP_WIN = ["sketchup_template.mods.png"]
SKETCHUP_MAC = ["sketchup_template_mac.mods.png", "sketchup_template_mac.combo.mods.png"]


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here.

    A missing module of our own is a real failure, never a skip."""
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}")
    except Exception as e:
        if isinstance(e, ModuleNotFoundError) and (e.name or "").startswith("polyhost"):
            raise
        if not (isinstance(e, ModuleNotFoundError)
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}")
    return OverlayHandler


def _as_list(overlay):
    return [overlay] if isinstance(overlay, str) else list(overlay)


class CadBimRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name, title="Model"):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else _as_list(m["overlay"])

    def test_tekla_on_windows(self):
        self.assertEqual(self._route("teklastructures", "windows"), TEKLA)
        self.assertEqual(self._route("tekla structures", "windows"), TEKLA)

    def test_inventor_on_windows(self):
        self.assertEqual(self._route("inventor", "windows", "Part1.ipt"), INVENTOR)

    def test_sketchup_on_windows(self):
        self.assertEqual(self._route("sketchup", "windows", "Untitled - SketchUp Pro 2026"),
                         SKETCHUP_WIN)

    def test_sketchup_on_macos(self):
        self.assertEqual(self._route("sketchup 2026", "macos"), SKETCHUP_MAC)
        self.assertEqual(self._route("sketchup", "macos"), SKETCHUP_MAC)

    def test_every_named_file_exists(self):
        names = TEKLA + INVENTOR + SKETCHUP_WIN + SKETCHUP_MAC
        missing = [f for f in names if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
