"""The SHIPPED `bitwig studio` mapping entry routes each reported panel layout.

The Bitwig Studio controller extension (`bitwig-extension/`) reports the panel
layout as `bitwig://arrange`, `bitwig://mix` or `bitwig://edit`. What this pins:

* `bitwig://edit` gets the Edit View set (the Detail Editor's arrow keys), on
  Windows/Linux and on macOS;
* ARRANGE, MIX, an unknown layout and no report keep the default set, and a
  route REPLACES it (`layer: false`) instead of layering over it;
* the entry's names are exactly the context-reporter allow-list for `bitwig`,
  and a report from the extension answers only for Bitwig;
* the Edit View spec differs from the default spec only in the arrow keys;
* every file the entry names exists, and the shipped `.bwextension` has the
  service file Bitwig loads it by.
"""

import unittest
import zipfile
from pathlib import Path

import yaml

from polyhost.handler.browser_url import CONTEXT_REPORTERS, BrowserUrlProvider
from polyhost.handler.common import find_matching_entry

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
SOURCES = RES / "overlay_sources" / "bitwig"
EXTENSION = ROOT / "bitwig-extension" / "PolyKybdContextReporter.bwextension"
KEY = "bitwig studio,bitwigstudio,bitwig-studio,com.bitwig.bitwigstudio"
ARROWS = {"LEFT", "RIGHT", "UP", "DOWN"}


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


def _first(entry):
    ov = entry["overlay"]
    return str(ov[0] if isinstance(ov, list) else ov)


class BitwigMappingFileTest(unittest.TestCase):
    """Properties of the raw files; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertIn(KEY, self.raw)
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "bitwig"})

    def test_every_named_file_exists(self):
        def walk(e):
            ov = e.get("overlay", [])
            for f in (ov if isinstance(ov, list) else [ov]):
                yield f
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from walk(child)
        files = list(walk(self.raw[KEY]))
        self.assertIn("bitwig_edit_template.mods.png", files)
        self.assertIn("bitwig_edit_template_mac.mods.png", files)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])

    def test_both_levels_opt_out_of_layering(self):
        self.assertIs(self.raw[KEY]["layer"], False)
        self.assertIs(self.raw[KEY]["os"]["macos"]["layer"], False)

    def test_edit_spec_differs_only_in_the_arrow_keys(self):
        def load(name):
            return yaml.safe_load((SOURCES / name).read_text(encoding="utf-8"))
        base, edit = load("bindings.yaml"), load("bindings_edit.yaml")
        self.assertEqual(edit["output"], "bitwig_edit_template")
        self.assertEqual({k: v for k, v in base.items() if k not in ("output", "bindings")},
                         {k: v for k, v in edit.items() if k not in ("output", "bindings")})

        def non_arrow(spec):
            return [b for b in spec["bindings"] if str(b["key"]) not in ARROWS]
        self.assertEqual(non_arrow(base), non_arrow(edit))
        edit_arrows = {(b["key"], tuple(b["mods"])) for b in edit["bindings"]
                       if str(b["key"]) in ARROWS}
        self.assertIn(("UP", ()), edit_arrows)
        self.assertIn(("LEFT", ("CTRL",)), edit_arrows)

    def test_shipped_extension_has_its_service_file(self):
        with zipfile.ZipFile(EXTENSION) as z:
            svc = z.read("META-INF/services/com.bitwig.extension.ExtensionDefinition")
            self.assertEqual(svc.decode().strip(), "org.polykybd.bitwig.PolyKybdReporterDefinition")
            self.assertIn("org/polykybd/bitwig/PolyKybdReporterExtension.class", z.namelist())


class BitwigReportTest(unittest.TestCase):
    """A report from the extension answers for Bitwig and for nothing else."""

    def setUp(self):
        self.now = 100.0
        self.p = BrowserUrlProvider(clock=lambda: self.now, macos_lookup=lambda _a: None)

    def test_report_answers_for_every_bitwig_name(self):
        self.assertTrue(self.p.update(app="bitwig", url="bitwig://edit", pid=42, input_age=0.1))
        for name in ("Bitwig Studio", "BitwigStudio", "bitwig-studio",
                     "com.bitwig.BitwigStudio", "Bitwig Studio.exe"):
            self.assertEqual(self.p.current_url(name), "bitwig://edit", name)
        self.assertIsNone(self.p.current_url("firefox"))
        self.assertIsNone(self.p.current_url("blender"))

    def test_withdrawal_and_staleness_clear_it(self):
        self.p.update(app="bitwig", url="bitwig://edit", pid=42)
        self.p.update(app="bitwig", url=None, focused=False, pid=42)
        self.assertIsNone(self.p.current_url("Bitwig Studio"))
        self.p.update(app="bitwig", url="bitwig://mix", pid=42)
        self.now += 9.0                      # past the 8 s window: no keep-alive came
        self.assertIsNone(self.p.current_url("Bitwig Studio"))


class BitwigRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        handler = _overlay_handler_class()(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.entry = handler.mapping["bitwig studio"]
        for name in KEY.split(","):
            assert handler.mapping[name] is cls.entry

    def _route(self, url, os_name="linux"):
        return find_matching_entry("Bitwig Studio", self.entry, url, os_name)

    def test_edit_gets_the_edit_set(self):
        self.assertEqual(_first(self._route("bitwig://edit")), "bitwig_edit_template.mods.png")
        self.assertEqual(_first(self._route("bitwig://edit", "windows")),
                         "bitwig_edit_template.mods.png")
        self.assertEqual(_first(self._route("bitwig://edit", "macos")),
                         "bitwig_edit_template_mac.mods.png")

    def test_other_layouts_and_no_report_keep_the_default(self):
        for url in (None, "bitwig://arrange", "bitwig://mix", "bitwig://play"):
            self.assertEqual(_first(self._route(url)), "bitwig_template.mods.png", url)
            self.assertEqual(_first(self._route(url, "macos")),
                             "bitwig_template_mac.mods.png", url)

    def test_edit_replaces_the_default(self):
        got = self._route("bitwig://edit")
        names = [str(f) for f in got["overlay"]]
        self.assertFalse([n for n in names if n.startswith("bitwig_template")], names)
        self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])
        self.assertIs(got.get("midi"), True)


if __name__ == "__main__":
    unittest.main()
