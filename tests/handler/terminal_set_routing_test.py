"""The SHIPPED WezTerm and kitty routing in `overlay-mapping.poly.yaml`.

Both terminals have a set of their own (overlay_sources/wezterm/, kitty/) and
host the editors, as Windows Terminal does. Each entry has an `os: macos`
branch for the Cmd set, and an `os:` branch is matched BEFORE the routes and
replaces the entry, so the branch repeats both routes. What it pins, on
Windows, Linux and macOS:

* a plain shell title loads the terminal's own set (Cmd set on macOS);
* a nano title loads the nano set, with the terminal's set underneath;
* a vim or emacs mode report loads the editor's set, and takes priority over
  a nano title;
* `hosted_in_terminal` is False for the terminal's own set (also for the
  macOS branch) and True for a program inside it;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import TERMINAL_APPS, hosted_in_terminal
from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

NANO = "nano_template.mods.png"
VIM_INSERT = "vim_insert_template.mods.png"
EMACS = "emacs_template.mods.png"


def _set(stem):
    return [f"{stem}.mods.png", f"{stem}.combo.mods.png", f"{stem}.extra.mods.png"]


# app names -> (default set, macOS set)
TERMINALS = {
    ("wezterm", "wezterm-gui", "org.wezfurlong.wezterm"):
        (_set("wezterm_template"), _set("wezterm_template_mac")),
    ("kitty",): (_set("kitty_template"), _set("kitty_template_mac")),
}
OSES = ("windows", "linux", "macos")
SHELL_TITLES = ("bash", "user@host: ~/nano-docs", "vim nano", "~/src> vim", "")
NANO_TITLES = ("nano notes.txt", "user@host - nano notes.txt", "Default (nano)")


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


def _files(entry):
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])
            if not getattr(f, "underlay", False)]


def _underlays(entry):
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])
            if getattr(f, "underlay", False)]


class TerminalSetRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _match(self, app, title, url=None, os_name="linux"):
        key = mapping_key(app, self.mapping)
        self.assertIsNotNone(key, app)
        return find_matching_entry(title, self.mapping[key], url, os_name)

    def _own(self, os_name, sets):
        return sets[1] if os_name == "macos" else sets[0]

    def test_every_name_is_a_terminal(self):
        for apps in TERMINALS:
            for app in apps:
                self.assertIn(app, TERMINAL_APPS, app)

    def test_a_plain_shell_loads_the_terminal_set(self):
        for apps, sets in TERMINALS.items():
            for app in apps:
                for os_name in OSES:
                    for title in SHELL_TITLES:
                        m = self._match(app, title, os_name=os_name)
                        self.assertIsNotNone(m, (app, os_name, title))
                        self.assertEqual(_files(m), self._own(os_name, sets),
                                         (app, os_name, title))
                        self.assertFalse(hosted_in_terminal(app, m, self.mapping),
                                         (app, os_name, title))

    def test_nano_routes_over_the_terminal_set(self):
        for apps, sets in TERMINALS.items():
            for app in apps:
                for os_name in OSES:
                    for title in NANO_TITLES:
                        m = self._match(app, title, os_name=os_name)
                        self.assertEqual(_files(m), [NANO, "nano_template.combo.mods.png"],
                                         (app, os_name, title))
                        self.assertEqual(_underlays(m), self._own(os_name, sets),
                                         (app, os_name, title))
                        self.assertTrue(hosted_in_terminal(app, m, self.mapping),
                                        (app, os_name, title))

    def test_editor_reports_route_over_the_terminal_set(self):
        for apps, sets in TERMINALS.items():
            for app in apps:
                for os_name in OSES:
                    m = self._match(app, "bash", "vim://insert", os_name)
                    self.assertEqual(_files(m), [VIM_INSERT], (app, os_name))
                    self.assertEqual(_underlays(m), self._own(os_name, sets), (app, os_name))
                    self.assertTrue(hosted_in_terminal(app, m, self.mapping))
                    m = self._match(app, "bash", "emacs://text-mode", os_name)
                    self.assertEqual(_files(m)[0], EMACS, (app, os_name))
                    # A mode report takes priority over a nano title.
                    m = self._match(app, NANO_TITLES[0], "vim://insert", os_name)
                    self.assertEqual(_files(m), [VIM_INSERT], (app, os_name))

    def test_an_unknown_report_keeps_the_terminal_set(self):
        for apps, sets in TERMINALS.items():
            for os_name in OSES:
                m = self._match(apps[0], "bash", "other://unknown", os_name)
                self.assertEqual(_files(m), self._own(os_name, sets), (apps[0], os_name))

    def test_every_named_file_exists(self):
        files = [f for sets in TERMINALS.values() for s in sets for f in s]
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
