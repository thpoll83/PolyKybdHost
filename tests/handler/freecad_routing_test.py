"""The SHIPPED `freecad` mapping entry routes each reported workbench correctly.

Drives `polyhost/res/overlay-mapping.poly.yaml`. What it pins:

* each `freecad://<workbench>` the add-on (freecad-addon/) sends lands on that
  workbench's set, and a workbench without its own set on the global set;
* no report (or a stale one, which `current_url` turns into None) keeps the
  fallback set, which has the keys of every workbench;
* a workbench set REPLACES the fallback (`layer: false`), on every `os:` branch;
* the entry's names are exactly the host's context-reporter allow-list;
* every file it names exists, and the largest set stays far under the 600-image limit.
"""
import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import CONTEXT_REPORTERS, BrowserUrlProvider
from polyhost.handler.common import find_matching_entry
from tests.handler.blender_routing_test import _overlay_handler_class

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
KEY = "freecad,org.freecad.freecad"
SETS = ("sketcher", "draft", "bim", "techdraw", "assembly", "spreadsheet")


def _first(entry):
    ov = entry["overlay"]
    return str(ov[0] if isinstance(ov, list) else ov)


def _files(e):
    ov = e.get("overlay", [])
    yield from (ov if isinstance(ov, list) else [ov])
    for sub in ("urls-contains", "os"):
        for child in (e.get(sub) or {}).values():
            yield from _files(child)


class FreecadMappingFileTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertIn(KEY, self.raw)
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "freecad"})

    def test_every_named_file_exists(self):
        files = list(_files(self.raw[KEY]))
        self.assertGreater(len(files), 40)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])

    def test_every_level_opts_out_of_layering(self):
        e = self.raw[KEY]
        for level in (e, e["os"]["macos"], e["os"]["linux"]):
            self.assertIs(level["layer"], False)
            self.assertEqual(len(level["urls-contains"]), len(SETS) + 1)

    def test_no_set_comes_near_the_image_limit(self):
        # One switch shows at most 600 distinct images (OVERLAY_POOL_CAPACITY);
        # a set has at most one image per binding.
        src = RES / "overlay_sources" / "freecad"
        for spec in sorted(src.glob("bindings*.yaml")):
            n = len(yaml.safe_load(spec.read_text(encoding="utf-8"))["bindings"])
            self.assertLess(n, 600, spec.name)


class FreecadRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        handler = _overlay_handler_class()(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.entry = handler.mapping["freecad"]
        assert handler.mapping["org.freecad.freecad"] is cls.entry

    def _route(self, url, os_name="windows"):
        return _first(find_matching_entry("FreeCAD", self.entry, url, os_name))

    def test_each_workbench_gets_its_set(self):
        for wb in SETS:
            for os_name, suffix in (("windows", ""), ("linux", "_linux"), ("macos", "_mac")):
                self.assertEqual(self._route(f"freecad://{wb}", os_name),
                                 f"freecad_{wb}_template{suffix}.mods.png", (wb, os_name))

    def test_other_workbenches_get_the_global_set(self):
        for url in ("freecad://partdesign", "freecad://part", "freecad://other",
                    "freecad://none"):
            self.assertEqual(self._route(url), "freecad_global_template.mods.png", url)
        self.assertEqual(self._route("freecad://part", "macos"),
                         "freecad_global_template_mac.mods.png")

    def test_no_report_keeps_the_fallback(self):
        self.assertEqual(self._route(None), "freecad_template.mods.png")
        self.assertEqual(self._route(None, "linux"), "freecad_template_linux.mods.png")
        self.assertEqual(self._route(None, "macos"), "freecad_template_mac.mods.png")

    def test_a_workbench_replaces_the_fallback(self):
        got = find_matching_entry("FreeCAD", self.entry, "freecad://sketcher", "linux")
        self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])
        self.assertNotIn("freecad_template_linux.mods.png", [str(f) for f in got["overlay"]])


class FreecadReportTest(unittest.TestCase):
    """A report reaches FreeCAD only, and only while fresh and focused."""

    def setUp(self):
        self.now = [100.0]
        self.p = BrowserUrlProvider(clock=lambda: self.now[0], macos_lookup=lambda a: None)

    def test_report_answers_for_freecad_only(self):
        self.p.update(app="freecad", url="freecad://bim", pid=5, input_age=0.0)
        self.assertEqual(self.p.current_url("freecad"), "freecad://bim")
        self.assertEqual(self.p.current_url("org.freecad.FreeCAD"), "freecad://bim")
        self.assertIsNone(self.p.current_url("blender"))
        self.now[0] += 20
        self.assertIsNone(self.p.current_url("freecad"))

    def test_the_instance_in_front_wins(self):
        self.p.update(app="freecad", url="freecad://bim", pid=5, input_age=0.0)
        self.now[0] += 1
        self.p.update(app="freecad", url="freecad://sketcher", pid=6, input_age=0.0)
        self.p.update(app="freecad", url="freecad://bim", pid=5, focused=False, input_age=1.0)
        self.assertEqual(self.p.current_url("freecad"), "freecad://sketcher")


if __name__ == "__main__":
    unittest.main()
