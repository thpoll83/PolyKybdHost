"""The SHIPPED mapping routes the Vim plugin's `vim://<mode>` reports.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* every terminal on `TERMINAL_APPS` has an entry, and each routes every mode
  the plugin (`vim-plugin/`) sends to that mode's overlay, replacing the
  terminal's own overlay (`layer: false`);
* a terminal with no report keeps what it had before: Windows Terminal its
  own overlay, every other terminal NO match, so the generic shortcut harvest
  still runs for a plain shell;
* GUI Vim (gvim, MacVim, Neovide) routes the same URLs, and falls back to the
  Normal mode set without a report;
* the GUI entry's names are exactly the host's "vim" context reporters, and
  every file named exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import CONTEXT_REPORTERS, TERMINAL_APPS
from polyhost.handler.common import find_matching_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
GUI_KEY = "gvim,macvim,neovide"
MODES = ("normal", "visual", "select", "insert", "replace", "cmdline", "terminal")


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as blender_routing_test)."""
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


def _files(entry):
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])]


class VimMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        cls.names = {}
        for key, entry in cls.raw.items():
            for name in key.split(","):
                cls.names[name.strip().lower()] = (key, entry)

    def test_gui_names_are_the_vim_context_reporters(self):
        self.assertIn(GUI_KEY, self.raw)
        self.assertEqual(set(GUI_KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "vim"})

    def test_every_terminal_has_an_entry_with_the_editor_routes(self):
        for name in sorted(TERMINAL_APPS):
            self.assertIn(name, self.names, name)
            _, entry = self.names[name]
            routes = entry.get("urls-contains") or {}
            for mode in MODES:
                self.assertIn(f"vim://{mode}", routes, f"{name}: {mode}")

    def test_every_named_file_exists(self):
        seen = set()
        for name in list(TERMINAL_APPS) + GUI_KEY.split(","):
            _, entry = self.names[name]
            for sub in (entry.get("urls-contains") or {}).values():
                seen.update(_files(sub))
        seen.update(_files(self.raw[GUI_KEY]))
        self.assertEqual(len(seen), len(MODES))
        missing = [f for f in seen if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


class VimRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        cls.mapping = _overlay_handler_class()(raw).mapping

    def _route(self, app, url, os_name="linux"):
        m = find_matching_entry("~/src - bash", self.mapping[app], url, os_name)
        return None if m is None else _files(m)

    def test_each_terminal_routes_each_mode(self):
        for app in sorted(TERMINAL_APPS):
            for mode in MODES:
                self.assertEqual(self._route(app, f"vim://{mode}"),
                                 [f"vim_{mode}_template.mods.png"], f"{app} {mode}")

    def test_the_mode_replaces_the_terminal_overlay(self):
        got = self._route("windowsterminal", "vim://insert", "windows")
        self.assertEqual(got, ["vim_insert_template.mods.png"])

    def test_windows_terminal_without_a_report_keeps_its_own_overlay(self):
        self.assertEqual(self._route("windowsterminal", None, "windows"),
                         ["windowsterminal_template.mods.png",
                          "windowsterminal_template.combo.mods.png"])

    def test_other_terminals_without_a_report_match_nothing(self):
        # No match -> the generic shortcut harvest runs, as before the entry.
        for app in sorted(TERMINAL_APPS - {"windowsterminal", "wt"}):
            self.assertIsNone(self._route(app, None), app)
            self.assertIsNone(self._route(app, "emacs://unknown-mode"), app)

    def test_gui_vim_routes_each_mode(self):
        for app in GUI_KEY.split(","):
            for mode in MODES:
                for os_name in ("windows", "linux", "macos"):
                    self.assertEqual(self._route(app, f"vim://{mode}", os_name),
                                     [f"vim_{mode}_template.mods.png"], app)

    def test_gui_vim_without_a_report_is_normal_mode(self):
        for app in GUI_KEY.split(","):
            self.assertEqual(self._route(app, None), ["vim_normal_template.mods.png"])


if __name__ == "__main__":
    unittest.main()
