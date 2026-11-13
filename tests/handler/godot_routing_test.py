"""The SHIPPED `godot` mapping entry routes each reported main screen.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* each `godot://<screen>` the plugin (godot-plugin/) sends picks that screen's
  set, drawn AFTER the fallback set so its keys take priority; Asset Store,
  another plugin's screen and no report keep the fallback set alone;
* a screen REPLACES the fallback (`layer: false`): no file is an underlay;
* macOS takes the `_mac` sets on every route;
* the entry's names are exactly the `godot` context reporters, and the names
  the OS reports for the official downloads (versioned on Linux) reach both
  the entry and the reporter;
* the whole chain from a report to the overlay, through `BrowserUrlProvider`;
* every file named exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import (
    CONTEXT_REPORTERS, BrowserUrlProvider, context_reporter_for)
from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
KEY = "godot,godot_v4,godot_mono,godot4,godot-bin,org.godotengine.godot,org.godotengine.editor"

BASE = "godot_template.mods.png"
SCREEN_SETS = {
    "godot://2d": "godot_2d_template.mods.png",
    "godot://3d": "godot_3d_template.mods.png",
    "godot://script": "godot_script_template.mods.png",
    "godot://game": "godot_game_template.mods.png",
}


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


def _mac(name):
    return name.replace("_template.", "_template_mac.")


class GodotMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_names_are_the_godot_context_reporters(self):
        self.assertIn(KEY, self.raw)
        self.assertEqual(set(KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "godot"})

    def test_routes_and_layering(self):
        entry = self.raw[KEY]
        self.assertIs(entry.get("layer"), False)
        self.assertEqual(set(entry["urls-contains"]), set(SCREEN_SETS))
        mac = entry["os"]["macos"]
        self.assertIs(mac.get("layer"), False)
        self.assertEqual(set(mac["urls-contains"]), set(SCREEN_SETS))

    def test_every_named_file_exists(self):
        entry = self.raw[KEY]
        files = set()
        for e in (entry, entry["os"]["macos"]):
            files |= set(_files(e))
            for sub in e["urls-contains"].values():
                files |= set(_files(sub))
        self.assertGreaterEqual(len(files), 20)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


class GodotNameTest(unittest.TestCase):
    """The names the OS reports reach both the entry and the reporter."""

    @classmethod
    def setUpClass(cls):
        raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        cls.keys = {n: KEY for n in KEY.split(",")}
        cls.others = {k.strip().lower() for key in raw for k in key.split(",")} - set(cls.keys)

    def test_reported_names(self):
        for name in (
                "godot_v4",                                 # Windows download (cut at the first dot)
                "godot",                                    # source build, Steam, macOS "Godot"
                "godot_v4.7.2-stable_linux.x86_64",         # Linux download
                "godot_v4.7.2-stable_mono_linux.x86_64",    # Linux .NET download
                "godot_v4.6-rc1_linux.arm64",               # a release candidate
                "godot-bin",                                # Flatpak
                "org.godotengine.editor"):                  # Wayland app id (4.5+)
            self.assertIsNotNone(mapping_key(name, self.keys), name)
            self.assertEqual(context_reporter_for(name), "godot", name)
        # The forwarder passes the raw Windows process name.
        self.assertEqual(context_reporter_for("Godot_v4.7.2-stable_win64.exe"), "godot")

    def test_version_and_build_stripping_moves_no_other_key(self):
        # Every key of the shipped mapping still resolves to itself.
        for name in self.others:
            self.assertIsNone(mapping_key(name, self.keys), name)
        self.assertIsNone(context_reporter_for("code"))
        self.assertIsNone(context_reporter_for("godotify"))


class GodotRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.handler = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.mapping = cls.handler.mapping

    def _route(self, url, os_name="linux", app="godot_v4"):
        m = find_matching_entry("", self.mapping[app], url, os_name)
        return None if m is None else _files(m)

    def test_each_screen_draws_its_set_over_the_fallback(self):
        for os_name in ("linux", "windows", "macos"):
            for url, own in SCREEN_SETS.items():
                files = self._route(url, os_name)
                base, own = (BASE, own) if os_name != "macos" else (_mac(BASE), _mac(own))
                self.assertEqual(files[0], base, (url, os_name))
                self.assertIn(own, files, (url, os_name))
                self.assertLess(files.index(base), files.index(own))

    def test_no_layering_underneath(self):
        for url in SCREEN_SETS:
            ov = self.mapping["godot"]["urls-contains"][url]["overlay"]
            self.assertFalse([f for f in ov if getattr(f, "underlay", False)], url)

    def test_fallback_without_a_screen_set(self):
        for url in (None, "godot://assetlib", "godot://other"):
            self.assertEqual(self._route(url), [
                BASE, "godot_template.combo.mods.png", "godot_template.extra.mods.png"], url)
            self.assertEqual(self._route(url, "macos")[0], _mac(BASE), url)

    def test_report_to_overlay_through_the_provider(self):
        p = BrowserUrlProvider(macos_lookup=lambda app: None)
        p.update(app="godot", url="godot://script", focused=True, pid=42, input_age=0.0)
        for app in ("godot_v4", "godot"):
            self.assertIn(SCREEN_SETS["godot://script"], self._route(p.current_url(app), app=app))
        # The report never reaches another app.
        self.assertIsNone(p.current_url("blender"))
        self.assertIsNone(p.current_url("code"))
        # Focus-out (or the plugin disabled): back to the fallback.
        p.update(app="godot", url=None, focused=False, pid=42)
        self.assertIsNone(p.current_url("godot_v4"))
        self.assertEqual(self._route(p.current_url("godot_v4"))[0], BASE)


if __name__ == "__main__":
    unittest.main()
