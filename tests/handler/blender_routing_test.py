"""The SHIPPED `blender` mapping entry routes each reported context correctly.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* every `blender://<mode>/<editor>` the add-on can send lands on the overlay for
  that context, and an editor without its own overlay falls to `global`, never
  to the 3D View set;
* no report (or a stale one, which `current_url` turns into None) is the 3D View
  `common` fallback;
* a context REPLACES the fallback (`layer: false`) -- layered, the 3D View keys
  would show dimmed under the Node Editor's;
* macOS takes the `_mac` sets (Cmd duplicates of Blender's Ctrl chords);
* the entry's names are exactly the host's context-reporter allow-list, so a
  name added to one and not the other cannot leave Blender with reports nobody
  reads, or a mapping nobody feeds;
* every file it names exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import CONTEXT_REPORTERS
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
KEY = "blender,org.blender.blender"


def _first(entry):
    ov = entry["overlay"]
    return str(ov[0] if isinstance(ov, list) else ov)


class BlenderMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertIn(KEY, self.raw)
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "blender"})

    def test_every_named_file_exists(self):
        def walk(e):
            ov = e.get("overlay", [])
            for f in (ov if isinstance(ov, list) else [ov]):
                yield f
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from walk(child)
        files = list(walk(self.raw[KEY]))
        self.assertGreater(len(files), 50)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])

    def test_both_levels_opt_out_of_layering(self):
        self.assertIs(self.raw[KEY]["layer"], False)
        self.assertIs(self.raw[KEY]["os"]["macos"]["layer"], False)


class BlenderRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        handler = _overlay_handler_class()(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.entry = handler.mapping["blender"]
        assert handler.mapping["org.blender.blender"] is cls.entry

    def _route(self, url, os_name="linux"):
        return _first(find_matching_entry("Blender", self.entry, url, os_name))

    def test_each_context_gets_its_overlay(self):
        cases = {
            "blender://OBJECT/VIEW_3D": "blender_object_template.mods.png",
            "blender://EDIT_MESH/VIEW_3D": "blender_edit_mesh_template.mods.png",
            "blender://SCULPT/VIEW_3D": "blender_sculpt_template.mods.png",
            "blender://POSE/VIEW_3D": "blender_pose_template.mods.png",
            "blender://EDIT_ARMATURE/VIEW_3D": "blender_edit_armature_template.mods.png",
            "blender://PAINT_WEIGHT/VIEW_3D": "blender_paint_weight_template.mods.png",
            "blender://PAINT_VERTEX/VIEW_3D": "blender_paint_vertex_template.mods.png",
            "blender://PAINT_TEXTURE/VIEW_3D": "blender_paint_texture_template.mods.png",
            # editors win over the mode they happen to be in
            "blender://OBJECT/NODE_EDITOR/ShaderNodeTree": "blender_node_template.mods.png",
            "blender://EDIT_MESH/NODE_EDITOR/GeometryNodeTree": "blender_node_template.mods.png",
            "blender://EDIT_MESH/IMAGE_EDITOR/UV": "blender_uv_template.mods.png",
            "blender://OBJECT/DOPESHEET_EDITOR/TIMELINE": "blender_dopesheet_template.mods.png",
            "blender://POSE/GRAPH_EDITOR/FCURVES": "blender_graph_template.mods.png",
            # a 3D View mode without its own set -> the 3D View common set
            "blender://EDIT_CURVE/VIEW_3D": "blender_common_template.mods.png",
            # an editor without its own set -> window-level keys only
            "blender://OBJECT/TEXT_EDITOR": "blender_global_template.mods.png",
            "blender://OBJECT/IMAGE_EDITOR/VIEW": "blender_global_template.mods.png",
        }
        for url, want in cases.items():
            self.assertEqual(self._route(url), want, url)

    def test_no_report_is_the_common_fallback(self):
        self.assertEqual(self._route(None), "blender_common_template.mods.png")

    def test_a_context_replaces_the_fallback(self):
        got = find_matching_entry("Blender", self.entry,
                                  "blender://OBJECT/NODE_EDITOR/ShaderNodeTree", "linux")
        names = [str(f) for f in got["overlay"]]
        self.assertFalse([n for n in names if "common" in n], names)
        self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])

    def test_macos_takes_the_mac_sets(self):
        self.assertEqual(self._route("blender://SCULPT/VIEW_3D", "macos"),
                         "blender_sculpt_template_mac.mods.png")
        self.assertEqual(self._route(None, "macos"), "blender_common_template_mac.mods.png")


if __name__ == "__main__":
    unittest.main()
