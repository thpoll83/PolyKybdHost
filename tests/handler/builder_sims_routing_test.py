"""The SHIPPED routing of the transport and builder simulation sets in
`overlay-mapping.poly.yaml`.

Every game here uses the same keys on every OS, so each entry has one set and
no `os:` branch. What it pins:

* every process name of a game loads that game's set on all three platforms;
* a window title does not reroute it;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

# overlay -> (process names, a window title of the game)
SETS = {
    "simutrans_template.mods.png": (
        ("simutrans", "simutrans.exe", "com.simutrans.simutrans"),
        "Simutrans 125.0.1"),
}


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


def _files(overlay):
    return [overlay] if isinstance(overlay, str) else list(overlay)


class BuilderSimsRoutingTest(unittest.TestCase):

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
        for overlay, (apps, title) in SETS.items():
            for app in apps:
                for os_name in ("windows", "macos", "linux"):
                    for shown in (title, "", None):
                        with self.subTest(app=app, os=os_name, title=shown):
                            self.assertEqual(
                                _files(self._route(app, os_name, shown)), [overlay])

    def test_every_named_file_exists(self):
        missing = [f for f in SETS if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
