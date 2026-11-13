"""The SHIPPED JetBrains mapping entry routes the plugin's `jetbrains://` reports.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* each window/debug state the plugin (`jetbrains-plugin/`) can send lands on the
  overlay for that mode: Terminal, a paused debug session, Project, and every
  other report on the editor set; on every `os:` branch of the entry;
* no report (or a stale one, which `current_url` turns into None) keeps the
  full fallback set the entry had before the plugin existed;
* a mode REPLACES the fallback (`layer: false`) on the entry and every branch;
* the entry's names are exactly the host's "jetbrains" context reporters, and a
  report from the plugin reaches `current_url` for those names only;
* the window tokens the routes need are the ones the plugin's `ReportCore.kt`
  sends, every file named exists, and the derived binding files are current.
"""

import importlib.util
import re
import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import CONTEXT_REPORTERS, BrowserUrlProvider
from polyhost.handler.common import find_matching_entry

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
SOURCES = RES / "overlay_sources" / "jetbrains"
CORE_KT = (ROOT / "jetbrains-plugin" / "src" / "main" / "kotlin" / "org" / "polykybd"
           / "reporter" / "ReportCore.kt")
NAMES = {n for n, t in CONTEXT_REPORTERS.items() if t == "jetbrains"}


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as blender_routing_test)."""
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


def _entry_key(raw):
    keys = [k for k in raw if isinstance(k, str) and k.startswith("idea64,")]
    assert len(keys) == 1, keys
    return keys[0]


class JetBrainsMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML and the plugin source; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        cls.key = _entry_key(cls.raw)
        cls.entry = cls.raw[cls.key]

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertEqual(set(self.key.split(",")), NAMES)

    def test_every_level_opts_out_of_layering(self):
        self.assertIs(self.entry["layer"], False)
        for name, branch in self.entry["os"].items():
            self.assertIs(branch["layer"], False, name)
            self.assertEqual(list(branch["urls-contains"]), list(self.entry["urls-contains"]), name)

    def test_every_named_file_exists(self):
        def walk(e):
            ov = e.get("overlay", [])
            yield from (ov if isinstance(ov, list) else [ov])
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from walk(child)
        files = list(walk(self.entry))
        self.assertGreater(len(files), 60)
        self.assertEqual([f for f in files if not (RES / "overlays" / f).is_file()], [])

    def test_routes_use_the_tokens_the_plugin_sends(self):
        src = CORE_KT.read_text(encoding="utf-8")
        tokens = set(re.findall(r'"[^"]+" to "([a-z]+)"', src)) | {"editor", "other"}
        self.assertIn('const val APP = "jetbrains"', src)
        self.assertIn('PAUSED("/paused")', src)
        for needle in self.entry["urls-contains"]:
            if needle.startswith("jetbrains://") and needle != "jetbrains://":
                self.assertIn(needle[len("jetbrains://"):], tokens, needle)

    def test_derived_binding_files_are_current(self):
        spec = importlib.util.spec_from_file_location("jb_gen_mode_specs",
                                                      SOURCES / "gen_mode_specs.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.main(["--check"]), 0)


class JetBrainsRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        handler = _overlay_handler_class()(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.entry = handler.mapping["idea64"]
        assert handler.mapping["pycharm"] is cls.entry

    def _route(self, url, os_name):
        m = find_matching_entry("main.py - PyCharm", self.entry, url, os_name)
        ov = m["overlay"]
        return [str(f) for f in (ov if isinstance(ov, list) else [ov])]

    # (os_name, fallback stem, editor, debug, project, terminal)
    CASES = (
        ("windows", "jetbrains_template", "jetbrains_editor_template",
         "jetbrains_debug_template", "jetbrains_project_template", "jetbrains_terminal_template"),
        ("macos", "jetbrains_mac_template", "jetbrains_editor_mac_template",
         "jetbrains_debug_mac_template", "jetbrains_project_mac_template",
         "jetbrains_terminal_mac_template"),
        ("linux", "jetbrains_linux_template", "jetbrains_editor_linux_template",
         "jetbrains_debug_linux_template", "jetbrains_project_linux_template",
         "jetbrains_terminal_linux_template"),
        ("linux_gnome", "jetbrains_gnome_template", "jetbrains_editor_gnome_template",
         "jetbrains_debug_gnome_template", "jetbrains_project_linux_template",
         "jetbrains_terminal_linux_template"),
        ("linux_kde", "jetbrains_kde_template", "jetbrains_editor_kde_template",
         "jetbrains_debug_kde_template", "jetbrains_project_linux_template",
         "jetbrains_terminal_kde_template"),
    )

    def test_each_mode_gets_its_overlay_on_every_platform(self):
        for os_name, fallback, editor, debug, project, terminal in self.CASES:
            cases = {
                None: fallback,
                "jetbrains://editor": editor,
                "jetbrains://editor/running": editor,
                "jetbrains://run": editor,
                "jetbrains://git": editor,
                "jetbrains://other": editor,
                "jetbrains://editor/paused": debug,
                "jetbrains://debug/paused": debug,
                "jetbrains://project/paused": debug,
                "jetbrains://project": project,
                "jetbrains://project/running": project,
                "jetbrains://terminal": terminal,
                "jetbrains://terminal/paused": terminal,
            }
            for url, stem in cases.items():
                with self.subTest(os=os_name, url=url):
                    files = self._route(url, os_name)
                    self.assertEqual(files[0], f"{stem}.mods.png")
                    # Replaced, not layered: no file of another set in the list.
                    self.assertTrue(all(f.startswith(stem + ".") for f in files), files)


class JetBrainsReportTest(unittest.TestCase):
    """A plugin report reaches the JetBrains window, and only that window."""

    def setUp(self):
        self.t = 1000.0
        self.p = BrowserUrlProvider(max_age_s=8.0, clock=lambda: self.t,
                                    macos_lookup=lambda app: None)

    def test_report_answers_for_every_ide_name(self):
        self.p.update(app="jetbrains", url="jetbrains://editor/paused", focused=True,
                      pid=4242, input_age=0.3)
        for name in ("idea64", "PyCharm64.exe", "jetbrains-clion", "IntelliJ IDEA",
                     "Android Studio"):
            self.assertEqual(self.p.current_url(name), "jetbrains://editor/paused", name)
        self.assertIsNone(self.p.current_url("code"))
        self.assertIsNone(self.p.current_url("blender"))

    def test_withdrawal_and_staleness_fall_back(self):
        self.p.update(app="jetbrains", url="jetbrains://project", pid=7)
        self.p.update(app="jetbrains", url=None, focused=False, pid=7)
        self.assertIsNone(self.p.current_url("idea64"))
        self.p.update(app="jetbrains", url="jetbrains://project", pid=7)
        self.t += 9.0
        self.assertIsNone(self.p.current_url("idea64"))

    def test_the_ide_with_the_newest_input_wins(self):
        self.p.update(app="jetbrains", url="jetbrains://terminal", pid=1, input_age=30.0)
        self.p.update(app="jetbrains", url="jetbrains://project", pid=2, input_age=0.1)
        self.assertEqual(self.p.current_url("pycharm64"), "jetbrains://project")


if __name__ == "__main__":
    unittest.main()
