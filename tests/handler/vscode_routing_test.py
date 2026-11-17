"""The SHIPPED `code`, `cursor` and `windsurf` entries route each debug mode.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* each `<app>://edit`, `<app>://debug/running`, `<app>://debug/stopped` the
  extension (vscode-extension/) sends puts that mode's debug set after the app's
  own set, on every `os:` branch;
* the same URL with `/diff` after it (a diff editor is the active tab) adds the
  diff set last and keeps the mode's debug set; the `/diff` routes are listed
  before the plain ones, which `urls-contains` would otherwise match first;
* no report (or a stale one, which `current_url` turns into None) is the app's
  set plus the fallback debug set, which draws the keys the app's set drew
  before the reporter existed;
* a mode REPLACES the fallback (`layer: false`): no underlay, no fallback file;
* one app's URL never routes another app's entry (vscode:// on Cursor);
* the entry names are exactly the context-reporter allow-list per token;
* every file named exists, and no switch shows more images than the pool holds
  (counted from the PNGs: every lit cell and channel a route's files draw).
"""

import unittest
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from polyhost.handler.browser_url import CONTEXT_REPORTERS, BrowserUrlProvider
from polyhost.handler.common import find_matching_entry

from tests.handler.blender_routing_test import _overlay_handler_class

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
# mapping key -> (token the extension sends, app-set stem per OS)
APPS = {
    "code": ("vscode", {"windows": "vscode_template", "macos": "vscode_mac_template",
                        "linux": "vscode_linux_template"}),
    "cursor": ("cursor", {"windows": "cursor_template", "macos": "cursor_mac_template",
                          "linux": "cursor_linux_template"}),
    "windsurf,devin,devin-desktop": ("windsurf", {"windows": "windsurf_template",
                                                  "macos": "windsurf_mac_template",
                                                  "linux": "windsurf_linux_template"}),
}
MODES = ("edit", "debug/running", "debug/stopped")
DIFF_FILES = ["vscode_diff.mods.png", "vscode_diff.combo.mods.png"]
# OVERLAY_POOL_CAPACITY (firmware NUM_OVERLAY_SLOTS).
POOL = 600
TITLE = "main.py - project - Visual Studio Code"


def _names(entry):
    return [str(f) for f in entry["overlay"]]


class VscodeMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        for key, (token, _) in APPS.items():
            self.assertIn(key, self.raw)
            self.assertEqual(set(key.split(",")),
                             {n for n, t in CONTEXT_REPORTERS.items() if t == token}, key)

    def test_every_named_file_exists(self):
        def walk(e):
            ov = e.get("overlay", [])
            yield from (ov if isinstance(ov, list) else [ov])
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from walk(child)
        for key in APPS:
            files = list(walk(self.raw[key]))
            self.assertGreater(len(files), 30, key)
            missing = [f for f in files if not (RES / "overlays" / f).is_file()]
            self.assertEqual(missing, [], key)

    def test_diff_routes_come_before_the_plain_ones(self):
        for key, (token, _) in APPS.items():
            levels = [self.raw[key]] + [self.raw[key]["os"][o] for o in ("macos", "linux")]
            for level in levels:
                needles = list(level["urls-contains"])
                self.assertEqual(needles, [f"{token}://{m}/diff" for m in ("debug/stopped", "debug/running", "edit")]
                                 + [f"{token}://{m}" for m in ("debug/stopped", "debug/running", "edit")], key)

    def test_every_level_opts_out_of_layering(self):
        for key in APPS:
            self.assertIs(self.raw[key]["layer"], False, key)
            for os_name in ("macos", "linux"):
                self.assertIs(self.raw[key]["os"][os_name]["layer"], False, (key, os_name))


class VscodeRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        handler = _overlay_handler_class()(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.mapping = handler.mapping

    def _route(self, key, url, os_name):
        entry = self.mapping[key.split(",")[0]]
        title = TITLE if key == "code" else "main.py - project"
        return find_matching_entry(title, entry, url, os_name)

    def test_each_mode_gets_its_debug_set_on_every_os(self):
        for key, (token, stems) in APPS.items():
            for os_name, stem in stems.items():
                suffix = "_mac" if os_name == "macos" else ""
                for mode in MODES:
                    got = _names(self._route(key, f"{token}://{mode}", os_name))
                    want = f"vscode_debug_{mode.split('/')[-1]}{suffix}.mods.png"
                    self.assertEqual(got[0], f"{stem}.mods.png", (key, os_name, mode))
                    self.assertIn(want, got, (key, os_name, mode))
                    self.assertFalse([n for n in got if "fallback" in n], (key, os_name, mode))
                    others = [n for n in got if n.startswith("vscode_debug_") and n != want
                              and not n.startswith(want.replace(".mods.png", "."))]
                    self.assertEqual(others, [], (key, os_name, mode))

    def test_no_report_is_the_app_set_plus_the_fallback(self):
        for key, (_, stems) in APPS.items():
            for os_name, stem in stems.items():
                got = _names(self._route(key, None, os_name))
                self.assertEqual(got[0], f"{stem}.mods.png", (key, os_name))
                self.assertEqual(got[-1], "vscode_debug_fallback.mods.png", (key, os_name))

    def test_a_mode_replaces_the_fallback(self):
        got = self._route("code", "vscode://debug/stopped", "windows")
        self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])

    def test_another_apps_url_does_not_route(self):
        got = _names(self._route("cursor", "vscode://debug/stopped", "windows"))
        self.assertEqual(got[-1], "vscode_debug_fallback.mods.png")

    def test_diff_adds_the_diff_set_and_keeps_the_debug_set(self):
        for key, (token, stems) in APPS.items():
            for os_name, stem in stems.items():
                for mode in MODES:
                    plain = _names(self._route(key, f"{token}://{mode}", os_name))
                    got = _names(self._route(key, f"{token}://{mode}/diff", os_name))
                    self.assertEqual(got, plain + DIFF_FILES, (key, os_name, mode))

    def test_diff_without_a_report_is_the_fallback(self):
        # A diff URL from another app, or no report: no diff set.
        got = _names(self._route("cursor", "vscode://edit/diff", "windows"))
        self.assertEqual(got[-1], "vscode_debug_fallback.mods.png")

    def test_diff_keys_are_free_in_every_set_below_them(self):
        # The diff set is drawn last; it must not cover a key the app set or a
        # debug set draws (same cell and channel of the same tier).
        diff = _lit(DIFF_FILES)
        for key, (token, stems) in APPS.items():
            for os_name in stems:
                for mode in MODES:
                    below = _names(self._route(key, f"{token}://{mode}", os_name))
                    self.assertEqual(diff & _lit(below), set(), (key, os_name, mode))

    def test_pool_capacity(self):
        # One switch shows at most 600 distinct images (OVERLAY_POOL_CAPACITY):
        # count every lit (tier, channel, cell) a route's files draw.
        for key, (token, stems) in APPS.items():
            for os_name in stems:
                for url in [None] + [f"{token}://{m}{d}" for m in MODES for d in ("", "/diff")]:
                    files = _names(self._route(key, url, os_name))
                    self.assertLess(len(_lit(files)), POOL, (key, os_name, url))


def _lit(files):
    """Every (tier, channel, cell) a list of overlay PNGs draws."""
    out = set()
    for name in files:
        tier = name.split(".", 1)[1].rsplit(".mods.png", 1)[0] if "." in name.split(".mods.png")[0] else ""
        a = np.asarray(Image.open(RES / "overlays" / name).convert("RGBA"))
        h, w = a.shape[0] // 40, a.shape[1] // 72
        cells = a[: h * 40, : w * 72].reshape(h, 40, w, 72, 4).max(axis=(1, 3))
        for y, x, c in zip(*np.nonzero(cells)):
            out.add((tier, int(c), int(y), int(x)))
    return out


class VscodeProviderTest(unittest.TestCase):
    """A report from the extension reaches only its own app."""

    def test_reports_answer_for_their_app_only(self):
        now = [100.0]
        p = BrowserUrlProvider(clock=lambda: now[0], macos_lookup=lambda _a: None)
        self.assertTrue(p.update(app="vscode", url="vscode://debug/stopped", focused=True, pid=7))
        p.update(app="cursor", url="cursor://edit", focused=True, pid=8)
        self.assertEqual(p.current_url("code"), "vscode://debug/stopped")
        self.assertEqual(p.current_url("Code.exe"), "vscode://debug/stopped")
        self.assertEqual(p.current_url("cursor"), "cursor://edit")
        self.assertIsNone(p.current_url("windsurf"))
        self.assertIsNone(p.current_url("notepad"))
        # unfocused window, then the withdrawal on exit
        p.update(app="vscode", url="vscode://debug/stopped", focused=False, pid=7)
        self.assertIsNone(p.current_url("code"))
        p.update(app="vscode", url="vscode://edit", focused=True, pid=7)
        p.update(app="vscode", url=None, focused=False, pid=7)
        self.assertIsNone(p.current_url("code"))
        # a stale report is no report
        p.update(app="windsurf", url="windsurf://debug/running", focused=True, pid=9)
        self.assertEqual(p.current_url("devin"), "windsurf://debug/running")
        now[0] += 60
        self.assertIsNone(p.current_url("devin-desktop"))

    def test_newest_input_wins_between_windows(self):
        now = [100.0]
        p = BrowserUrlProvider(clock=lambda: now[0], macos_lookup=lambda _a: None)
        p.update(app="vscode", url="vscode://debug/stopped", focused=True, pid=1, input_age=0.1)
        p.update(app="vscode", url="vscode://edit", focused=False, pid=2, input_age=30)
        self.assertEqual(p.current_url("code"), "vscode://debug/stopped")


if __name__ == "__main__":
    unittest.main()
