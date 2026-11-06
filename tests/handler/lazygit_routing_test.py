"""The SHIPPED lazygit routing: a terminal's WINDOW TITLE, as for GNU nano.

lazygit sets no window title (no OSC 0/2 write in its source, v0.66.2), so
the host sees it only when the shell or the terminal puts the running command
into the title. Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What
it pins:

* Windows Terminal and the other terminals load the lazygit set for every
  title format that shows lazygit as the running command;
* a title that only CONTAINS lazygit elsewhere (a prompt in ~/lazygit, `vim
  lazygit.yml`, `man lazygit`) keeps the terminal's own overlay, or matches
  nothing in a terminal without a set;
* an editor's mode report takes priority over the title;
* the nano titles still load the nano set;
* every file named exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
WT_KEY = "windowsterminal,wt"

LAZYGIT = ["lazygit_template.mods.png", "lazygit_template.combo.mods.png"]
NANO = ["nano_template.mods.png", "nano_template.combo.mods.png"]
WT = "windowsterminal_template.mods.png"
VIM_INSERT = "vim_insert_template.mods.png"

# Titles that show lazygit as the running command, by the program that wrote it.
LAZYGIT_TITLES = {
    "cmd.exe": "C:\\WINDOWS\\system32\\cmd.exe - lazygit",
    "Terminal.app": "myrepo — lazygit — 120×40",
    "iTerm2": "Default (lazygit)",
    "Konsole": "~/src/myrepo : lazygit — Konsole",
    "fish": "lazygit ~/s/myrepo",
    "fish over SSH": "[myhost] lazygit ~/s/myrepo",
    "oh-my-zsh / bash script": "lazygit",
    "with a path option": "lazygit -p ~/src/myrepo",
    "subcommand": "lazygit log",
    "Nushell": "~/src/myrepo> lazygit",
    "Nushell, explicit external": "~/src/myrepo> ^lazygit",
    "xonsh": "lazygit | me@pc: ~/src/myrepo | xonsh",
}

# Titles that contain the word lazygit NOT as the command.
OTHER_TITLES = {
    "bash prompt in ~/lazygit": "user@host: ~/lazygit",
    "vim on the config": "vim lazygit.yml",
    "vim, file named lazygit": "vim lazygit",
    "man page": "man lazygit",
    "cd": "cd lazygit",
    "Terminal.app in ~/lazygit, running vim": "lazygit — vim notes.txt — 80×24",
    "Konsole in ~/lazygit, idle": "lazygit : bash — Konsole",
    "a plain shell": "bash",
}

OTHER_TERMINALS = ("kitty", "konsole", "terminal", "iterm2", "conhost", "alacritty")


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
    """The program's own files: a terminal's set layered underneath (an
    `Underlay`, drawn dimmed) is left out."""
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])
            if not getattr(f, "underlay", False)]


class LazygitMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_every_title_route_is_the_same_entry(self):
        routes = self.raw[WT_KEY]["titles-contains"]
        keys = {k for k in routes if "lazygit" in str(k)}
        self.assertEqual(keys, {"lazygit", "(lazygit)", "(lazygit", "^lazygit"})
        for key in keys:
            self.assertIs(routes[key], routes["lazygit"], key)

    def test_every_named_file_exists(self):
        files = _files(self.raw[WT_KEY]["titles-contains"]["lazygit"])
        self.assertEqual(files, LAZYGIT)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


class LazygitRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, title, url=None, os_name="windows"):
        m = find_matching_entry(title, self.mapping[app], url, os_name)
        return None if m is None else _files(m)

    def test_lazygit_titles_load_the_set_in_windows_terminal(self):
        for app in ("windowsterminal", "wt"):
            for fmt, title in LAZYGIT_TITLES.items():
                self.assertEqual(self._route(app, title), LAZYGIT, (app, fmt))

    def test_lazygit_titles_load_the_set_in_the_other_terminals(self):
        for os_name in ("windows", "macos", "linux"):
            for app in OTHER_TERMINALS:
                for fmt, title in LAZYGIT_TITLES.items():
                    self.assertEqual(self._route(app, title, os_name=os_name),
                                     LAZYGIT, (os_name, app, fmt))

    def test_other_titles_keep_the_terminal_set(self):
        for fmt, title in OTHER_TITLES.items():
            self.assertEqual(self._route("windowsterminal", title)[0], WT, fmt)

    def test_other_titles_leave_the_other_terminals_unmatched(self):
        for app in OTHER_TERMINALS:
            for fmt, title in OTHER_TITLES.items():
                self.assertIsNone(self._route(app, title, os_name="linux"), (app, fmt))

    def test_a_mode_report_takes_priority_over_the_title(self):
        for title in LAZYGIT_TITLES.values():
            self.assertEqual(self._route("kitty", title, "vim://insert"),
                             [VIM_INSERT], title)

    def test_nano_still_routes_to_nano(self):
        for app in ("windowsterminal", "kitty"):
            self.assertEqual(self._route(app, "nano notes.txt"), NANO, app)
            self.assertEqual(self._route(app, "Default (nano)"), NANO, app)


if __name__ == "__main__":
    unittest.main()
