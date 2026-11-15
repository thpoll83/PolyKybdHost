"""The SHIPPED `binaryninja` mapping entry routes each reported view correctly.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* `binaryninja://linear/...` takes the Linear set and `binaryninja://hex` the
  Hex set, at every IL level; `binaryninja://console` and `binaryninja://xrefs`
  (Qt focus in the scripting console or a cross-references pane) take their
  own sets;
* Graph view, the other views and no report keep the main set;
* a view's set REPLACES the main one (`layer: false`);
* macOS takes the `_mac` sets;
* the entry's names are exactly the host's context-reporter allow-list;
* every file it names exists, and the derived binding files are current;
* a report reaches the overlay through `BrowserUrlProvider`, and only while
  Binary Ninja is the app asking.
"""

import subprocess
import sys
import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import CONTEXT_REPORTERS, BrowserUrlProvider
from polyhost.handler.common import find_matching_entry

from tests.handler.blender_routing_test import _overlay_handler_class

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
KEY = "binaryninja,binary ninja"

MAIN = "binaryninja_template.mods.png"
LINEAR = "binaryninja_linear_template.mods.png"
HEX = "binaryninja_hex_template.mods.png"
CONSOLE = "binaryninja_console_template.mods.png"
XREFS = "binaryninja_xrefs_template.mods.png"


def _first(entry):
    ov = entry["overlay"]
    return str(ov[0] if isinstance(ov, list) else ov)


class BinaryNinjaMappingFileTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertIn(KEY, self.raw)
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "binaryninja"})

    def test_every_named_file_exists(self):
        def walk(e):
            ov = e.get("overlay", [])
            for f in (ov if isinstance(ov, list) else [ov]):
                yield f
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from walk(child)
        files = list(walk(self.raw[KEY]))
        self.assertGreaterEqual(len(files), 15)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])

    def test_both_levels_opt_out_of_layering(self):
        self.assertIs(self.raw[KEY]["layer"], False)
        self.assertIs(self.raw[KEY]["os"]["macos"]["layer"], False)

    def test_derived_binding_files_are_current(self):
        gen = RES / "overlay_sources" / "binaryninja" / "gen_view_sets.py"
        r = subprocess.run([sys.executable, str(gen), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class BinaryNinjaRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        handler = _overlay_handler_class()(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.entry = handler.mapping["binaryninja"]
        cls.raw_entry = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))[KEY]
        assert handler.mapping["binary ninja"] is cls.entry

    def _route(self, url, os_name="linux"):
        return _first(find_matching_entry("binaryninja", self.entry, url, os_name))

    def test_each_view_gets_its_overlay(self):
        cases = {
            "binaryninja://linear": LINEAR,
            "binaryninja://linear/disasm": LINEAR,
            "binaryninja://linear/hlil": LINEAR,
            "binaryninja://linear/pseudo_c": LINEAR,
            "binaryninja://hex": HEX,
            "binaryninja://console": CONSOLE,
            "binaryninja://xrefs": XREFS,
            "binaryninja://graph/disasm": MAIN,
            "binaryninja://graph/mlil_ssa": MAIN,
            "binaryninja://triage": MAIN,
            "binaryninja://bytes": MAIN,
            "binaryninja://other": MAIN,
        }
        for url, want in cases.items():
            self.assertEqual(self._route(url), want, url)
            self.assertEqual(self._route(url, "windows"), want, url)

    def test_no_report_is_the_main_set(self):
        self.assertEqual(self._route(None), MAIN)
        self.assertEqual(self._route(None, "windows"), MAIN)
        self.assertEqual(self._route(None, "macos"), "binaryninja_template_mac.mods.png")

    def test_console_and_xrefs_sets(self):
        for os_name in ("linux", "windows"):
            self.assertEqual(self._route("binaryninja://console", os_name), CONSOLE)
            self.assertEqual(self._route("binaryninja://xrefs", os_name), XREFS)
        self.assertEqual(self._route("binaryninja://console", "macos"),
                         "binaryninja_console_template_mac.mods.png")
        self.assertEqual(self._route("binaryninja://xrefs", "macos"),
                         "binaryninja_xrefs_template_mac.mods.png")
        for url in ("binaryninja://console", "binaryninja://xrefs"):
            for os_name in ("linux", "macos"):
                got = find_matching_entry("binaryninja", self.entry, url, os_name)
                names = [str(f) for f in got["overlay"]]
                self.assertFalse([n for n in names if n.startswith("binaryninja_template")],
                                 (url, os_name, names))

    def test_needles_are_longest_first(self):
        for branch in (self.raw_entry, self.raw_entry["os"]["macos"]):
            needles = list(branch["urls-contains"])
            self.assertEqual(needles, sorted(needles, key=len, reverse=True))

    def test_graph_zoom_keys_only_in_the_main_set(self):
        src = RES / "overlay_sources" / "binaryninja"
        sigs = {}
        for name in ("bindings", "bindings_linear", "bindings_hex",
                     "bindings_console", "bindings_xrefs"):
            spec = yaml.safe_load((src / f"{name}.yaml").read_text(encoding="utf-8"))
            sigs[name] = {(str(b["key"]), tuple(b.get("mods") or ())) for b in spec["bindings"]}
        for key in (("W", ()), ("Z", ())):
            self.assertIn(key, sigs["bindings"])
            for name in ("bindings_linear", "bindings_hex", "bindings_console",
                         "bindings_xrefs"):
                self.assertNotIn(key, sigs[name], name)
        # The console and the xrefs pane draw no plain letter.
        for name in ("bindings_console", "bindings_xrefs"):
            plain = [k for k, m in sigs[name] if len(k) == 1 and k.isalpha()
                     and not set(m) & {"CMDCTRL", "CTRL", "ALT", "GUI"}]
            self.assertEqual(plain, [], name)
        # Esc stays the program mark.
        for name in sigs:
            self.assertFalse([k for k, _m in sigs[name] if k.upper() in ("ESC", "ESCAPE")])

    def test_a_view_replaces_the_main_set(self):
        got = find_matching_entry("binaryninja", self.entry, "binaryninja://hex", "linux")
        names = [str(f) for f in got["overlay"]]
        self.assertNotIn(MAIN, names)
        self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])

    def test_macos_takes_the_mac_sets(self):
        self.assertEqual(self._route("binaryninja://hex", "macos"),
                         "binaryninja_hex_template_mac.mods.png")
        self.assertEqual(self._route("binaryninja://linear/hlil", "macos"),
                         "binaryninja_linear_template_mac.mods.png")
        self.assertEqual(self._route("binaryninja://graph/hlil", "macos"),
                         "binaryninja_template_mac.mods.png")

    def test_report_to_overlay_through_the_provider(self):
        p = BrowserUrlProvider(macos_lookup=lambda app: None)
        p.update(app="binaryninja", url="binaryninja://hex", focused=True, pid=7,
                 input_age=0.0)
        for app in ("binaryninja", "Binary Ninja", "binaryninja.exe"):
            self.assertEqual(p.current_url(app), "binaryninja://hex", app)
            self.assertEqual(self._route(p.current_url(app)), HEX, app)
        # A report never reaches another app.
        self.assertIsNone(p.current_url("blender"))
        self.assertIsNone(p.current_url("code"))
        # The withdrawal (plugin turned off, Binary Ninja closing): main set.
        p.update(app="binaryninja", url=None, focused=False, pid=7)
        self.assertIsNone(p.current_url("binaryninja"))
        self.assertEqual(self._route(p.current_url("binaryninja")), MAIN)

    def test_console_report_through_the_provider(self):
        p = BrowserUrlProvider(macos_lookup=lambda app: None)
        for url, want in (("binaryninja://console", CONSOLE), ("binaryninja://xrefs", XREFS)):
            p.update(app="binaryninja", url=url, focused=True, pid=7, input_age=0.0)
            self.assertEqual(p.current_url("Binary Ninja"), url)
            self.assertEqual(self._route(p.current_url("Binary Ninja")), want)


if __name__ == "__main__":
    unittest.main()
