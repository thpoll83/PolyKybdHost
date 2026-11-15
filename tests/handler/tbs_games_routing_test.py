"""The SHIPPED routing of the turn-based strategy game sets in
`overlay-mapping.poly.yaml`.

What it pins:

* every process name of a set loads that set, on all three platforms;
* a set with a macOS branch loads its macOS files there;
* a window title does not reroute a set that is matched by process name;
* Unciv started from its jar and FreeCol are `java` or `javaw` processes: the
  window titles "Unciv" and "FreeCol <version>" load their sets there, and the
  other programs on those process names (a JetBrains IDE, Minecraft, Ghidra)
  keep their sets;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

WESNOTH = ["wesnoth_template.mods.png", "wesnoth_template.combo.mods.png"]
WESNOTH_MAC = ["wesnoth_template_mac.mods.png", "wesnoth_template_mac.combo.mods.png",
               "wesnoth_template_mac.extra.mods.png"]
VCMI = "vcmi_template.mods.png"
UNCIV = "unciv_template.mods.png"
FREEORION = ["freeorion_template.mods.png", "freeorion_template.combo.mods.png"]
FREECOL = ["freecol_template.mods.png", "freecol_template.combo.mods.png"]

MINECRAFT = ["minecraft_java_template.mods.png", "minecraft_java_template.combo.mods.png"]
GHIDRA = ["ghidra_template.mods.png", "ghidra_template.combo.mods.png"]
# Games that run in a JVM: (window title, overlay).
JAVA_GAMES = [
    ("Unciv", UNCIV),
    ("FreeCol 1.2.0", FREECOL),
]

OSES = ("windows", "macos", "linux")

# (process names, window title, {os: overlay}); an os that is not listed uses
# the "windows" value.
BY_PROCESS = [
    (("wesnoth", "wesnoth.exe", "org.wesnoth.wesnoth", "the battle for wesnoth"),
     "The Battle for Wesnoth - 1.18.8", {"windows": WESNOTH, "macos": WESNOTH_MAC}),
    (("vcmiclient", "vcmi_client", "vcmi_client.exe", "eu.vcmi.vcmi"),
     "VCMI 1.7.5", {"windows": VCMI}),
    (("unciv", "unciv.exe", "io.github.yairm210.unciv"), "Unciv", {"windows": UNCIV}),
    (("freeorion", "freeorion.exe", "org.freeorion.freeorion"),
     "FreeOrion v0.5.1.2", {"windows": FREEORION}),
    (("freecol", "freecol.exe", "net-sf-freecol-freecol", "org.freecol.freecol"),
     "FreeCol 1.2.0", {"windows": FREECOL}),
]


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as emulator_routing_test)."""
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}") from e
    except Exception as e:
        if not ((isinstance(e, ModuleNotFoundError)
                 and not (e.name or "").startswith("polyhost"))
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}") from e
    return OverlayHandler


def _files(overlay):
    return [overlay] if isinstance(overlay, str) else list(overlay)


class TbsGamesRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name, title):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_every_process_name_on_every_platform(self):
        for apps, title, expected in BY_PROCESS:
            for app in apps:
                for os_name in OSES:
                    with self.subTest(app=app, os=os_name):
                        self.assertEqual(self._route(app, os_name, title),
                                         expected.get(os_name, expected["windows"]))

    def test_title_does_not_reroute_a_process_match(self):
        for apps, _title, expected in BY_PROCESS:
            for title in ("", "CodeBrowser: project:/program", "Minecraft 1.21.4"):
                with self.subTest(app=apps[0], title=title):
                    self.assertEqual(self._route(apps[0], "windows", title),
                                     expected["windows"])

    def test_java_games_route_by_title(self):
        for title, expected in JAVA_GAMES:
            for app in ("java", "javaw"):
                for os_name in OSES:
                    with self.subTest(app=app, os=os_name, title=title):
                        self.assertEqual(self._route(app, os_name, title), expected)

    def test_other_java_programs_keep_their_sets(self):
        game_sets = [overlay for _title, overlay in JAVA_GAMES]
        for os_name in OSES:
            with self.subTest(os=os_name):
                self.assertEqual(self._route("java", os_name, "Minecraft 1.21.4"), MINECRAFT)
                # An IDE window of a project that has a game's name.
                for title in ("Unciv \u2013 KeyboardBinding.kt",
                              "FreeCol \u2013 FreeColFrame.java"):
                    ide = self._route("java", os_name, title)
                    self.assertIsNotNone(ide)
                    self.assertIn("jetbrains", _files(ide)[0])
                self.assertNotIn(self._route("java", os_name, "Some other program"), game_sets)
        self.assertEqual(self._route("javaw", "windows", "Minecraft 1.21.4"), MINECRAFT)
        self.assertEqual(self._route("javaw", "windows", "CodeBrowser: demo:/a.exe"), GHIDRA)
        self.assertIsNone(self._route("javaw", "windows", "Unciv \u2013 KeyboardBinding.kt"))
        self.assertIsNone(self._route("javaw", "windows", "FreeCol \u2013 FreeColFrame.java"))
        self.assertIsNone(self._route("javaw", "windows", "Some other program"))

    def test_every_named_file_exists(self):
        named = [f for _apps, _title, expected in BY_PROCESS
                 for overlay in expected.values() for f in _files(overlay)]
        named += [f for _title, overlay in JAVA_GAMES for f in _files(overlay)]
        missing = [f for f in named if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
