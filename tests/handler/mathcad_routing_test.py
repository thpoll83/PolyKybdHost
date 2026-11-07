"""The SHIPPED routing of the PTC Mathcad Prime set in `overlay-mapping.poly.yaml`.

What it pins:

* `MathcadPrime.exe` (reported as `mathcadprime`) loads the Mathcad set on
  Windows;
* `mathcad` alone (the retired Mathcad 15) matches nothing;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

MATHCAD = ["mathcad_template.mods.png", "mathcad_template.combo.mods.png"]


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


class MathcadRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name, title="untitled"):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_mathcad_prime_routes_on_windows(self):
        for title in ("Untitled1 - PTC Mathcad Prime 12.0.1.0",
                      "beam.mcdx - PTC Mathcad Prime 11.0.1.0"):
            with self.subTest(title=title):
                self.assertEqual(self._route("mathcadprime", "windows", title),
                                 MATHCAD)

    def test_mathcad_15_is_not_matched(self):
        self.assertIsNone(self._route("mathcad", "windows", "Mathcad - [Untitled:1]"))

    def test_every_named_file_exists(self):
        missing = [f for f in MATHCAD if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
