"""The SHIPPED qutebrowser routing in `overlay-mapping.poly.yaml`.

qutebrowser binds the Control key on every OS (it swaps Qt's macOS Ctrl/Cmd
mapping back), so the `qutebrowser` entry has one set and no `os:` branch. It
has no web-app routing: the URL-reporting extension does not run there. What
it pins:

* `qutebrowser` (Windows, macOS, Linux) and `org.qutebrowser.qutebrowser`
  (Wayland app id, Flathub) load the set on all three platforms;
* a page title that names a web app does not reroute it;
* `python3` (a source checkout) is not mapped to it;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

SET = ["qutebrowser_template.mods.png", "qutebrowser_template.combo.mods.png"]


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as telegram_routing_test)."""
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


class QutebrowserRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name, title="Example Domain - qutebrowser"):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_every_platform_loads_the_one_set(self):
        for os_name in ("windows", "macos", "linux"):
            with self.subTest(os=os_name):
                self.assertEqual(self._route("qutebrowser", os_name), SET)

    def test_wayland_app_id_loads_the_set(self):
        self.assertEqual(self._route("org.qutebrowser.qutebrowser", "linux"), SET)

    def test_web_app_title_does_not_reroute(self):
        self.assertEqual(self._route("qutebrowser", "linux",
                                     "Inbox - Gmail - qutebrowser"), SET)

    def test_python_interpreter_is_not_qutebrowser(self):
        key = mapping_key("python3", self.mapping)
        if key is not None:
            self.assertNotEqual(self._route("python3", "linux"), SET)

    def test_every_named_file_exists(self):
        missing = [f for f in SET if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
