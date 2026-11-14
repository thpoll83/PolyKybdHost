"""The SHIPPED `unity` mapping entry routes each reported Unity Editor context.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* every `unity://<edit|play>/<window>` the Editor package (`unity-package/`)
  can send lands on the set for that window: the Game view in Play mode on the
  Play-mode set, the Scene view, the Animation window and the Timeline window
  on their own sets, every other window on the global set;
* no report (or a stale one, which `current_url` turns into None) is the Scene
  view set;
* a context REPLACES the fallback (`layer: false`), on both `os:` levels;
* macOS takes the `_mac` sets;
* the whole chain from a report to the overlay, through `BrowserUrlProvider`;
* the entry's names are exactly the `unity` context reporters;
* every file it names exists, and no route shows more than one switch can hold.
"""

import unittest
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from polyhost.device.device_settings import OVERLAY_POOL_CAPACITY
from polyhost.handler.browser_url import CONTEXT_REPORTERS, BrowserUrlProvider
from polyhost.handler.common import find_matching_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
KEY = "unity"

GLOBAL = "unity_template.mods.png"
SCENE = "unity_scene_template.mods.png"
ANIMATION = "unity_animation_template.mods.png"
TIMELINE = "unity_timeline_template.mods.png"
PLAY = "unity_play_template.mods.png"


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


def _first(entry):
    ov = entry["overlay"]
    return str(ov[0] if isinstance(ov, list) else ov)


def _mac(name):
    return name.replace(".mods.png", "_mac.mods.png")


class UnityMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertIn(KEY, self.raw)
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "unity"})

    def test_every_named_file_exists(self):
        def walk(e):
            ov = e.get("overlay", [])
            yield from (ov if isinstance(ov, list) else [ov])
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from walk(child)
        files = list(walk(self.raw[KEY]))
        self.assertGreaterEqual(len(files), 25)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])

    def test_both_levels_opt_out_of_layering(self):
        self.assertIs(self.raw[KEY]["layer"], False)
        self.assertIs(self.raw[KEY]["os"]["macos"]["layer"], False)

    def test_both_levels_route_the_same_needles_in_the_same_order(self):
        top = list(self.raw[KEY]["urls-contains"])
        self.assertEqual(top, list(self.raw[KEY]["os"]["macos"]["urls-contains"]))
        self.assertEqual(top[-1], "unity://")   # the catch-all comes last

    def test_every_route_fits_one_switch(self):
        # One switch shows at most OVERLAY_POOL_CAPACITY distinct images. Count
        # them from the PNGs: every lit 72x40 cell of every channel, deduplicated
        # by content, over all files of one route.
        def images(files):
            seen = set()
            for f in files:
                a = np.asarray(Image.open(RES / "overlays" / f).convert("RGBA"))
                for ch in range(4):
                    for r in range(a.shape[0] // 40):
                        for c in range(a.shape[1] // 72):
                            cell = a[r * 40:(r + 1) * 40, c * 72:(c + 1) * 72, ch] > 127
                            if cell.any():
                                seen.add(cell.tobytes())
            return len(seen)

        def routes(e):
            yield e["overlay"]
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from routes(child)
        counts = [images(r) for r in routes(self.raw[KEY])]
        self.assertGreater(max(counts), 80)        # the count saw the artwork
        self.assertLess(max(counts), OVERLAY_POOL_CAPACITY)


class UnityRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        handler = _overlay_handler_class()(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.entry = handler.mapping[KEY]

    def _route(self, url, os_name="linux"):
        return _first(find_matching_entry("", self.entry, url, os_name))

    CASES = {
        "unity://play/game": PLAY,
        "unity://edit/game": GLOBAL,          # Game view outside Play mode: editor keys
        "unity://edit/scene": SCENE,
        "unity://play/scene": SCENE,
        "unity://edit/animation": ANIMATION,
        "unity://play/animation": ANIMATION,
        "unity://edit/timeline": TIMELINE,
        "unity://play/timeline": TIMELINE,
        "unity://edit/animator": GLOBAL,      # not the Animation window
        "unity://edit/hierarchy": GLOBAL,
        "unity://edit/project": GLOBAL,
        "unity://edit/inspector": GLOBAL,
        "unity://play/inspector": GLOBAL,
        "unity://edit/console": GLOBAL,
        "unity://edit/other": GLOBAL,
        "unity://edit/none": GLOBAL,
    }

    def test_each_context_gets_its_overlay(self):
        for os_name in ("windows", "linux"):
            for url, want in self.CASES.items():
                self.assertEqual(self._route(url, os_name), want, (url, os_name))

    def test_macos_takes_the_mac_sets(self):
        for url, want in self.CASES.items():
            self.assertEqual(self._route(url, "macos"), _mac(want), url)
        self.assertEqual(self._route(None, "macos"), _mac(SCENE))

    def test_no_report_is_the_scene_fallback(self):
        self.assertEqual(self._route(None), SCENE)

    def test_a_context_replaces_the_fallback(self):
        got = find_matching_entry("", self.entry, "unity://play/game", "linux")
        names = [str(f) for f in got["overlay"]]
        self.assertFalse([n for n in names if "scene" in n], names)
        self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])

    def test_report_to_overlay_through_the_provider(self):
        now = [100.0]
        p = BrowserUrlProvider(clock=lambda: now[0], macos_lookup=lambda app: None)
        self.assertIsNone(p.current_url("unity"))
        self.assertEqual(self._route(p.current_url("unity")), SCENE)
        self.assertTrue(p.update(app="unity", url="unity://play/game", focused=True,
                                 pid=4242, input_age=0.2))
        self.assertEqual(self._route(p.current_url("unity")), PLAY)
        p.update(app="unity", url="unity://edit/animation", focused=True, pid=4242)
        self.assertEqual(self._route(p.current_url("unity")), ANIMATION)
        p.update(app="unity", url="unity://edit/timeline", focused=True, pid=4242)
        self.assertEqual(self._route(p.current_url("unity")), TIMELINE)
        # The withdrawal the package sends when it is turned off or Unity quits.
        p.update(app="unity", url=None, focused=False, pid=4242)
        self.assertEqual(self._route(p.current_url("unity")), SCENE)
        # A report goes stale after the freshness window: the fallback again.
        p.update(app="unity", url="unity://edit/hierarchy", focused=True, pid=4242)
        self.assertEqual(self._route(p.current_url("unity")), GLOBAL)
        now[0] += 60
        self.assertEqual(self._route(p.current_url("unity")), SCENE)

    def test_a_unity_report_never_answers_for_another_app(self):
        p = BrowserUrlProvider(macos_lookup=lambda app: None)
        p.update(app="unity", url="unity://edit/scene", focused=True, pid=1)
        self.assertIsNone(p.current_url("blender"))
        self.assertIsNone(p.current_url("code"))


if __name__ == "__main__":
    unittest.main()
