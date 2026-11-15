"""The SHIPPED `maya,maya.bin` entry routes each panel the Maya plug-in reports.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* `maya://<panel>/<selection mode>` for the Graph Editor, Time Editor, UV
  Editor, Node Editor and Hypershade loads that panel's set, in either
  selection mode, on Windows, Linux and macOS (the `_mac` sets);
* a viewport, the Outliner, the Dope Sheet, `other`, and no report keep the
  viewport set;
* a panel set REPLACES the viewport set (`layer: false` on the entry and on its
  macOS branch);
* the entry's names are exactly the `maya` names of the host's context-reporter
  allow-list, and the provider hands a fresh `maya://` report to Maya, also when
  macOS names the app with its release year, and to no other app;
* every file the entry names exists.

The plug-in itself is not run here (tests/maya_plugin/ covers its Maya-free
half); none of this was checked with a running Maya.
"""
import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import CONTEXT_REPORTERS, BrowserUrlProvider
from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
KEY = "maya,maya.bin"
PANELS = ("graph", "timeeditor", "uv", "node", "hypershade")


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as maya_routing_test)."""
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}") from e
    except Exception as e:
        if not ((isinstance(e, ModuleNotFoundError)
                 and not (e.name or "").startswith("polyhost"))
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}") from e
    return OverlayHandler


def _first(entry):
    ov = entry["overlay"]
    return str(ov[0] if isinstance(ov, list) else ov)


class MayaModeMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertIn(KEY, self.raw)
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "maya"})

    def test_both_levels_opt_out_of_layering(self):
        self.assertIs(self.raw[KEY]["layer"], False)
        self.assertIs(self.raw[KEY]["os"]["macos"]["layer"], False)

    def test_every_os_branch_routes_every_panel(self):
        for level in (self.raw[KEY], self.raw[KEY]["os"]["macos"]):
            self.assertEqual(set(level["urls-contains"]),
                             {f"maya://{p}/" for p in PANELS})

    def test_every_named_file_exists(self):
        def walk(e):
            ov = e.get("overlay", [])
            yield from (ov if isinstance(ov, list) else [ov])
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from walk(child)
        files = list(walk(self.raw[KEY]))
        self.assertGreaterEqual(len(files), 30)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


class MayaModeRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, url, os_name):
        entry = self.mapping[mapping_key(app, self.mapping)]
        return _first(find_matching_entry("Untitled", entry, url, os_name))

    def test_each_panel_gets_its_set(self):
        for os_name, app, sfx in (("windows", "maya", ""), ("linux", "maya.bin", ""),
                                  ("macos", "maya", "_mac"), ("macos", "maya 2026", "_mac")):
            for panel in PANELS:
                for mode in ("object", "component"):
                    url = f"maya://{panel}/{mode}"
                    with self.subTest(os=os_name, app=app, url=url):
                        self.assertEqual(self._route(app, url, os_name),
                                         f"maya_{panel}_template{sfx}.mods.png")

    def test_other_panels_and_no_report_keep_the_viewport_set(self):
        for os_name, sfx in (("windows", ""), ("linux", ""), ("macos", "_mac")):
            for url in (None, "maya://model/object", "maya://model/component",
                        "maya://outliner/object", "maya://dopesheet/object",
                        "maya://other/other"):
                with self.subTest(os=os_name, url=url):
                    self.assertEqual(self._route("maya", url, os_name),
                                     f"maya_template{sfx}.mods.png")

    def test_a_panel_set_replaces_the_viewport_set(self):
        for os_name in ("windows", "macos"):
            entry = self.mapping["maya"]
            got = find_matching_entry("Untitled", entry, "maya://graph/object", os_name)
            names = [str(f) for f in got["overlay"]]
            self.assertFalse([n for n in names if n.startswith("maya_template")], names)
            self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])


class MayaReportProviderTest(unittest.TestCase):
    """The provider gives the plug-in's report to Maya only."""

    def setUp(self):
        self.now = [100.0]
        self.p = BrowserUrlProvider(clock=lambda: self.now[0], macos_lookup=lambda _a: None)

    def test_report_reaches_maya(self):
        self.assertTrue(self.p.update(app="maya", url="maya://uv/component", pid=7,
                                      input_age=0.0))
        for name in ("maya", "maya.exe", "Maya", "maya.bin", "maya 2026"):
            self.assertEqual(self.p.current_url(name), "maya://uv/component", name)

    def test_report_never_reaches_another_app(self):
        self.p.update(app="maya", url="maya://graph/object", pid=7)
        for name in ("blender", "google-chrome", "mayan", "3dsmax"):
            self.assertIsNone(self.p.current_url(name), name)

    def test_stale_or_withdrawn_report_is_dropped(self):
        self.p.update(app="maya", url="maya://graph/object", pid=7)
        self.now[0] += 9.0
        self.assertIsNone(self.p.current_url("maya"))
        self.p.update(app="maya", url="maya://graph/object", pid=7)
        self.p.update(app="maya", url=None, focused=False, pid=7)
        self.assertIsNone(self.p.current_url("maya"))


if __name__ == "__main__":
    unittest.main()
