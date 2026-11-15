"""The SHIPPED rhythm game routing in `overlay-mapping.poly.yaml`.

Each game uses the same keys on every OS, so each entry has one set and no
`os:` branch. What it pins:

* every process name of a game loads that game's set, on all three platforms
  and whatever the window title is, including no title;
* on Windows the host cuts the process name at the first dot before the lookup
  (`polyhost/handler/active_window.py`), so every `.exe` name also routes by
  its bare stem;
* the `match:` list of each spec holds the same names as the mapping entry;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

STEPMANIA = ["stepmania_template.mods.png", "stepmania_template.combo.mods.png"]
STEPMANIA_NAMES = ("stepmania", "stepmania.exe", "stepmania-sse2.exe", "stepmania-sse2")

ETTERNA = ["etterna_template.mods.png", "etterna_template.combo.mods.png"]
ETTERNA_NAMES = ("etterna", "etterna.exe")

OSU = ["osu_template.mods.png", "osu_template.combo.mods.png"]
OSU_NAMES = ("osu!", "osu!.exe", "sh.ppy.osu")

# (set, process names, a window title of the game, spec under overlay_sources/)
GAMES = (
    (STEPMANIA, STEPMANIA_NAMES, "StepMania", "stepmania/stepmania.yaml"),
    (ETTERNA, ETTERNA_NAMES, "Etterna", "etterna/etterna.yaml"),
    (OSU, OSU_NAMES, "osu!", "osu/osu.yaml"),
)


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as qutebrowser_routing_test)."""
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


class RhythmGameRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        cls.mapping = _overlay_handler_class()(cls.raw).mapping

    def _route(self, app, os_name, title):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_windows_names_route_after_the_first_dot_cut(self):
        # active_window.py: `raw_app_name.split(".", -1)[0].lower()` on Windows.
        for overlay, names, title, _ in GAMES:
            for app in names:
                if not app.endswith(".exe"):
                    continue
                stem = app.split(".", -1)[0].lower()
                with self.subTest(app=app, stem=stem):
                    self.assertEqual(self._route(stem, "windows", title), overlay)

    def test_every_process_name_on_every_platform(self):
        for overlay, names, title, _ in GAMES:
            for app in names:
                for os_name in ("windows", "macos", "linux"):
                    with self.subTest(app=app, os=os_name):
                        self.assertEqual(self._route(app, os_name, title), overlay)

    def test_title_does_not_reroute(self):
        for overlay, names, _, _ in GAMES:
            for title in ("", None, "some other title"):
                with self.subTest(app=names[0], title=title):
                    self.assertEqual(self._route(names[0], "linux", title), overlay)

    def test_spec_match_list_equals_the_mapping_keys(self):
        for _, names, _, spec in GAMES:
            match = yaml.safe_load(
                (RES / "overlay_sources" / spec).read_text(encoding="utf-8"))["match"]
            entry = [k for k in self.raw if names[0] in k.split(",")]
            with self.subTest(spec=spec):
                self.assertEqual(len(entry), 1)
                self.assertEqual(sorted(match), sorted(entry[0].split(",")))
                self.assertEqual(sorted(match), sorted(names))

    def test_every_named_file_exists(self):
        files = []
        for overlay, _, _, _ in GAMES:
            files += [overlay] if isinstance(overlay, str) else overlay
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
