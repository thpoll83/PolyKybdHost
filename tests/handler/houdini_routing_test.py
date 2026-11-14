"""The SHIPPED routing of the Houdini set in `overlay-mapping.poly.yaml`.

Houdini binds Ctrl on Windows/Linux and Cmd on macOS, so the entry has an
`os: macos` branch. What it pins:

* every launcher name of every edition (FX, Core, Apprentice, Indie, Escape)
  and the Linux `houdini-bin` binary load the Windows/Linux set;
* the macOS app names with a trailing dotted version (`Houdini FX 22.0.368`)
  reach the entry and load the macOS set;
* every file the route names exists;
* with the Houdini package's report (`houdini://<pane>[/<network type>]`), a
  Network Editor loads the Network Editor set, an Animation Editor the graph
  view set, the Python Shell and the Textport their text-input sets, any other
  pane and no report keep the Scene View set, and the report REPLACES the
  fallback (`layer: false`);
* the entry's names are exactly the host's context-reporter allow-list, and a
  macOS name with a version reaches the reporter too.

The names are the expected process / app names; none was checked on an
install (see overlay_sources/houdini/SOURCES.md).
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import (
    CONTEXT_REPORTERS, BrowserUrlProvider, context_reporter_for)
from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

HOUDINI = ["houdini_template.mods.png", "houdini_template.combo.mods.png"]
HOUDINI_MAC = ["houdini_template_mac.mods.png", "houdini_template_mac.combo.mods.png"]
NETWORK = ["houdini_network_template.mods.png", "houdini_network_template.combo.mods.png"]
NETWORK_MAC = ["houdini_network_template_mac.mods.png",
               "houdini_network_template_mac.combo.mods.png",
               "houdini_network_template_mac.extra.mods.png"]
ANIM = ["houdini_anim_template.mods.png", "houdini_anim_template.combo.mods.png"]
ANIM_MAC = ["houdini_anim_template_mac.mods.png", "houdini_anim_template_mac.combo.mods.png"]
# Text-input panes: one artwork set for every OS (no binding uses Cmd).
PYTHON = ["houdini_python_template.mods.png"]
TEXTPORT = ["houdini_textport_template.mods.png"]
PANE_SETS = NETWORK + NETWORK_MAC + ANIM + ANIM_MAC + PYTHON + TEXTPORT
KEY = ("houdini,houdinifx,houdinicore,happrentice,hindie,hescape,houdini-bin,"
       "houdini fx,houdini core,houdini apprentice,houdini indie")

LAUNCHERS = ["houdini", "houdinifx", "houdinicore", "happrentice", "hindie", "hescape"]

# (reported app name, os, expected overlay list)
ROUTES = (
    [(name, "windows", HOUDINI) for name in LAUNCHERS]
    + [(name, "linux", HOUDINI) for name in LAUNCHERS + ["houdini-bin"]]
    + [
        ("houdini fx 22.0.368", "macos", HOUDINI_MAC),
        ("houdini core 21.0.440", "macos", HOUDINI_MAC),
        ("houdini apprentice 20.5.684", "macos", HOUDINI_MAC),
        ("houdini indie 22.0.368", "macos", HOUDINI_MAC),
        ("houdini fx", "macos", HOUDINI_MAC),
        ("houdini", "macos", HOUDINI_MAC),
    ]
)


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as vfx_routing_test)."""
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}") from e
    except Exception as e:
        # Skip only for a missing third-party backend or an Xlib display error.
        # A missing polyhost module is a real failure.
        if not ((isinstance(e, ModuleNotFoundError)
                 and not (e.name or "").startswith("polyhost"))
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}") from e
    return OverlayHandler


class HoudiniReporterFileTest(unittest.TestCase):
    """The raw YAML and the allow-list; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertIn(KEY, self.raw)
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "houdini"})

    def test_both_levels_opt_out_of_layering(self):
        self.assertIs(self.raw[KEY]["layer"], False)
        self.assertIs(self.raw[KEY]["os"]["macos"]["layer"], False)

    def test_every_os_name_reaches_the_reporter(self):
        for app, _os, _files in ROUTES:
            with self.subTest(app=app):
                self.assertEqual(context_reporter_for(app), "houdini")
        self.assertEqual(context_reporter_for("houdinifx.exe"), "houdini")
        self.assertIsNone(context_reporter_for("houdini engine"))

    def test_a_report_answers_only_while_houdini_is_focused(self):
        now = [100.0]
        p = BrowserUrlProvider(clock=lambda: now[0], macos_lookup=lambda _a: None)
        self.assertTrue(p.update(app="houdini", url="houdini://network/sop", pid=7))
        self.assertEqual(p.current_url("houdinifx"), "houdini://network/sop")
        self.assertEqual(p.current_url("houdini fx 22.0.368"), "houdini://network/sop")
        self.assertIsNone(p.current_url("blender"))
        now[0] += 9.0                                  # stale: the fallback returns
        self.assertIsNone(p.current_url("houdini"))
        p.update(app="houdini", url="houdini://scene/sop", pid=7)
        p.update(app="houdini", url=None, focused=False, pid=7)   # Houdini exited
        self.assertIsNone(p.current_url("houdini"))


class HoudiniRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry("Untitled", self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_each_name_loads_its_set_on_each_os(self):
        for app, os_name, expected in ROUTES:
            with self.subTest(app=app, os=os_name):
                self.assertEqual(self._route(app, os_name), expected)

    def _route_url(self, url, os_name):
        m = find_matching_entry("Untitled", self.mapping["houdini"], url, os_name)
        return None if m is None else [str(f) for f in m["overlay"]]

    def test_each_pane_gets_its_set(self):
        cases = {
            "houdini://network/sop": NETWORK,
            "houdini://network/obj": NETWORK,
            "houdini://network/lop": NETWORK,
            "houdini://network": NETWORK,
            "houdini://anim": ANIM,
            "houdini://anim/obj": ANIM,
            "houdini://python": PYTHON,
            "houdini://textport": TEXTPORT,
            "houdini://scene/sop": HOUDINI,
            "houdini://parms/obj": HOUDINI,
            "houdini://channels": HOUDINI,
            "houdini://compositor": HOUDINI,
            "houdini://other": HOUDINI,
            None: HOUDINI,
        }
        for url, want in cases.items():
            with self.subTest(url=url):
                self.assertEqual(self._route_url(url, "windows"), want)
                self.assertEqual(self._route_url(url, "linux"), want)
        self.assertEqual(self._route_url("houdini://network/dop", "macos"), NETWORK_MAC)
        self.assertEqual(self._route_url("houdini://scene/obj", "macos"), HOUDINI_MAC)
        self.assertEqual(self._route_url(None, "macos"), HOUDINI_MAC)
        self.assertEqual(self._route_url("houdini://anim", "macos"), ANIM_MAC)
        self.assertEqual(self._route_url("houdini://python", "macos"), PYTHON)
        self.assertEqual(self._route_url("houdini://textport", "macos"), TEXTPORT)
        self.assertEqual(self._route_url("houdini://channels", "macos"), HOUDINI_MAC)

    def test_a_pane_set_replaces_the_scene_view_set(self):
        # A text pane must not show the Scene View tool letters dimmed under it.
        for url in ("houdini://network/sop", "houdini://anim",
                    "houdini://python", "houdini://textport"):
            for os_name in ("linux", "macos"):
                with self.subTest(url=url, os=os_name):
                    got = find_matching_entry("Untitled", self.mapping["houdini"], url, os_name)
                    self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])

    def test_pane_set_files_exist(self):
        missing = [f for f in PANE_SETS if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])

    def test_pool_capacity(self):
        # One switch shows at most 600 distinct images (OVERLAY_POOL_CAPACITY):
        # count the lit 72x40 cells per colour channel of each route's PNGs.
        import numpy as np
        from PIL import Image

        def slots(files):
            n = 0
            for f in files:
                a = np.asarray(Image.open(RES / "overlays" / f).convert("RGBA")) > 127
                for r in range(a.shape[0] // 40):
                    for c in range(a.shape[1] // 72):
                        cell = a[r * 40:(r + 1) * 40, c * 72:(c + 1) * 72]
                        n += int(cell.any(axis=(0, 1)).sum())
            return n

        for files in (NETWORK, NETWORK_MAC, ANIM, ANIM_MAC, PYTHON, TEXTPORT):
            with self.subTest(files=files[0]):
                self.assertLessEqual(slots(files), 600)

    def test_unrelated_names_do_not_match(self):
        # A name that only starts with "houdini" is not the app.
        for app in ("houdini engine", "houdinilauncher"):
            with self.subTest(app=app):
                self.assertIsNone(mapping_key(app, self.mapping))

    def test_every_named_file_exists(self):
        named = {f for _, _, files in ROUTES for f in files}
        missing = sorted(f for f in named if not (RES / "overlays" / f).is_file())
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
