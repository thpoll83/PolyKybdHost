"""The SHIPPED GNU nano routing: a terminal's WINDOW TITLE, not a report.

nano has no plugin and sets no title, so the host sees it only when the shell
or the terminal puts the running command into the title. Drives
`polyhost/res/overlay-mapping.poly.yaml` itself. What it pins:

* Windows Terminal loads the nano set for every title format that shows nano
  as the running command (cmd.exe, fish, oh-my-zsh, the bash and PowerShell
  snippets in overlay_sources/nano/SOURCES.md, and the macOS Terminal, iTerm2
  and Konsole formats the shared `&editor_titles` list is written for);
* a title that only CONTAINS nano elsewhere (`vim nano`, `man nano`, a prompt
  in ~/nano-docs, Terminal.app in a directory named nano) keeps the
  terminal's own overlay;
* an editor's mode report takes priority over a nano title;
* the other terminals (the entry with no overlay of its own) do not route by
  title: that entry matches only through `urls-contains`
  (`tests/handler/matcher_test.py::TestRoutesOnlyEntry`);
* every file named exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
WT_KEY = "windowsterminal,wt"

NANO = "nano_template.mods.png"
WT = "windowsterminal_template.mods.png"
VIM_INSERT = "vim_insert_template.mods.png"
EMACS = "emacs_template.mods.png"

# Titles that show nano as the running command, by the program that wrote it.
NANO_TITLES = {
    "cmd.exe": "C:\\WINDOWS\\system32\\cmd.exe - nano notes.txt",
    "cmd.exe, admin": "Administrator: Command Prompt - nano notes.txt",
    "cmd.exe, sudo": "Command Prompt - sudo nano C:\\x.ini",
    "Terminal.app": "Documents — nano notes.txt — 80×24",
    "Terminal.app, no arguments": "Documents — nano — 80×24",
    "Terminal.app, in a directory named nano": "nano — nano notes.txt — 80×24",
    "iTerm2": "Default (nano)",
    "iTerm2, with arguments": "Default (nano notes.txt)",
    "Konsole": "~/src : nano — Konsole",
    "fish": "nano notes.txt ~/s/docs",
    "fish over SSH": "[myhost] nano notes.txt ~/s/docs",
    "oh-my-zsh": "nano notes.txt",
    "oh-my-zsh, sudo": "sudo nano /etc/hosts",
    "bash snippet": "nano --version",
    "nano alone": "nano",
    "nano with an option": "nano -w notes.txt",
}

# Titles that contain the word nano, or something like it, NOT as the command.
OTHER_TITLES = {
    "bash prompt": "user@host: ~/nano-docs",
    "bash prompt in ~/nano": "user@host: ~/nano",
    "bash prompt, base name only": "user@host: nano",
    "vim, file name": "vim nanotech.txt",
    "vim, file named nano": "vim nano",
    "man page": "man nano",
    "cd": "cd nano",
    "less": "less nano.txt",
    "Terminal.app in ~/nano, running vim": "nano — vim notes.txt — 80×24",
    "Terminal.app in ~/nano, idle": "nano — -zsh — 80×24",
    "Konsole in ~/nano, idle": "nano : bash — Konsole",
    "iTerm2, idle": "Default (-zsh)",
    "nanorc": "vim .nanorc",
    "a plain shell": "bash",
}


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


class NanoMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))

    def test_every_title_route_is_the_same_entry(self):
        routes = self.raw[WT_KEY]["titles-contains"]
        self.assertEqual(set(routes), {"nano", "(nano)", "(nano"})
        for key in routes:
            self.assertIs(routes[key], routes["nano"], key)

    def test_every_named_file_exists(self):
        files = _files(self.raw[WT_KEY]["titles-contains"]["nano"])
        self.assertEqual(files, [NANO, "nano_template.combo.mods.png"])
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


class NanoRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.handler = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.mapping = cls.handler.mapping

    def _route(self, app, title, url=None, os_name="windows"):
        m = find_matching_entry(title, self.mapping[app], url, os_name)
        return None if m is None else _files(m)

    def test_nano_titles_load_the_nano_set_in_windows_terminal(self):
        for app in ("windowsterminal", "wt"):
            for fmt, title in NANO_TITLES.items():
                files = self._route(app, title)
                self.assertEqual(files, [NANO, "nano_template.combo.mods.png"], (app, fmt))

    def test_other_titles_keep_the_terminal_set(self):
        for fmt, title in OTHER_TITLES.items():
            self.assertEqual(self._route("windowsterminal", title)[0], WT, fmt)
        # No title at all, and an empty one.
        self.assertEqual(self._route("windowsterminal", "")[0], WT)
        self.assertEqual(self._route("windowsterminal", None)[0], WT)

    def test_a_mode_report_takes_priority_over_the_title(self):
        for title in NANO_TITLES.values():
            self.assertEqual(self._route("windowsterminal", title, "vim://insert"),
                             [VIM_INSERT], title)
            self.assertEqual(self._route("wt", title, "emacs://text-mode")[0],
                             EMACS, title)

    def test_the_other_terminals_do_not_route_by_title(self):
        # The entry has no overlay of its own, so it routes only through
        # urls-contains; a title alone matches nothing and the generic
        # shortcut harvest runs, as before.
        for app in ("kitty", "konsole", "terminal", "iterm2", "conhost"):
            for title in NANO_TITLES.values():
                self.assertIsNone(self._route(app, title, os_name="linux"), (app, title))


if __name__ == "__main__":
    unittest.main()
