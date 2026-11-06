"""The SHIPPED tmux routing: a terminal's WINDOW TITLE, not a report.

tmux's `set-titles` option is off by default, so tmux never writes the outer
terminal's title; the title keeps what the shell or the terminal wrote when
tmux started. Drives `polyhost/res/overlay-mapping.poly.yaml` itself. What it
pins:

* every terminal loads the tmux set for every title format that shows tmux as
  the running command (the bash and zsh scripts in polyhost/res/shell/, fish,
  oh-my-zsh, cmd.exe over WSL, and the macOS Terminal, iTerm2 and Konsole
  formats);
* a title that only CONTAINS tmux elsewhere (`man tmux`, `vim .tmux.conf`, a
  prompt in ~/tmux) keeps the terminal's own overlay, and the other terminals
  match nothing for it;
* the nano titles still load the nano set, and a vim or emacs mode report
  takes priority over a tmux title;
* Windows Terminal's own set is drawn dimmed under the tmux set;
* the same set on Windows, Linux and macOS;
* every file named exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
WT_KEY = "windowsterminal,wt"

TMUX = ["tmux_template.mods.png"]
NANO = ["nano_template.mods.png", "nano_template.combo.mods.png"]
WT = "windowsterminal_template.mods.png"
VIM_INSERT = "vim_insert_template.mods.png"
EMACS = "emacs_template.mods.png"

# Titles that show tmux as the running command, by the program that wrote it.
TMUX_TITLES = {
    # The bash script in res/shell/, read on a pty with tmux 3.4.
    "bash script": "tmux -L pkprobe -f /dev/null new -s work",
    "bash script, plain": "tmux",
    "attach": "tmux attach -t work",
    "short attach": "tmux a",
    "oh-my-zsh": "tmux new -s work",
    "sudo": "sudo tmux",
    "fish": "tmux ~/s/docs",
    "fish over SSH": "[myhost] tmux ~/s/docs",
    "Terminal.app": "Documents — tmux — 80×24",
    "iTerm2": "Default (tmux)",
    "iTerm2, with arguments": "Default (tmux new -s work)",
    "Konsole": "~/src : tmux — Konsole",
    "cmd.exe": "C:\\WINDOWS\\system32\\cmd.exe - tmux",
    "Nushell": "~/docs> tmux",
    "Nushell, explicit external": "/home/me/docs> ^tmux",
    "xonsh": "tmux | me@pc: ~/docs | xonsh",
}

# Titles that contain the word tmux, or something like it, NOT as the command.
OTHER_TITLES = {
    "bash prompt in ~/tmux": "user@host: ~/tmux",
    "bash prompt, base name only": "user@host: tmux",
    "man page": "man tmux",
    "tmux.conf": "vim .tmux.conf",
    "vim on a file named tmux": "vim tmux",
    "cd": "cd tmux",
    "ssh starting tmux remotely": "ssh host -t tmux a",
    "Terminal.app in ~/tmux, running vim": "tmux — vim notes.txt — 80×24",
    "Konsole in ~/tmux, idle": "tmux : bash — Konsole",
    "tmux's own set-titles string": 'work:0:bash - "vm" ',
    "a plain shell": "bash",
    "xonsh, idle in ~/tmux": "me@pc: ~/tmux | xonsh",
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
    """The program's own files: a terminal's set layered underneath (an
    `Underlay`, drawn dimmed) is left out."""
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])
            if not getattr(f, "underlay", False)]


def _underlays(entry):
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])
            if getattr(f, "underlay", False)]


class TmuxMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        cls.routes = cls.raw[WT_KEY]["titles-contains"]

    def test_every_title_route_is_the_same_entry(self):
        keys = {k for k in self.routes if "tmux" in str(k)}
        self.assertEqual(keys, {"tmux", "(tmux)", "(tmux", "^tmux"})
        for key in keys:
            self.assertIs(self.routes[key], self.routes["tmux"], key)

    def test_no_os_branch(self):
        self.assertNotIn("os", self.routes["tmux"])

    def test_every_named_file_exists(self):
        files = _files(self.routes["tmux"])
        self.assertEqual(files, TMUX)
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


class TmuxRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.handler = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.mapping = cls.handler.mapping

    def _route(self, app, title, url=None, os_name="windows"):
        m = find_matching_entry(title, self.mapping[app], url, os_name)
        return None if m is None else _files(m)

    def test_tmux_titles_load_the_tmux_set_in_windows_terminal(self):
        for app in ("windowsterminal", "wt"):
            for fmt, title in TMUX_TITLES.items():
                self.assertEqual(self._route(app, title), TMUX, (app, fmt))

    def test_the_other_terminals_route_by_title_on_every_os(self):
        for os_name in ("linux", "macos", "windows"):
            for app in ("kitty", "konsole", "terminal", "iterm2", "gnome-terminal-server",
                        "alacritty", "wezterm", "ghostty"):
                for fmt, title in TMUX_TITLES.items():
                    self.assertEqual(self._route(app, title, os_name=os_name), TMUX,
                                     (os_name, app, fmt))

    def test_other_titles_keep_the_terminal_set(self):
        for fmt, title in OTHER_TITLES.items():
            self.assertEqual(self._route("windowsterminal", title)[0], WT, fmt)
            # Terminals with no overlay set of their own (not kitty or WezTerm).
            for app in ("alacritty", "konsole", "terminal", "iterm2"):
                self.assertIsNone(self._route(app, title, os_name="linux"), (app, fmt))

    def test_nano_still_loads_the_nano_set(self):
        for title in ("nano notes.txt", "Default (nano)", "~/src : nano — Konsole"):
            self.assertEqual(self._route("kitty", title, os_name="linux"), NANO, title)

    def test_a_mode_report_takes_priority_over_the_title(self):
        for title in TMUX_TITLES.values():
            self.assertEqual(self._route("windowsterminal", title, "vim://insert"),
                             [VIM_INSERT], title)
            self.assertEqual(self._route("kitty", title, "emacs://text-mode",
                                         os_name="linux")[0], EMACS, title)

    def test_windows_terminal_dims_its_own_set_under_tmux(self):
        m = find_matching_entry("tmux", self.mapping["windowsterminal"], None, "windows")
        self.assertEqual(_underlays(m), ["windowsterminal_template.mods.png",
                                         "windowsterminal_template.combo.mods.png"])
        self.assertEqual(str(m["overlay"][-1]), TMUX[0])

    def test_tmux_in_a_terminal_is_hosted(self):
        from polyhost.handler.browser_url import hosted_in_terminal
        for app, os_name in (("kitty", "linux"), ("windowsterminal", "windows")):
            m = find_matching_entry("tmux attach", self.mapping[app], None, os_name)
            self.assertTrue(hosted_in_terminal(app, m, self.mapping), app)


if __name__ == "__main__":
    unittest.main()
