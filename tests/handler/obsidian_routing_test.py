"""The SHIPPED Obsidian routing: the `obsidian` entry and its view reports.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* each `obsidian://<view>` report from the plugin (`obsidian-plugin/`) picks
  that view's set, on every `os:` branch;
* the editor (Source mode, Live Preview), Vim Insert and Replace mode, and no
  report at all keep the main set;
* the Vim Normal and Visual layers are drawn LAST, over the main set;
* `layer: false`, so a view replaces the main set instead of drawing it dimmed;
* the whole chain from a report to the overlay, through `BrowserUrlProvider`,
  and a report never reaches another app;
* the entry's name is exactly the `obsidian` context reporter;
* every file named exists, and the largest set stays under the pool size.
"""

import unittest
from pathlib import Path

import yaml
from PIL import Image

from polyhost.handler.browser_url import CONTEXT_REPORTERS, BrowserUrlProvider
from polyhost.handler.common import find_matching_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
KEY = "obsidian"
POOL = 600     # OVERLAY_POOL_CAPACITY: distinct images one switch can show

MAIN = {"other_os": "obsidian_template.mods.png", "macos": "obsidian_template_mac.mods.png"}


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (same tolerance as blender_routing_test)."""
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


def _files(entry):
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])]


def _suffix(os_name):
    return "_mac" if os_name == "macos" else ""


class ObsidianMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        cls.entry = cls.raw[KEY]

    def test_name_is_the_obsidian_context_reporter(self):
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "obsidian"})

    def test_every_branch_turns_layering_off_and_has_the_routes(self):
        branches = [self.entry, *self.entry["os"].values()]
        self.assertEqual(list(self.entry["os"]), ["macos"])
        for b in branches:
            self.assertIs(b.get("layer"), False)
            self.assertEqual(list(b["urls-contains"]),
                             ["/vim-normal", "/vim-visual", "obsidian://reading",
                              "obsidian://canvas", "obsidian://graph", "obsidian://other"])

    def test_every_named_file_exists(self):
        files = set()
        for b in [self.entry, *self.entry["os"].values()]:
            files |= set(_files(b))
            for sub in b["urls-contains"].values():
                files |= set(_files(sub))
        self.assertGreaterEqual(len(files), 24)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])

    def test_largest_set_fits_the_pool(self):
        """A drawn cell per (key, modifier) is at most one image, so the lit
        cells of a set's files bound its distinct images."""
        worst = 0
        for b in [self.entry, *self.entry["os"].values()]:
            for sub in [b, *b["urls-contains"].values()]:
                n = 0
                for f in _files(sub):
                    im = Image.open(RES / "overlays" / f).convert("RGBA")
                    for ch in im.split():
                        for row in range(9):
                            for col in range(10):
                                box = (col * 72, row * 40, col * 72 + 72, row * 40 + 40)
                                if ch.crop(box).getbbox():
                                    n += 1
                worst = max(worst, n)
        self.assertLess(worst, POOL)


class ObsidianRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, url, os_name="linux"):
        m = find_matching_entry("Note - My vault - Obsidian v1.9.0", self.mapping[KEY],
                                url, os_name)
        return None if m is None else _files(m)

    def test_each_view_picks_its_set(self):
        for os_name in ("linux", "windows", "macos"):
            sfx = _suffix(os_name)
            for view in ("reading", "canvas", "graph"):
                self.assertEqual(self._route(f"obsidian://{view}", os_name)[0],
                                 f"obsidian_{view}_template{sfx}.mods.png", (view, os_name))
            self.assertEqual(self._route("obsidian://other", os_name)[0],
                             f"obsidian_global_template{sfx}.mods.png", os_name)

    def test_editor_and_no_report_keep_the_main_set(self):
        for os_name in ("linux", "windows", "macos"):
            main = MAIN["macos" if os_name == "macos" else "other_os"]
            for url in (None, "obsidian://live", "obsidian://source",
                        "obsidian://live/vim-insert", "obsidian://source/vim-replace"):
                files = self._route(url, os_name)
                self.assertEqual(files[0], main, (url, os_name))
                self.assertNotIn("obsidian_vim_normal_template.mods.png", files)

    def test_vim_layers_go_last_over_the_main_set(self):
        for os_name in ("linux", "macos"):
            main = MAIN["macos" if os_name == "macos" else "other_os"]
            for view in ("live", "source"):
                for mode in ("normal", "visual"):
                    files = self._route(f"obsidian://{view}/vim-{mode}", os_name)
                    self.assertEqual(files[0], main)
                    self.assertEqual(files[-1], f"obsidian_vim_{mode}_template.mods.png")

    def test_a_view_replaces_the_main_set(self):
        # layer: false -- no main-set file dimmed under the reading set.
        files = self._route("obsidian://reading")
        self.assertNotIn(MAIN["other_os"], files)
        self.assertFalse([f for f in self.mapping[KEY]["urls-contains"]["obsidian://reading"]
                          ["overlay"] if getattr(f, "underlay", False)])

    def test_report_to_overlay_through_the_provider(self):
        p = BrowserUrlProvider(macos_lookup=lambda app: None)
        self.assertIsNone(p.current_url("obsidian"))
        p.update(app="obsidian", url="obsidian://canvas", focused=True, pid=42, input_age=0.0)
        self.assertEqual(p.current_url("obsidian"), "obsidian://canvas")
        self.assertEqual(self._route(p.current_url("obsidian"))[0],
                         "obsidian_canvas_template.mods.png")
        # Never another app's: not a native app, not a terminal, not a browser.
        for app in ("code", "kitty", "firefox", "blender"):
            self.assertIsNone(p.current_url(app), app)
        # The withdrawal on unload: back to the main set at once.
        p.update(app="obsidian", url=None, focused=False, pid=42)
        self.assertIsNone(p.current_url("obsidian"))
        self.assertEqual(self._route(p.current_url("obsidian"))[0], MAIN["other_os"])

    def test_windows_process_name(self):
        p = BrowserUrlProvider(macos_lookup=lambda app: None)
        p.update(app="obsidian", url="obsidian://graph", focused=True, pid=1)
        self.assertEqual(p.current_url("Obsidian.exe"), "obsidian://graph")


if __name__ == "__main__":
    unittest.main()
