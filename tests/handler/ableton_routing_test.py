"""The SHIPPED Ableton Live 12 mapping entry routes each reported view correctly.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* `ableton://session[/clip|/device]` (the remote script in
  `ableton-remote-script/`) gets the Session View set;
* `ableton://arrangement[...]` and no report (or a stale one, which
  `current_url` turns into None) get the Arrangement set, the old fallback;
* a view REPLACES the fallback (`layer: false`);
* macOS takes the `_mac` sets, and every branch keeps `midi: true`;
* the entry's names are exactly the host's context-reporter allow-list;
* every file it names exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import CONTEXT_REPORTERS, context_reporter_for
from polyhost.handler.common import find_matching_entry
from polyhost.services.midi_guide import is_midi_entry
from tests.handler.blender_routing_test import _first, _overlay_handler_class

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
KEY = ("ableton live 12 suite,ableton live 12 standard,ableton live 12 intro,"
       "ableton live 12 lite,ableton live 12 trial")


class AbletonMappingFileTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_context_reporter_allow_list(self):
        self.assertIn(KEY, self.raw)
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "ableton"})
        self.assertEqual(context_reporter_for("Ableton Live 12 Suite.exe"), "ableton")

    def test_every_named_file_exists(self):
        def walk(e):
            ov = e.get("overlay", [])
            yield from (ov if isinstance(ov, list) else [ov])
            for sub in ("urls-contains", "os"):
                for child in (e.get(sub) or {}).values():
                    yield from walk(child)
        files = list(walk(self.raw[KEY]))
        self.assertGreaterEqual(len(files), 21)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])

    def test_both_levels_opt_out_of_layering(self):
        self.assertIs(self.raw[KEY]["layer"], False)
        self.assertIs(self.raw[KEY]["os"]["macos"]["layer"], False)


class AbletonRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        handler = _overlay_handler_class()(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.entry = handler.mapping["ableton live 12 suite"]
        assert handler.mapping["ableton live 12 trial"] is cls.entry

    def _match(self, url, os_name="windows"):
        return find_matching_entry("Ableton Live 12 Suite", self.entry, url, os_name)

    def test_each_view_gets_its_overlay(self):
        cases = {
            "ableton://session": "ableton_session_template.mods.png",
            "ableton://session/clip": "ableton_session_template.mods.png",
            "ableton://session/device": "ableton_session_template.mods.png",
            "ableton://arrangement": "ableton_template.mods.png",
            "ableton://arrangement/clip": "ableton_template.mods.png",
            "ableton://arrangement/device": "ableton_template.mods.png",
        }
        for url, want in cases.items():
            self.assertEqual(_first(self._match(url)), want, url)

    def test_no_report_is_the_arrangement_fallback(self):
        self.assertEqual(_first(self._match(None)), "ableton_template.mods.png")

    def test_a_view_replaces_the_fallback(self):
        got = self._match("ableton://session")
        names = [str(f) for f in got["overlay"]]
        self.assertTrue(all(n.startswith("ableton_session_template") for n in names), names)
        self.assertFalse([f for f in got["overlay"] if getattr(f, "underlay", False)])

    def test_macos_takes_the_mac_sets(self):
        self.assertEqual(_first(self._match("ableton://session/clip", "macos")),
                         "ableton_session_template_mac.mods.png")
        self.assertEqual(_first(self._match("ableton://arrangement", "macos")),
                         "ableton_template_mac.mods.png")
        self.assertEqual(_first(self._match(None, "macos")), "ableton_template_mac.mods.png")

    def test_every_view_stays_a_midi_program(self):
        for os_name in ("windows", "macos"):
            for url in (None, "ableton://session", "ableton://arrangement/device"):
                self.assertTrue(is_midi_entry(self._match(url, os_name),
                                              "Ableton Live 12 Suite"), (os_name, url))


if __name__ == "__main__":
    unittest.main()
