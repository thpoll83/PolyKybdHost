"""The SHIPPED `qgis` mapping entry routes each mode the QGIS plugin reports.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* every URL the plugin's core can build lands on that mode's overlay set, on
  Windows, Linux and macOS (the digitizing and vertex sets, with and without
  Advanced Digitizing, and the print layout set);
* no report, and every other tool or window, keeps the main set;
* a mode set REPLACES the main set (`layer: false`);
* the entry's names are exactly the host's context-reporter allow-list, and a
  report from the plugin is used while QGIS is focused;
* every file it names exists, and the generated mode specs are not stale.
"""

import importlib.util
import itertools
import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import CONTEXT_REPORTERS, BrowserUrlProvider
from polyhost.handler.common import find_matching_entry

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
KEY = "qgis,qgis3,qgis4,org.qgis.qgis,qgis-bin,qgis-ltr-bin,qgis-dev-bin,qgis-qt6-bin,qgis-ltr"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = _load(ROOT / "qgis-plugin" / "polykybd_context_reporter" / "core.py",
             "polykybd_qgis_reporter_core_routing")


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (as in blender_routing_test)."""
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


def _first(entry):
    ov = entry["overlay"]
    return str(ov[0] if isinstance(ov, list) else ov)


def _expected(url, os_name):
    """The main-set stem a URL should load, from the plugin's own tokens."""
    suffix = {"windows": "", "linux": "_linux", "macos": "_mac"}[os_name]
    if url == "qgis://layout":
        return "qgis_layout_template" + ("_mac" if os_name == "macos" else "")
    if url and url.startswith("qgis://map/"):
        parts = url[len("qgis://map/"):].split("/")
        if parts[0] in core.CAD_TOOLS:
            cad = "_cad" if "cad" in parts else ""
            return f"qgis_{parts[0]}{cad}_template{suffix}"
    return "qgis_template" + suffix


def _all_urls():
    urls = {core.context_url(w) for w in ("layout", "dialog")}
    for tool, editing, cad in itertools.product(sorted(core.TOOLS), (False, True), (False, True)):
        urls.add(core.context_url("map", tool, editing, cad))
    return sorted(urls)


class QgisMappingFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertIn(KEY, self.raw)
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "qgis"})

    def test_every_named_file_exists(self):
        def walk(e):
            ov = e.get("overlay", [])
            for f in (ov if isinstance(ov, list) else [ov]):
                yield f
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from walk(child)
        files = list(walk(self.raw[KEY]))
        self.assertGreater(len(files), 40)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])

    def test_every_level_opts_out_of_layering(self):
        self.assertIs(self.raw[KEY]["layer"], False)
        for os_name in ("macos", "linux"):
            self.assertIs(self.raw[KEY]["os"][os_name]["layer"], False, os_name)

    def test_generated_mode_specs_are_current(self):
        gen = _load(RES / "overlay_sources" / "qgis" / "gen_mode_specs.py", "qgis_gen_mode_specs")
        self.assertEqual(gen.main(["--check"]), 0)


class QgisModeRoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = _overlay_handler_class()(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.entry = handler.mapping["qgis"]
        assert handler.mapping["qgis-bin"] is cls.entry

    def _route(self, url, os_name):
        return _first(find_matching_entry("QGIS", self.entry, url, os_name))

    def test_each_mode_gets_its_overlay_on_every_os(self):
        for os_name in ("windows", "linux", "macos"):
            for url in _all_urls():
                with self.subTest(os=os_name, url=url):
                    self.assertEqual(self._route(url, os_name),
                                     _expected(url, os_name) + ".mods.png")

    def test_the_mode_sets_are_used(self):
        # Guard against _expected() and the mapping agreeing on the fallback only.
        self.assertEqual(self._route("qgis://map/vertex/cad/edit", "windows"),
                         "qgis_vertex_cad_template.mods.png")
        self.assertEqual(self._route("qgis://map/digitize/edit", "linux"),
                         "qgis_digitize_template_linux.mods.png")
        self.assertEqual(self._route("qgis://layout", "macos"),
                         "qgis_layout_template_mac.mods.png")

    def test_no_report_is_the_main_set(self):
        for os_name, want in (("windows", "qgis_template"), ("linux", "qgis_template_linux"),
                              ("macos", "qgis_template_mac")):
            self.assertEqual(self._route(None, os_name), want + ".mods.png")

    def test_a_mode_replaces_the_main_set(self):
        got = find_matching_entry("QGIS", self.entry, "qgis://map/digitize/cad/edit", "linux")
        names = [str(f) for f in got["overlay"]]
        self.assertFalse([n for n in names if n.startswith("qgis_template")], names)
        self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])


class QgisReportTest(unittest.TestCase):
    def test_report_is_used_only_while_qgis_is_focused(self):
        p = BrowserUrlProvider(max_age_s=8.0, macos_lookup=lambda app: None)
        url = core.context_url("map", "vertex", True, False)
        self.assertTrue(p.update(app="qgis", url=url, focused=True, pid=7, input_age=0.0))
        for name in ("qgis", "QGIS4", "qgis-bin.exe", "org.qgis.qgis"):
            self.assertEqual(p.current_url(name), url, name)
        self.assertIsNone(p.current_url("blender"))
        p.update(app="qgis", url=None, focused=False, pid=7)
        self.assertIsNone(p.current_url("qgis"))


if __name__ == "__main__":
    unittest.main()
