"""The SHIPPED routing of the QGIS set in `overlay-mapping.poly.yaml`.

What it pins:

* every Windows executable (qgis-bin, qgis-ltr-bin, qgis-dev-bin,
  qgis-qt6-bin) loads the Windows set;
* the Linux names (the process `qgis`, the WM_CLASS class QGIS3 / QGIS4 and
  the Wayland/Flatpak id org.qgis.qgis) load the Linux set;
* the macOS app ("QGIS", "QGIS-LTR") loads the macOS set;
* a name that only starts with "qgis" (the QGIS Server binary) matches nothing;
* every named file exists, and the Windows and Linux sets have the extra
  (Ctrl+Alt+Shift) layer.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"


def _set(name, *tiers):
    return [f"{name}.mods.png"] + [f"{name}.{t}.mods.png" for t in tiers]


QGIS = _set("qgis_template", "combo", "extra")
QGIS_MAC = _set("qgis_template_mac", "combo", "extra", "gui")
QGIS_LINUX = _set("qgis_template_linux", "combo", "extra")
ALL = [QGIS, QGIS_MAC, QGIS_LINUX]
TITLE = "Untitled Project — QGIS"


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as capcut_routing_test)."""
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


class QgisRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name, title=TITLE):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_windows_executables(self):
        for app in ("qgis-bin", "qgis-ltr-bin", "qgis-dev-bin", "qgis-qt6-bin"):
            with self.subTest(app=app):
                self.assertEqual(self._route(app, "windows"), QGIS)

    def test_linux_names(self):
        for app in ("qgis", "qgis3", "qgis4", "org.qgis.qgis"):
            with self.subTest(app=app):
                self.assertEqual(self._route(app, "linux"), QGIS_LINUX)

    def test_macos_app(self):
        for app in ("qgis", "qgis-ltr"):
            with self.subTest(app=app):
                self.assertEqual(self._route(app, "macos"), QGIS_MAC)

    def test_qgis_server_matches_nothing(self):
        self.assertIsNone(self._route("qgis_mapserver", "linux"))

    def test_every_named_file_exists(self):
        missing = [f for files in ALL for f in files
                   if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
