"""The SHIPPED Telegram Desktop routing in `overlay-mapping.poly.yaml`.

Two Mac apps call themselves "Telegram": the Qt Telegram Desktop the set is
drawn from, and the Mac App Store's native client, which has other keys. So the
`telegram` entry has only windows and linux branches and no default overlay.
What it pins:

* Windows and Linux names load the Windows/Linux set;
* "Telegram" on macOS matches nothing, so it gets generic icons, not Ctrl keys;
* "Telegram Lite" (the Mac App Store build of the Qt app) and "Telegram
  Desktop" on macOS load the macOS set, and only on macOS;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

WIN = ["telegram_template.mods.png", "telegram_template.combo.mods.png"]
MAC = ["telegram_template_mac.mods.png", "telegram_template_mac.combo.mods.png",
       "telegram_template_mac.extra.mods.png"]


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as nano_routing_test)."""
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


class TelegramRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry("Telegram", self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_windows_and_linux_names_load_the_windows_set(self):
        for app, os_name in (("telegram", "windows"), ("telegram", "linux"),
                             ("telegramdesktop", "linux"),
                             ("telegram-desktop", "linux_gnome"),
                             ("org.telegram.desktop", "linux_kde")):
            self.assertEqual(self._route(app, os_name), WIN, (app, os_name))

    def test_plain_telegram_on_macos_matches_nothing(self):
        self.assertIsNone(self._route("telegram", "macos"))

    def test_telegram_desktop_on_macos_loads_the_macos_set(self):
        self.assertEqual(self._route("telegram desktop", "macos"), MAC)

    def test_telegram_lite_loads_the_macos_set_on_macos_only(self):
        self.assertEqual(self._route("telegram lite", "macos"), MAC)
        self.assertIsNone(self._route("telegram lite", "windows"))

    def test_every_named_file_exists(self):
        missing = [f for f in WIN + MAC if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
