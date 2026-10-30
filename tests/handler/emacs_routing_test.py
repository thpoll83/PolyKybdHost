"""The SHIPPED Emacs routing: the `emacs` entry and the terminal entries.

Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* GUI Emacs with an `emacs://<major-mode>` report gets that mode's set
  (org-mode, Dired) and every other mode the global set; with no report, the
  global set;
* org-mode's files are the global set FIRST and the org set after it, so the
  org keys take priority and every other key keeps its global icon;
* a terminal takes the same routing from the report of an `emacs -nw` in it,
  and one running a shell (no report) is unchanged: the terminal entry with
  no overlay of its own matches nothing, so the generic shortcut harvest runs,
  and Windows Terminal keeps its own set;
* the whole chain from a report to the overlay, through `BrowserUrlProvider`;
* the GUI entry's names are exactly the `emacs` context reporters, and every
  terminal on `TERMINAL_APPS` carries the routes;
* every file named exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import (
    CONTEXT_REPORTERS, TERMINAL_APPS, BrowserUrlProvider)
from polyhost.handler.common import find_matching_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
GUI_KEY = "emacs"

GLOBAL = "emacs_template.mods.png"
ORG = "emacs_org_template.mods.png"
DIRED = "emacs_dired_template.mods.png"
WT = "windowsterminal_template.mods.png"


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (same tolerance as blender_routing_test)."""
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


def _emacs_routes(entry):
    return [k for k in (entry.get("urls-contains") or {}) if k.startswith("emacs://")]


class EmacsMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_gui_names_are_the_emacs_context_reporters(self):
        self.assertIn(GUI_KEY, self.raw)
        self.assertEqual(set(GUI_KEY.split(",")),
                         {n for n, t in CONTEXT_REPORTERS.items() if t == "emacs"})

    def test_every_terminal_carries_the_emacs_routes(self):
        terminals = set(TERMINAL_APPS)
        covered = set()
        for key, e in self.raw.items():
            names = {n.strip().lower() for n in key.split(",")}
            if not names & terminals:
                continue
            self.assertEqual(_emacs_routes(e), _emacs_routes(self.raw[GUI_KEY]), key)
            covered |= names & terminals
            # An editor's mode replaces a terminal's own overlay; an entry
            # with no overlay of its own has nothing to layer.
            if "overlay" in e:
                self.assertIs(e.get("layer"), False, key)
        self.assertEqual(covered, terminals)

    def test_specific_modes_come_before_the_catch_all(self):
        routes = _emacs_routes(self.raw[GUI_KEY])
        self.assertEqual(routes[-1], "emacs://")
        self.assertEqual(set(routes[:-1]), {"emacs://org-mode", "emacs://dired-mode"})

    def test_every_named_file_exists(self):
        files = set()
        routes = self.raw[GUI_KEY]["urls-contains"]
        for e in [self.raw[GUI_KEY], *(routes[k] for k in _emacs_routes(self.raw[GUI_KEY]))]:
            files |= set(_files(e))
        self.assertGreaterEqual(len(files), 7)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


class EmacsRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.handler = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.mapping = cls.handler.mapping

    def _route(self, app, url, title="", os_name="linux"):
        m = find_matching_entry(title, self.mapping[app], url, os_name)
        return None if m is None else _files(m)

    def test_gui_emacs_routes_each_mode(self):
        cases = {
            "emacs://org-mode": ORG,
            "emacs://org-mode/normal": ORG,         # evil state appended
            "emacs://dired-mode": DIRED,
            "emacs://fundamental-mode": GLOBAL,
            "emacs://emacs-lisp-mode/insert": GLOBAL,
            "emacs://org-agenda-mode": GLOBAL,      # not org-mode's keymap
            "emacs://wdired-mode": GLOBAL,          # editable Dired: editing keys
        }
        for os_name in ("linux", "windows", "macos"):
            for url, want in cases.items():
                files = self._route("emacs", url, os_name=os_name)
                # The set's own primary file is the last `.mods.png` named.
                primary = [f for f in files if not f.endswith(".combo.mods.png")
                           and not f.endswith(".extra.mods.png")][-1]
                self.assertEqual(primary, want, (url, os_name))

    def test_gui_emacs_without_a_report_is_the_global_set(self):
        self.assertEqual(self._route("emacs", None)[0], GLOBAL)

    def test_org_draws_on_top_of_global(self):
        files = self._route("emacs", "emacs://org-mode")
        self.assertEqual(files[0], GLOBAL)
        self.assertLess(files.index(GLOBAL), files.index(ORG))
        self.assertFalse([f for f in self.mapping["emacs"]["urls-contains"]["emacs://org-mode"]
                          ["overlay"] if getattr(f, "underlay", False)])

    def test_dired_is_a_complete_set(self):
        self.assertEqual(self._route("emacs", "emacs://dired-mode"),
                         [DIRED, "emacs_dired_template.combo.mods.png"])

    def test_terminal_with_a_report_takes_the_editor_set(self):
        for app in ("kitty", "konsole", "org.kde.konsole", "gnome-terminal-server",
                    "xterm", "alacritty", "terminal", "iterm2", "windowsterminal", "wt"):
            self.assertEqual(self._route(app, "emacs://dired-mode"), _files(
                self.mapping["emacs"]["urls-contains"]["emacs://dired-mode"]), app)
            self.assertEqual(self._route(app, "emacs://text-mode")[0], GLOBAL, app)

    def test_terminal_without_a_report_is_unchanged(self):
        # No entry of its own: matches nothing, so the generic path runs.
        for app in ("kitty", "konsole", "xterm", "terminal", "iterm2", "conhost"):
            self.assertIsNone(self._route(app, None, title="bash"), app)
            # A URL no route names (the vim routes are not this test's concern).
            self.assertIsNone(self._route(app, "other://x", title="x"), app)
        # Windows Terminal keeps its own set.
        self.assertEqual(self._route("windowsterminal", None)[0], WT)
        self.assertEqual(self._route("wt", None)[0], WT)

    def test_an_unmatched_terminal_leaves_no_template_on_the_board(self):
        h = self.handler
        h.current_entry = None
        h.last_entry = None
        h.title, h.current_url = "bash", None
        found, _ = h.try_to_match_window("kitty", self.mapping["kitty"])
        self.assertFalse(found)
        self.assertFalse(h.covered_by_template())

    def test_report_to_overlay_through_the_provider(self):
        p = BrowserUrlProvider(macos_lookup=lambda app: None)
        p.update(app="emacs", url="emacs://org-mode", focused=True, pid=42, input_age=0.0)
        for app in ("kitty", "emacs"):
            files = self._route(app, p.current_url(app))
            self.assertIn(ORG, files, app)
        # A report never reaches a non-terminal app.
        self.assertIsNone(p.current_url("code"))
        # Focus-out (the terminal's focus event): the shell gets nothing.
        p.update(app="emacs", url=None, focused=False, pid=42)
        self.assertIsNone(self._route("kitty", p.current_url("kitty")))


if __name__ == "__main__":
    unittest.main()
