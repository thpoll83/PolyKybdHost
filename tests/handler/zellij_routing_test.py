"""The SHIPPED Zellij routing: the terminal's WINDOW TITLE that Zellij writes.

Zellij runs inside a terminal and has no report of its own, so the host sees
it only in the title. Drives `polyhost/res/overlay-mapping.poly.yaml` itself.
What it pins:

* Zellij up to 0.42 ("Zellij (<session>) - <pane title>") loads the set in
  every terminal, and so does 0.43.1+ ("<session> | <pane title>") for a
  session name Zellij generated;
* `zellij` at the command position (the shell integration's title before
  Zellij writes its own; Konsole, iTerm2, Terminal.app and cmd.exe formats)
  loads it too;
* a title that only CONTAINS zellij elsewhere, a named session, or a
  hyphenated word that is not a generated session name does not;
* Zellij's title is chosen over nano's in the same title, and a vim or emacs
  mode report is chosen over Zellij;
* the route is a program inside the terminal (`hosted_in_terminal`), so the
  terminal's own shortcuts stay dimmed;
* every named file exists, and the nano titles still load nano.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
WT_KEY = "windowsterminal,wt"

ZELLIJ = ["zellij_template.mods.png", "zellij_template.combo.mods.png"]
NANO = ["nano_template.mods.png", "nano_template.combo.mods.png"]
WT = "windowsterminal_template.mods.png"
VIM_INSERT = ["vim_insert_template.mods.png"]
EMACS = "emacs_template.mods.png"

TERMINALS = ("kitty", "konsole", "terminal", "iterm2", "alacritty", "wezterm",
             "ghostty", "gnome-terminal-server", "foot")

# Titles Zellij writes, or that show zellij as the running command.
ZELLIJ_TITLES = {
    # make_terminal_title() up to v0.42.2.
    "0.42, pane title": "Zellij (eager-tiger) - user@host: ~/src",
    "0.42, named session": "Zellij (work) - user@host: ~/src",
    "0.42, nano in the pane": "Zellij (work) - nano notes.txt",
    # v0.43.0 with an empty pane title.
    "0.43.0, no pane title": "Zellij (work) ",
    # v0.43.1 and later, a generated session name.
    "0.43.1+, no pane title": "adamant-aardvark",
    "0.43.1+, pane title": "zippy-zebra | user@host: ~/src",
    "0.43.1+, nano in the pane": "lucky-lemur | nano notes.txt",
    "0.43.1+, old spelling": "brave-iguanadon | htop",
    "0.43.1+, new spelling": "brave-iguanodon | htop",
    # zellij at the command position.
    "shell integration": "zellij",
    "shell integration, attach": "zellij attach work",
    "shell integration, sudo-less option": "zellij -s work",
    "Konsole": "~/src : zellij — Konsole",
    "iTerm2": "Default (zellij)",
    "iTerm2, with arguments": "Default (zellij attach work)",
    "Terminal.app": "Documents — zellij — 80×24",
    "cmd.exe": "C:\\WINDOWS\\system32\\cmd.exe - zellij",
    "Nushell": "~/docs> zellij",
}

# Titles that must NOT load the set.
OTHER_TITLES = {
    "0.43.1+, named session": "work | user@host: ~/src",
    "0.43.1+, named session alone": "work",
    "hyphenated command": "docker-compose up",
    "hyphenated command alone": "git-lfs",
    "generated name plus letters": "adamant-aardvarks",
    "unknown adjective": "sleepy-tiger | user@host: ~",
    "prompt in ~/zellij": "user@host: ~/zellij",
    "vim on the config": "vim zellij.kdl",
    "vim on a file named zellij": "vim zellij",
    "info page": "info zellij",  # `man zellij` loads the less set (tui_routing_test)
    "cd": "cd zellij",
    "word in a sentence": "Notes about Zellij",
    "a plain shell": "bash",
}


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
    """The program's own files; a terminal's set layered underneath (an
    `Underlay`) is left out."""
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])
            if not getattr(f, "underlay", False)]


class ZellijMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_every_title_route_is_the_same_entry(self):
        routes = self.raw[WT_KEY]["titles-contains"]
        keys = {k for k in routes if "zellij" in str(k).lower()}
        self.assertEqual(keys, {"Zellij", "zellij", "(zellij)", "(zellij", "^zellij"})
        for key in keys:
            self.assertIs(routes[key], routes["Zellij"], key)

    def test_the_session_name_route_names_the_same_files(self):
        # The shared map also holds ranger's "ranger:<path>" route.
        (route,) = [v for k, v in self.raw[WT_KEY]["titles-match"].items()
                    if str(k).startswith("^(?:adamant")]
        self.assertEqual(route["overlay"], ZELLIJ)
        self.assertEqual(self.raw[WT_KEY]["titles-contains"]["Zellij"]["overlay"], ZELLIJ)

    def test_every_named_file_exists(self):
        missing = [f for f in ZELLIJ if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


class ZellijRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.handler = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.mapping = cls.handler.mapping

    def _match(self, app, title, url=None, os_name="linux"):
        return find_matching_entry(title, self.mapping[app], url, os_name)

    def _route(self, app, title, url=None, os_name="linux"):
        m = self._match(app, title, url, os_name)
        return None if m is None else _files(m)

    def test_zellij_titles_load_the_set_in_every_terminal(self):
        for app in TERMINALS:
            for os_name in ("linux", "macos"):
                for fmt, title in ZELLIJ_TITLES.items():
                    self.assertEqual(self._route(app, title, os_name=os_name), ZELLIJ,
                                     (app, os_name, fmt))

    def test_zellij_titles_load_the_set_in_windows_terminal(self):
        for app in ("windowsterminal", "wt"):
            for fmt, title in ZELLIJ_TITLES.items():
                self.assertEqual(self._route(app, title, os_name="windows"), ZELLIJ,
                                 (app, fmt))

    def test_other_titles_do_not_load_the_set(self):
        for app in TERMINALS:
            for fmt, title in OTHER_TITLES.items():
                route = self._route(app, title)
                if app in ("kitty", "wezterm"):  # their own set, no Zellij
                    self.assertTrue(route and str(route[0]).startswith(app), (app, fmt))
                else:
                    self.assertIsNone(route, (app, fmt))
        for fmt, title in OTHER_TITLES.items():
            self.assertEqual(self._route("windowsterminal", title, os_name="windows")[0],
                             WT, fmt)

    def test_a_mode_report_takes_priority_over_zellij(self):
        for title in ZELLIJ_TITLES.values():
            self.assertEqual(self._route("kitty", title, "vim://insert"), VIM_INSERT, title)
            self.assertEqual(self._route("wt", title, "emacs://text-mode",
                                         os_name="windows")[0], EMACS, title)

    def test_zellij_is_hosted_in_the_terminal(self):
        from polyhost.handler.browser_url import hosted_in_terminal
        for title in ("Zellij (work) - user@host: ~", "zippy-zebra | user@host: ~",
                      "Default (zellij)"):
            self.assertTrue(hosted_in_terminal("kitty", self._match("kitty", title),
                                               self.mapping), title)

    def test_nano_titles_still_load_nano(self):
        for title in ("nano notes.txt", "Default (nano)", "~/src : nano — Konsole",
                      "Documents — nano notes.txt — 80×24"):
            self.assertEqual(self._route("kitty", title), NANO, title)


if __name__ == "__main__":
    unittest.main()
