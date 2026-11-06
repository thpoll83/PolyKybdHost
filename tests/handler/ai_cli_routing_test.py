"""The SHIPPED routing of terminal AI coding CLIs: a terminal's WINDOW TITLE.

Claude Code, Codex, OpenCode, Gemini CLI, Qwen Code and GitHub Copilot CLI
replace the shell's title with their own; Aider sets none. Each route in
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
    "less aider.log",
    "man gemini",
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
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])]


def _all_files(entry):
    """Every overlay file an entry names, its `os:` branches included."""
    out = list(_files(entry))
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
                self.assertIsNone(self._route("kitty", title, os_name=os_name),
                                  (os_name, title))

    def test_a_mode_report_takes_priority_over_a_cli_title(self):
        for titles in TITLES.values():
            for title in titles:
                self.assertEqual(self._route("windowsterminal", title, "vim://insert"),
                                 [VIM_INSERT], title)


if __name__ == "__main__":
    unittest.main()
