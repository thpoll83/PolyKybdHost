"""The SHIPPED `ida` mapping entry routes each view the IDA plugin reports.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself, like
blender_routing_test. What it pins:

* every `ida://<view>` the plugin (ida-plugin/) can send lands on its set:
  pseudocode, disassembly (text, graph, proximity) and hex, the rest `global`;
* no report keeps the `ida_template` fallback, and a view's set replaces it
  (`layer: false`) on every OS branch;
* the entry's names are exactly the host's `CONTEXT_REPORTERS` "ida" names,
  and the macOS name with a version still finds the reporter;
* a report is taken from the provider only while IDA is the focused app;
* the generated view specs are current, and every named file exists.
"""

import importlib.util
import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import CONTEXT_REPORTERS, BrowserUrlProvider, context_reporter_for
from polyhost.handler.common import find_matching_entry
from tests.handler.blender_routing_test import _overlay_handler_class

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
KEY = "ida,ida64,idaq,idaq64,ida pro,ida professional,ida home,ida free,ida classroom"
GEN_VIEWS = RES / "overlay_sources" / "ida" / "gen_views.py"


def _first(entry):
    ov = entry["overlay"]
    return str(ov[0] if isinstance(ov, list) else ov)


class IdaMappingFileTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertIn(KEY, self.raw)
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "ida"})

    def test_reporter_found_for_each_reported_name(self):
        for name in ("ida", "ida.exe", "IDA64.exe", "IDA Professional 9.1", "ida pro 9.0",
                     "IDA Home 9.2", "ida free"):
            self.assertEqual(context_reporter_for(name), "ida", name)
        self.assertIsNone(context_reporter_for("idapython"))

    def test_both_levels_opt_out_of_layering(self):
        self.assertIs(self.raw[KEY]["layer"], False)
        self.assertIs(self.raw[KEY]["os"]["macos"]["layer"], False)

    def test_every_named_file_exists(self):
        def walk(e):
            ov = e.get("overlay", [])
            yield from (ov if isinstance(ov, list) else [ov])
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from walk(child)
        files = list(walk(self.raw[KEY]))
        self.assertGreater(len(files), 20)
        self.assertEqual([f for f in files if not (RES / "overlays" / f).is_file()], [])

    def test_the_generated_view_specs_are_current(self):
        spec = importlib.util.spec_from_file_location("ida_gen_views", GEN_VIEWS)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.main(["--check"]), 0)


class IdaRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        handler = _overlay_handler_class()(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.entry = handler.mapping["ida"]
        assert handler.mapping["ida professional"] is cls.entry

    def _route(self, url, os_name="windows"):
        return _first(find_matching_entry("ida", self.entry, url, os_name))

    def test_each_view_gets_its_overlay(self):
        cases = {
            "ida://pseudocode": "ida_pseudocode_template.mods.png",
            "ida://disasm/text": "ida_disasm_template.mods.png",
            "ida://disasm/graph": "ida_disasm_template.mods.png",
            "ida://disasm/proximity": "ida_disasm_template.mods.png",
            "ida://hex": "ida_disasm_template.mods.png",
            "ida://types": "ida_global_template.mods.png",
            "ida://list": "ida_global_template.mods.png",
            "ida://output": "ida_global_template.mods.png",
            "ida://cli": "ida_global_template.mods.png",
            "ida://other": "ida_global_template.mods.png",
        }
        for os_name in ("windows", "linux"):
            for url, want in cases.items():
                self.assertEqual(self._route(url, os_name), want, (os_name, url))

    def test_no_report_is_the_fallback(self):
        self.assertEqual(self._route(None), "ida_template.mods.png")
        self.assertEqual(self._route(None, "macos"), "ida_template_mac.mods.png")

    def test_a_view_replaces_the_fallback(self):
        for os_name in ("windows", "macos"):
            got = find_matching_entry("ida", self.entry, "ida://pseudocode", os_name)
            names = [str(f) for f in got["overlay"]]
            self.assertFalse([n for n in names if n.startswith("ida_template")], names)
            self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])

    def test_macos_takes_the_mac_sets(self):
        self.assertEqual(self._route("ida://pseudocode", "macos"),
                         "ida_pseudocode_template_mac.mods.png")
        self.assertEqual(self._route("ida://disasm/graph", "macos"),
                         "ida_disasm_template_mac.mods.png")
        self.assertEqual(self._route("ida://list", "macos"), "ida_global_template_mac.mods.png")


class IdaReportProviderTest(unittest.TestCase):
    """The provider hands IDA its own fresh report, and nobody else."""

    def setUp(self):
        self.now = [1000.0]
        self.p = BrowserUrlProvider(clock=lambda: self.now[0])

    def test_report_reaches_ida_only(self):
        self.assertTrue(self.p.update(app="ida", url="ida://pseudocode", pid=1, input_age=0.1))
        self.assertEqual(self.p.current_url("ida"), "ida://pseudocode")
        self.assertEqual(self.p.current_url("IDA Professional 9.1"), "ida://pseudocode")
        self.assertIsNone(self.p.current_url("blender"))
        self.assertIsNone(self.p.current_url("notepad"))

    def test_stale_or_withdrawn_report_keeps_the_fallback(self):
        self.p.update(app="ida", url="ida://hex", pid=1)
        self.now[0] += 100
        self.assertIsNone(self.p.current_url("ida"))
        self.p.update(app="ida", url="ida://hex", pid=1)
        self.p.update(app="ida", url=None, focused=False, pid=1)
        self.assertIsNone(self.p.current_url("ida"))


if __name__ == "__main__":
    unittest.main()
