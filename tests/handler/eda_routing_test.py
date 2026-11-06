"""The SHIPPED routing of the electronics tools in `overlay-mapping.poly.yaml`.

Altium Designer, Cadence OrCAD X Capture, IAR Embedded Workbench for Arm and
STM32CubeIDE. What it pins:

* Altium (`x2`, and `dxp` for releases before Altium Designer 10) loads the
  PCB Editor set, and the Schematic Editor set when the window title names a
  .SchDoc or .SchLib document;
* OrCAD X Capture (`capture`) loads its set;
* IAR (`iaridepm`) loads the Windows set, and the Linux set on Linux;
* STM32CubeIDE loads the CDT set of its platform, and Eclipse keeps its own;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

ALTIUM_PCB = ["altium_pcb_template.mods.png", "altium_pcb_template.combo.mods.png"]
ALTIUM_SCH = ["altium_sch_template.mods.png", "altium_sch_template.combo.mods.png"]
ORCAD = ["orcad_capture_template.mods.png", "orcad_capture_template.combo.mods.png"]
IAR = ["iar_ewarm_template.mods.png", "iar_ewarm_template.combo.mods.png"]
IAR_LINUX = ["iar_ewarm_template_linux.mods.png", "iar_ewarm_template_linux.combo.mods.png"]
CDT = ["eclipse_cdt_template.mods.png", "eclipse_cdt_template.combo.mods.png",
       "eclipse_cdt_template.extra.mods.png"]
CDT_LINUX = ["eclipse_cdt_template_linux.mods.png", "eclipse_cdt_template_linux.combo.mods.png",
             "eclipse_cdt_template_linux.extra.mods.png"]
CDT_MAC = ["eclipse_cdt_template_mac.mods.png", "eclipse_cdt_template_mac.combo.mods.png",
           "eclipse_cdt_template_mac.extra.mods.png", "eclipse_cdt_template_mac.gui.mods.png"]


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here.

    A missing module of our own is a real error, not a missing display, so a
    ModuleNotFoundError naming a `polyhost` module is raised again.
    """
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}")
    except ModuleNotFoundError as e:
        if (e.name or "").startswith("polyhost"):
            raise
        raise unittest.SkipTest(f"active_window needs a module: {e}")
    except Exception as e:
        if type(e).__module__.split(".")[0] != "Xlib":
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}")
    return OverlayHandler


class EdaRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, title, os_name="windows"):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else [str(f) for f in m["overlay"]]

    def test_altium_pcb_document_loads_the_pcb_set(self):
        for app in ("x2", "dxp"):
            with self.subTest(app=app):
                self.assertEqual(self._route(app, "Altium Designer - Board.PcbDoc"), ALTIUM_PCB)
                self.assertEqual(self._route(app, "Altium Designer - Footprints.PcbLib"),
                                 ALTIUM_PCB)

    def test_altium_schematic_document_loads_the_schematic_set(self):
        for title in ("Altium Designer - Sheet1.SchDoc",
                      "C:\\Projects\\Power.SchDoc - Altium Designer (25.1.2)",
                      "Altium Designer - Symbols.SchLib"):
            with self.subTest(title=title):
                self.assertEqual(self._route("x2", title), ALTIUM_SCH)

    def test_altium_other_windows_get_the_pcb_set(self):
        self.assertEqual(self._route("x2", "Altium Designer"), ALTIUM_PCB)
        self.assertEqual(self._route("x2", "Altium Designer - Notes.SchDocBackup"), ALTIUM_PCB)

    def test_orcad_capture(self):
        self.assertEqual(self._route("capture", "OrCAD X Capture - [/ - (SCHEMATIC1 : PAGE1)]"),
                         ORCAD)

    def test_iar_per_platform(self):
        self.assertEqual(self._route("iaridepm", "IAR Embedded Workbench IDE - Arm 9.70.1"), IAR)
        self.assertEqual(self._route("iaridepm", "IAR Embedded Workbench IDE", "linux"),
                         IAR_LINUX)

    def test_stm32cubeide_per_platform(self):
        title = "ws - blinky/Core/Src/main.c - STM32CubeIDE"
        self.assertEqual(self._route("stm32cubeide", title), CDT)
        self.assertEqual(self._route("stm32cubeide", title, "linux"), CDT_LINUX)
        self.assertEqual(self._route("stm32cubeide", title, "macos"), CDT_MAC)

    def test_eclipse_keeps_its_java_set(self):
        got = self._route("eclipse", "ws - app/src/Main.java - Eclipse IDE")
        self.assertIn("eclipse_template.mods.png", got)

    def test_every_named_file_exists(self):
        names = (ALTIUM_PCB + ALTIUM_SCH + ORCAD + IAR + IAR_LINUX
                 + CDT + CDT_LINUX + CDT_MAC)
        missing = [f for f in names if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
