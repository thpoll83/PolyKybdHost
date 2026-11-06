"""The SHIPPED Monkeytype and keybr routing in `overlay-mapping.poly.yaml`.

Both are web pages, so they route through the browser entries by the tab's URL
(and, for Monkeytype, by the tab title when no URL is known). What it pins:

* monkeytype.com's test page loads the Monkeytype set in Chrome, Edge and
  Safari, on Windows, Linux and macOS (the macOS set binds Cmd);
* Firefox loads the Firefox set, without Ctrl/Cmd+Shift+P, which Firefox
  reserves for a private window;
* keybr.com's practice page ("/" or "/<locale>") loads the keybr set;
* other pages of either site, and a search for them, keep the browser set;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

MT = ["monkeytype_template.mods.png", "monkeytype_template.combo.mods.png"]
MT_MAC = ["monkeytype_template_mac.mods.png", "monkeytype_template_mac.extra.mods.png"]
MT_FF = ["monkeytype_firefox_template.mods.png"]
KB = ["keybr_template.mods.png"]
KB_MAC = ["keybr_template_mac.mods.png"]

MT_TITLE = "Monkeytype | A minimalistic, customizable typing test"


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


def _files(match):
    return [] if match is None else [str(f) for f in
                                     (match["overlay"] if isinstance(match["overlay"], list)
                                      else [match["overlay"]])]


class TypingTestSitesRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from polyhost.device.command_ids import OsType
        cls.os = OsType
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def assertSet(self, files, want):
        """`files` holds the site set `want` and no other site set. The matcher
        puts the browser's own set beside it for the keys the site leaves free."""
        for f in want:
            self.assertIn(f, files)
        others = [f for f in files if f.startswith(("monkeytype_", "keybr_")) and f not in want]
        self.assertEqual(others, [], files)

    def _route(self, app, os_name, title, url):
        key = mapping_key(app, self.mapping)
        self.assertIsNotNone(key, app)
        return _files(find_matching_entry(title, self.mapping[key], url,
                                          self.os[os_name], title_known=True))

    def test_monkeytype_test_page_by_url(self):
        for app, os_name, want in (
                ("chrome", "WINDOWS", MT), ("msedge", "WINDOWS", MT),
                ("google-chrome", "LINUX", MT), ("google chrome", "MACOS", MT_MAC),
                ("safari", "MACOS", MT_MAC),
                ("firefox", "WINDOWS", MT_FF), ("firefox", "LINUX", MT_FF),
                ("firefox", "MACOS", MT_FF)):
            for url in ("https://monkeytype.com/", "https://www.monkeytype.com/",
                        "https://monkeytype.com/?testSettings=abc"):
                with self.subTest(app=app, os=os_name, url=url):
                    self.assertSet(self._route(app, os_name, MT_TITLE, url), want)

    def test_monkeytype_by_title_without_url(self):
        for app, os_name, want in (("chrome", "WINDOWS", MT), ("google chrome", "MACOS", MT_MAC),
                                   ("firefox", "WINDOWS", MT_FF), ("firefox", "MACOS", MT_FF)):
            with self.subTest(app=app, os=os_name):
                self.assertSet(self._route(app, os_name, MT_TITLE + " - Google Chrome", None),
                               want)

    def test_keybr_practice_page(self):
        for app, os_name, want in (
                ("chrome", "WINDOWS", KB), ("firefox", "WINDOWS", KB),
                ("firefox", "LINUX", KB), ("google chrome", "MACOS", KB_MAC),
                ("safari", "MACOS", KB_MAC), ("firefox", "MACOS", KB_MAC)):
            for url in ("https://www.keybr.com/", "https://keybr.com/",
                        "https://www.keybr.com/de", "https://www.keybr.com/pt-br/"):
                with self.subTest(app=app, os=os_name, url=url):
                    self.assertSet(self._route(app, os_name, "Practice", url), want)

    def test_other_pages_keep_the_browser_set(self):
        cases = (
            ("https://monkeytype.com/settings", "Settings | Monkeytype"),
            ("https://monkeytype.com/account", "Account | Monkeytype"),
            ("https://www.google.com/search?q=monkeytype.com", "monkeytype.com - Google Search"),
            ("https://github.com/monkeytypegame/monkeytype", "x"),
            ("https://www.keybr.com/typing-test", "Typing Test"),
            ("https://www.keybr.com/multiplayer", "Multiplayer"),
            ("https://www.keybr.com/de/help", "Help"),
            ("https://www.google.com/search?q=keybr.com", "keybr.com - Google Search"))
        for app in ("chrome", "firefox"):
            for os_name in ("WINDOWS", "MACOS"):
                for url, title in cases:
                    with self.subTest(app=app, os=os_name, url=url):
                        files = self._route(app, os_name, title, url)
                        self.assertFalse(any(s in f for f in files
                                             for s in ("monkeytype_", "keybr_")), files)
                # Without a URL, a title that only names Monkeytype is not the test.
                with self.subTest(app=app, os=os_name, title="settings"):
                    files = self._route(app, os_name, "Settings | Monkeytype", None)
                    self.assertFalse(any("monkeytype_" in f for f in files), files)

    def test_every_named_file_exists(self):
        missing = [f for f in MT + MT_MAC + MT_FF + KB + KB_MAC
                   if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
