"""The SHIPPED routing of the Houdini set in `overlay-mapping.poly.yaml`.

Houdini binds Ctrl on Windows/Linux and Cmd on macOS, so the entry has an
`os: macos` branch. What it pins:

* every launcher name of every edition (FX, Core, Apprentice, Indie, Escape)
  and the Linux `houdini-bin` binary load the Windows/Linux set;
* the macOS app names with a trailing dotted version (`Houdini FX 22.0.368`)
  reach the entry and load the macOS set;
* every file the route names exists.

The names are the expected process / app names; none was checked on an
install (see overlay_sources/houdini/SOURCES.md).
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

HOUDINI = ["houdini_template.mods.png", "houdini_template.combo.mods.png"]
HOUDINI_MAC = ["houdini_template_mac.mods.png", "houdini_template_mac.combo.mods.png"]

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
