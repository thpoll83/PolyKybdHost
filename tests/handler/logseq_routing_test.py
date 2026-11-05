"""The SHIPPED Logseq routing in `overlay-mapping.poly.yaml`.

The `logseq` entry has an `os: macos:` branch, because Logseq binds several
keys differently on macOS (`(if mac? ...)` in its shortcut config). What it
pins:

* Windows and Linux names, the Flatpak id included, load the Windows/Linux set;
* "logseq" on macOS loads the macOS set;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

WIN = ["logseq_template.mods.png", "logseq_template.combo.mods.png"]
MAC = ["logseq_template_mac.mods.png", "logseq_template_mac.combo.mods.png",
       "logseq_template_mac.extra.mods.png"]


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as telegram_routing_test)."""
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


class LogseqRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry("Logseq", self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_windows_and_linux_names_load_the_windows_set(self):
        for app, os_name in (("logseq", "windows"), ("logseq", "linux"),
                             ("com.logseq.logseq", "linux_gnome"),
                             ("logseq", "linux_kde")):
            self.assertEqual(self._route(app, os_name), WIN, (app, os_name))

    def test_macos_loads_the_macos_set(self):
        self.assertEqual(self._route("logseq", "macos"), MAC)

    def test_every_named_file_exists(self):
        missing = [f for f in WIN + MAC if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
