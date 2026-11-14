"""The SHIPPED Jupyter routing: the JupyterLab Desktop entry and the browser maps.

Drives `polyhost/res/overlay-mapping.poly.yaml` and `BrowserUrlProvider`. What
it pins:

* JupyterLab Desktop with a `jupyter://` report gets that mode's set; with no
  report, the all-modes set (`layer: false`, so a mode replaces it);
* a browser with a fresh, focused JupyterLab page report gets the mode's set on
  top of the browser's own set, before the tab URL; an unfocused or stale
  report gives the tab URL back;
* a Jupyter report never reaches an app that is neither JupyterLab Desktop
  nor a browser, and a web address that only contains the text is not routed;
* the Desktop entry's names are exactly the `jupyter` context reporters;
* every file named exists, and no mode set exceeds the overlay pool;
* the terminal set draws only keys that xterm.js does not send to the shell.
"""

import re
import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import (
    CONTEXT_REPORTERS, PAGE_REPORTERS, BrowserUrlProvider)
from polyhost.handler.common import find_matching_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
DESKTOP = "jupyterlab,jupyterlab-desktop,jupyterlab desktop"
# The handler's mapping is keyed per app name.
CHROME, FIREFOX = "chrome", "firefox"

MODES = {
    "jupyter://notebook/command": "command",
    "jupyter://notebook/edit": "edit",
    "jupyter://editor": "editor",
    "jupyter://console": "console",
    "jupyter://terminal": "terminal",
    "jupyter://other": "global",
}


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _files(entry):
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])]


def _primary(mode, os_name):
    return f"jupyter_{mode}_template{'_mac' if os_name == 'macos' else ''}.mods.png"


def _base(os_name):
    return f"jupyter_template{'_mac' if os_name == 'macos' else ''}.mods.png"


class JupyterMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_desktop_names_are_the_jupyter_context_reporters(self):
        self.assertIn(DESKTOP, self.raw)
        self.assertEqual(set(DESKTOP.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "jupyter"})
        self.assertIn("jupyter", PAGE_REPORTERS)

    def test_desktop_entry_and_its_macos_branch_replace_the_fallback(self):
        e = self.raw[DESKTOP]
        self.assertIs(e["layer"], False)
        self.assertIs(e["os"]["macos"]["layer"], False)
        self.assertEqual(list(e["urls-contains"]), list(e["os"]["macos"]["urls-contains"]))

    def test_every_named_file_exists(self):
        files = set()
        e = self.raw[DESKTOP]
        for branch in (e, e["os"]["macos"]):
            files |= set(_files(branch))
            for sub in branch["urls-contains"].values():
                files |= set(_files(sub))
        self.assertGreaterEqual(len(files), 6 * 5 + 5)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])

    def test_no_mode_set_exceeds_the_overlay_pool(self):
        # One switch shows at most 600 distinct images (OVERLAY_POOL_CAPACITY);
        # a binding line is at most one image.
        src = RES / "overlay_sources" / "jupyter"
        for mode in set(MODES.values()):
            spec = yaml.safe_load((src / f"bindings_{mode}.yaml").read_text(encoding="utf-8"))
            self.assertLess(len(spec["bindings"]), 600, mode)


    def test_terminal_set_draws_only_keys_xterm_lets_through(self):
        # In a terminal, xterm.js sends Ctrl+letter, Alt+key and the F keys to
        # the shell, so on Windows/Linux only the Ctrl+Shift chords, Ctrl+,
        # and the terminal's Ctrl+V paste act. On macOS the F keys are input.
        src = RES / "overlay_sources" / "jupyter"
        spec = yaml.safe_load((src / "bindings_terminal.yaml").read_text(encoding="utf-8"))
        win = [b for b in spec["bindings"] if b.get("except") == ["macos"]]
        mac = [b for b in spec["bindings"] if b.get("only") == ["macos"]]
        self.assertEqual(len(win) + len(mac), len(spec["bindings"]))
        for b in win:
            mods = set(b["mods"])
            ok = (mods == {"CTRL", "SHIFT"}
                  or (mods == {"CTRL"} and b["key"] in ("COMMA", "V")))
            self.assertTrue(ok, b)
        self.assertIn("Paste", {b["label"] for b in win})
        self.assertFalse([b for b in win + mac if re.fullmatch(r"F\d+", str(b["key"]))])
        self.assertNotIn("Paste", {b["label"] for b in mac})
        self.assertIn("Left sidebar", {b["label"] for b in mac})


class JupyterRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            from polyhost.handler.active_window import OverlayHandler
        except SystemExit as e:
            raise unittest.SkipTest(f"window backend exited at import: {e!r}")
        except Exception as e:
            if not (isinstance(e, ModuleNotFoundError)
                    or type(e).__module__.split(".")[0] == "Xlib"):
                raise
            raise unittest.SkipTest(f"active_window needs a display: {e}")
        cls.mapping = OverlayHandler(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, key, url, title="", os_name="linux"):
        key = "jupyterlab" if key == DESKTOP else key
        m = find_matching_entry(title, self.mapping[key], url, os_name)
        return None if m is None else _files(m)

    def test_desktop_routes_each_mode(self):
        for os_name in ("linux", "windows", "macos"):
            for url, mode in MODES.items():
                files = self._route(DESKTOP, url, os_name=os_name)
                self.assertEqual(files[0], _primary(mode, os_name), (url, os_name))
                # layer: false -- the all-modes set is not drawn underneath.
                self.assertNotIn(_base(os_name), files, (url, os_name))

    def test_desktop_without_a_report_keeps_the_all_modes_set(self):
        for os_name in ("linux", "macos"):
            self.assertEqual(self._route(DESKTOP, None, os_name=os_name)[0],
                             _base(os_name))

    def test_browser_routes_each_mode_on_top_of_the_browser(self):
        for key in (CHROME, FIREFOX):
            for os_name in ("linux", "macos"):
                for url, mode in MODES.items():
                    files = self._route(key, url, os_name=os_name)
                    self.assertIn(_primary(mode, os_name), files, (key, url, os_name))
                    # Layered: the browser's own set comes first.
                    self.assertLess(0, files.index(_primary(mode, os_name)))

    def test_browser_tab_url_still_routes_without_a_report(self):
        files = self._route(CHROME, "http://localhost:8888/lab/tree/a.ipynb")
        self.assertIn("jupyter_template.mods.png", files)

    def test_a_web_address_with_the_text_is_not_routed(self):
        files = self._route(CHROME, "https://www.google.com/search?q=jupyter://editor")
        self.assertFalse([f for f in files if f.startswith("jupyter_")])

    def test_report_to_overlay_through_the_provider(self):
        clock = FakeClock()
        p = BrowserUrlProvider(clock=clock, macos_lookup=lambda app: None)
        p.update(browser="chrome", url="http://localhost:8888/lab", focused=True)
        self.assertTrue(p.update(app="jupyter", url="jupyter://notebook/edit",
                                 focused=True, pid=7, input_age=0.0))
        for app, key in (("google-chrome", CHROME), ("jupyterlab", "jupyterlab")):
            self.assertIn(_primary("edit", "linux"), self._route(key, p.current_url(app)), app)
        # Never another app.
        self.assertIsNone(p.current_url("code"))
        self.assertIsNone(p.current_url("kitty"))
        # The page lost focus: the browser's tab URL answers again.
        self.assertTrue(p.update(app="jupyter", url=None, focused=False, pid=7))
        self.assertEqual(p.current_url("google-chrome"), "http://localhost:8888/lab")
        self.assertIsNone(p.current_url("jupyterlab"))



class JupyterProviderTest(unittest.TestCase):
    """The provider alone; no window backend needed."""

    def test_stale_page_report_gives_the_tab_back(self):
        clock = FakeClock()
        p = BrowserUrlProvider(max_age_s=8.0, clock=clock, macos_lookup=lambda app: None)
        p.update(app="jupyter", url="jupyter://console", focused=True, pid=7)
        clock.t += 5
        p.update(browser="firefox", url="https://github.com/", focused=True)
        self.assertEqual(p.current_url("firefox"), "jupyter://console")
        clock.t += 4
        self.assertEqual(p.current_url("firefox"), "https://github.com/")

    def test_newest_input_wins_between_servers(self):
        p = BrowserUrlProvider(clock=FakeClock(), macos_lookup=lambda app: None)
        p.update(app="jupyter", url="jupyter://editor", focused=True, pid=1, input_age=9.0)
        p.update(app="jupyter", url="jupyter://notebook/command", focused=True, pid=2,
                 input_age=0.5)
        self.assertEqual(p.current_url("chrome"), "jupyter://notebook/command")


if __name__ == "__main__":
    unittest.main()
