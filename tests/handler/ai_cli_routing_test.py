"""The SHIPPED routing of terminal AI coding CLIs: a terminal's WINDOW TITLE.

Claude Code, Codex, OpenCode, Gemini CLI, Qwen Code, GitHub Copilot CLI and
Kimi Code CLI replace the shell's title with their own; Aider sets none. Each route in
`&editor_titles` matches the CLI's own title format and its command name at
the command position. Drives `polyhost/res/overlay-mapping.poly.yaml` itself.
The formats are in `polyhost/res/overlay_sources/aicli/SOURCES.md`. What it
pins:

* every title format of every CLI loads that CLI's set, in Windows Terminal
  (which has its own overlay) and in the terminals without one;
* Qwen Code's "✳︎" / "◐︎" (with U+FE0E) load the Qwen set, not Claude Code's;
* titles that only mention a CLI (a prompt in ~/codex, `vim claude.md`,
  `cd opencode`, a Codex default title) keep the terminal's own overlay;
* an editor's mode report takes priority over a CLI title;
* every file named exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
WT_KEY = "windowsterminal,wt"
WT = "windowsterminal_template.mods.png"
VIM_INSERT = "vim_insert_template.mods.png"

# The first overlay file of each CLI's set, and the titles that must load it.
TITLES = {
    "claude_code_cli_template": [
        "✳ Claude Code",
        "✳ Fix the login redirect",
        "◐ Fix the login redirect",
        "◑ Fix the login redirect",
        "✳ Fix the login redirect — Konsole",
        "Documents — ✳ Claude Code — 80×24",
        "claude",
        "claude --resume",
        "Administrator: Command Prompt - claude",
        "Default (claude)",
        "~/src : claude — Konsole",
        "~/src> claude",                       # Nushell
        "claude | me@pc: ~/src | xonsh",       # xonsh
    ],
    "codex_cli_template": [
        "codex",
        "codex resume --last",
        "codex Fix the parser | PolyKybdHost",
        # What the shell integration's codex wrapper makes Codex write.
        "codex | PolyKybdHost",
        "codex | Fix the parser | PolyKybdHost",
        "codex ⠋ Fix the parser | PolyKybdHost",
        "[ ! ] Action Required | Fix the parser | PolyKybdHost",
        "[ . ] Action Required | PolyKybdHost",
        "● [ ! ] Action Required | PolyKybdHost",
        "Default (codex)",
        "/home/me/src> ^codex",                # Nushell, explicit external
    ],
    "opencode_template": [
        "OpenCode",
        "OpenCode — Konsole",
        "OC | Refactor the matcher",
        "opencode",
        "opencode run hello",
        "Default (opencode)",
    ],
    "gemini_cli_template": [
        "◇  Ready (PolyKybdHost)" + " " * 56,
        "✦  Working… (PolyKybdHost)",
        "✦  Reading the matcher (PolyKybdHost)",
        "✋  Action Required (PolyKybdHost)",
        "⏲  Working… (PolyKybdHost)",
        "Gemini CLI (PolyKybdHost)" + " " * 55,
        "gemini",
        "gemini -m gemini-2.5-pro",
    ],
    "qwen_code_template": [
        "Qwen - PolyKybdHost" + " " * 61,
        "\u25d0\ufe0e Qwen - PolyKybdHost",
        "\u2733\ufe0e Qwen - PolyKybdHost",
        "\u25d0\ufe0e Refactor session",
        "\u2733\ufe0e Refactor session",
        "qwen",
    ],
    "copilot_cli_template": [
        "GitHub Copilot",
        "🤖 Fix the parser",
        "Copilot: Fix the parser",
        "copilot",
        "copilot --resume",
    ],
    "kimi_cli_template": [
        "Kimi Code",
        "Kimi Code — Konsole",
        "Documents — Kimi Code — 80×24",
        "kimi",
        "kimi --resume ses-1",
        "~/src> kimi",                         # Nushell
        "Default (kimi)",
        "C:\\WINDOWS\\system32\\cmd.exe - kimi",
    ],
    "aider_template": [
        "aider",
        "aider --model sonnet main.py",
        "~/src> aider",                        # Nushell
        "aider | me@pc: ~/src | xonsh",        # xonsh
        "C:\\WINDOWS\\system32\\cmd.exe - aider",
        "Default (aider)",
    ],
}

# Titles that mention a CLI, or look like one, but are not that CLI running.
OTHER_TITLES = [
    "user@host: ~/codex",
    "user@host: ~/claude-notes",
    "vim claude.md",
    "vim CLAUDE.md",
    "cd opencode",
    "cat aider.log",
    "info gemini",
    "git log --grep codex",
    "~/src> cd",                              # Nushell in a folder, then cd codex
    "/home/me/codex",                         # Nushell, idle in ~/codex
    "me@pc: ~/claude | xonsh",                # xonsh, idle in ~/claude
    "Fix the parser | PolyKybdHost",          # Codex's default title
    "⠋ Fix the parser | PolyKybdHost",        # ... while it works
    "Qwen",
    "OpenCode — vim notes.txt — 80×24",      # Terminal.app in ~/OpenCode
    "OpenCode notes",
    "user@host: ~/OpenCode",
    "GitHub Copilot docs",
    "Kimi Code notes",
    "vim kimi.md",
    "user@host: ~/kimi",
    "bash",
]


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


def _files(entry):
    """The program's own files: a terminal's set layered underneath (an
    `Underlay`, drawn dimmed) is left out; `test_*_dims_the_terminal_set` checks it."""
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])
            if not getattr(f, "underlay", False)]


def _underlays(entry):
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])
            if getattr(f, "underlay", False)]


def _all_files(entry):
    """Every overlay file an entry names, its `os:` branches included. A route
    with no overlay of its own (ranger: only macOS and Linux branches) names
    files only in its branches."""
    out = list(_files(entry)) if "overlay" in entry else []
    for sub in (entry.get("os") or {}).values():
        out += _all_files(sub)
    return out


class AiCliMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        cls.routes = cls.raw[WT_KEY]["titles-contains"]

    def test_every_named_file_exists(self):
        for key, entry in self.routes.items():
            missing = [f for f in _all_files(entry)
                       if not (RES / "overlays" / f).is_file()]
            self.assertEqual(missing, [], key)

    def test_the_other_terminals_share_the_list(self):
        router = next(k for k in self.raw if isinstance(k, str)
                      and k.startswith("alacritty,"))
        self.assertIs(self.raw[router]["titles-contains"], self.routes)


class AiCliRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.handler = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.mapping = cls.handler.mapping

    def _route(self, app, title, url=None, os_name="windows"):
        m = find_matching_entry(title, self.mapping[app], url, os_name)
        return None if m is None else _files(m)

    def test_each_cli_title_loads_its_set_in_windows_terminal(self):
        for stem, titles in TITLES.items():
            for title in titles:
                files = self._route("windowsterminal", title)
                self.assertTrue(files and files[0].startswith(stem),
                                (stem, title, files))

    def test_each_cli_title_loads_its_set_in_the_other_terminals(self):
        for os_name in ("linux", "macos"):
            for app in ("kitty", "konsole", "iterm2", "warp", "mintty", "ghostty",
                            "roxterm", "mobaxterm"):
                for stem, titles in TITLES.items():
                    for title in titles:
                        files = self._route(app, title, os_name=os_name)
                        self.assertTrue(files and files[0].startswith(stem),
                                        (os_name, app, stem, title, files))

    def test_other_titles_keep_the_terminal_set(self):
        # On every OS: an `os:` branch is tried before the route's own title
        # regex, so each branch must repeat it.
        for title in OTHER_TITLES:
            for os_name in ("windows", "linux", "macos"):
                self.assertEqual(self._route("windowsterminal", title, os_name=os_name)[0],
                                 WT, (os_name, title))
                self.assertIsNone(self._route("alacritty", title, os_name=os_name),
                                  (os_name, title))

    def test_windows_terminal_dims_its_own_set_under_a_cli(self):
        for stem, titles in TITLES.items():
            m = find_matching_entry(titles[0], self.mapping["windowsterminal"], None, "windows")
            self.assertEqual(_underlays(m), ["windowsterminal_template.mods.png", "windowsterminal_template.combo.mods.png"], stem)
            # The CLI's files come last, so they win every key they draw.
            self.assertTrue(str(m["overlay"][-1]).startswith(stem), m["overlay"])

    def test_a_cli_in_a_terminal_is_hosted(self):
        from polyhost.handler.browser_url import hosted_in_terminal
        for app, os_name in (("gnome-terminal-server", "linux"), ("kitty", "linux"),
                             ("windowsterminal", "windows"), ("WindowsTerminal.exe", "windows")):
            entry = self.mapping[app.lower().removesuffix(".exe")]
            m = find_matching_entry("✳ Fix the parser", entry, None, os_name)
            self.assertTrue(hosted_in_terminal(app, m, self.mapping), app)
        # Windows Terminal's own set is not hosted, and neither is a non-terminal.
        own = find_matching_entry("PowerShell", self.mapping["windowsterminal"], None, "windows")
        self.assertFalse(hosted_in_terminal("windowsterminal", own, self.mapping))
        code = find_matching_entry("main.py - Visual Studio Code", self.mapping["code"], None, "linux")
        self.assertFalse(hosted_in_terminal("code", code, self.mapping))
        self.assertFalse(hosted_in_terminal("kitty", None, self.mapping))

    def test_a_forwarded_cli_in_a_terminal_is_hosted(self):
        from unittest import mock
        from polyhost.device.command_ids import OsType
        from polyhost.handler.remote_window import RemoteHandler
        with mock.patch.object(RemoteHandler, "listen_to_forwarder", lambda self: None):
            rh = RemoteHandler(self.mapping)
        rh.report_window(1, "gnome-terminal-server", "✳ Fix the parser", os=OsType.LINUX)
        rh.remote_changed({})
        self.assertTrue(rh.has_overlay())
        self.assertTrue(rh.template_is_hosted())
        rh.report_window(2, "code", "main.py - Visual Studio Code", os=OsType.LINUX)
        rh.remote_changed({})
        self.assertFalse(rh.template_is_hosted())

    def test_a_mode_report_takes_priority_over_a_cli_title(self):
        for titles in TITLES.values():
            for title in titles:
                self.assertEqual(self._route("windowsterminal", title, "vim://insert"),
                                 [VIM_INSERT], title)


if __name__ == "__main__":
    unittest.main()
