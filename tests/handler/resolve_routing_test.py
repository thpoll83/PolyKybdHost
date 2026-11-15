"""The SHIPPED `resolve,davinci resolve` mapping entry routes each page report.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* every `resolve://<page>` the page reporter (resolve-plugin/) can send lands
  on that page's set, on Windows/Linux and on macOS;
* no report (or a stale one, which `current_url` turns into None) and an
  unknown page keep the fallback set;
* a page REPLACES the fallback (`layer: false`);
* the entry's names are exactly the host's context-reporter allow-list;
* every file it names exists, and the per-page specs match pages.yaml.
"""

import importlib.util
import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import (
    CONTEXT_REPORTERS, DEFAULT_MAX_AGE_S, BrowserUrlProvider, context_reporter_for)
from polyhost.handler.common import find_matching_entry


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here.

    Imported lazily so the file-level checks above it still run without a
    display. Tolerated, as in hosted_app_routing_test: a missing dependency,
    Xlib refusing a missing display -- and `SystemExit`, which is what pymonctl
    raises at import when Xorg/xrandr are absent (it calls `sys.exit(1)`).
    Anything else is a real regression and propagates."""
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


RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
KEY = "resolve,davinci resolve"
PAGES = ("media", "cut", "edit", "fusion", "color", "fairlight", "deliver")


def _first(entry):
    ov = entry["overlay"]
    return str(ov[0] if isinstance(ov, list) else ov)


class ResolveMappingFileTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "resolve"})
        for name in ("Resolve.exe", "resolve", "DaVinci Resolve"):
            self.assertEqual(context_reporter_for(name), "resolve", name)

    def test_every_named_file_exists(self):
        def walk(e):
            ov = e.get("overlay", [])
            yield from (ov if isinstance(ov, list) else [ov])
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from walk(child)
        files = list(walk(self.raw[KEY]))
        self.assertEqual(len(files), 2 + 3 + 7 * (2 + 3))
        self.assertEqual([f for f in files if not (RES / "overlays" / f).is_file()], [])

    def test_both_levels_opt_out_of_layering(self):
        self.assertIs(self.raw[KEY]["layer"], False)
        self.assertIs(self.raw[KEY]["os"]["macos"]["layer"], False)

    def test_page_specs_are_generated_from_pages_yaml(self):
        path = RES / "overlay_sources" / "resolve" / "gen_pages.py"
        spec = importlib.util.spec_from_file_location("resolve_gen_pages", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.main(["--check"]), 0)


class ResolveReportTest(unittest.TestCase):
    """A page report reaches Resolve, and only Resolve, while it is fresh."""

    def setUp(self):
        self.now = 100.0
        self.p = BrowserUrlProvider(clock=lambda: self.now, macos_lookup=lambda _a: None)

    def test_report_answers_for_resolve_only(self):
        self.assertTrue(self.p.update(app="resolve", url="resolve://fusion", pid=5))
        for name in ("Resolve", "resolve.exe", "DaVinci Resolve"):
            self.assertEqual(self.p.current_url(name), "resolve://fusion", name)
        self.assertIsNone(self.p.current_url("blender"))

    def test_stale_or_withdrawn_report_is_no_url(self):
        self.p.update(app="resolve", url="resolve://color", pid=5)
        self.now += DEFAULT_MAX_AGE_S + 1
        self.assertIsNone(self.p.current_url("Resolve"))
        self.p.update(app="resolve", url="resolve://color", pid=5)
        self.p.update(app="resolve", url=None, focused=False, pid=5)
        self.assertIsNone(self.p.current_url("Resolve"))


class ResolveRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        handler = _overlay_handler_class()(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.entry = handler.mapping["resolve"]
        assert handler.mapping["davinci resolve"] is cls.entry

    def _route(self, url, os_name="linux"):
        return _first(find_matching_entry("Resolve", self.entry, url, os_name))

    def test_each_page_gets_its_set(self):
        for page in PAGES:
            self.assertEqual(self._route(f"resolve://{page}"),
                             f"resolve_{page}_template.mods.png", page)
            self.assertEqual(self._route(f"resolve://{page}", "windows"),
                             f"resolve_{page}_template.mods.png", page)

    def test_macos_takes_the_mac_sets(self):
        for page in PAGES:
            self.assertEqual(self._route(f"resolve://{page}", "macos"),
                             f"resolve_{page}_template_mac.mods.png", page)
        self.assertEqual(self._route(None, "macos"), "resolve_template_mac.mods.png")

    def test_no_report_keeps_the_fallback(self):
        self.assertEqual(self._route(None), "resolve_template.mods.png")
        self.assertEqual(self._route("resolve://project"), "resolve_template.mods.png")

    def test_a_page_replaces_the_fallback(self):
        got = find_matching_entry("Resolve", self.entry, "resolve://color", "linux")
        names = [str(f) for f in got["overlay"]]
        self.assertEqual([n for n in names if n.startswith("resolve_template")], [])
        self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])


if __name__ == "__main__":
    unittest.main()
