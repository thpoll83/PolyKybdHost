"""The SHIPPED routing of the terminal file managers yazi, ranger and lf.

All three run in a terminal and are seen only in its WINDOW TITLE
(`overlay-mapping.poly.yaml`, the shared `&editor_titles` list, and a
`titles-match` entry for ranger's own title). What it pins:

* every terminal loads each set for every title format that shows the program
  as the running command, and for the title the program writes itself
  (yazi's "Yazi: <dir>", ranger's "ranger:<path>");
* a title that only CONTAINS the word elsewhere (`vim lf`, `man ranger`, a
  prompt in ~/yazi), or a longer word with it inside ("golf", "self-test",
  "lfs"), keeps the terminal's own overlay or matches nothing;
* ranger has a macOS and a Linux set and nothing on Windows; yazi and lf load
  the same set on all three;
* an editor's mode report takes priority over a file manager's title;
* every file named exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
WT_KEY = "windowsterminal,wt"

YAZI = "yazi_template.mods.png"
RANGER = "ranger_template.mods.png"
LF = "lf_template.mods.png"
WT = "windowsterminal_template.mods.png"
VIM_INSERT = "vim_insert_template.mods.png"

# Terminals with no overlay set of their own (kitty and WezTerm have one).
OTHER_TERMINALS = ("alacritty", "konsole", "terminal", "iterm2", "gnome-terminal")


def _titles(cmd):
    """Titles that show `cmd` as the running command, by the program that wrote
    it (the formats of overlay_sources/nano/SOURCES.md)."""
    return {
        "cmd.exe": f"C:\\WINDOWS\\system32\\cmd.exe - {cmd}",
        "Terminal.app": f"Documents — {cmd} — 80×24",
        "Terminal.app, with an argument": f"Documents — {cmd} ~/src — 80×24",
        "iTerm2": f"Default ({cmd})",
        "Konsole": f"~/src : {cmd} — Konsole",
        "fish": f"{cmd} ~/s/docs",
        "fish over SSH": f"[myhost] {cmd} ~/s/docs",
        "oh-my-zsh / bash script": cmd,
        "with an argument": f"{cmd} /tmp",
        "sudo": f"sudo {cmd}",
        "Nushell": f"~/docs> {cmd}",
        "Nushell, explicit external": f"/home/me/docs> ^{cmd}",
        "xonsh": f"{cmd} | me@pc: ~/docs | xonsh",
    }


YAZI_TITLES = dict(_titles("yazi"), **{
    "yazi's own title": "Yazi: Downloads",
    "yazi's own title, a path (older default)": "Yazi: /home/me/Downloads",
    "yazi's own title in Konsole": "~/src : Yazi: Downloads — Konsole",
    "yazi's own title in Terminal.app": "Documents — Yazi: Downloads — 80×24",
})
RANGER_TITLES = dict(_titles("ranger"), **{
    "ranger's own title (update_title)": "ranger:/home/me/src",
    "ranger's own title, shortened": "ranger:me/src/docs",
    "ranger's own title in Terminal.app": "Documents — ranger:~/src — 80×24",
})
LF_TITLES = _titles("lf")


def _others(word):
    """Titles that contain `word`, or something like it, NOT as the command."""
    return {
        "bash prompt": f"user@host: ~/{word}-docs",
        "bash prompt in the directory": f"user@host: ~/{word}",
        "bash prompt, base name only": f"user@host: {word}",
        "vim on a file of that name": f"vim {word}",
        "vim on a file starting with it": f"vim {word}.txt",
        "man page": f"man {word}",
        "Terminal.app in a directory of that name": f"{word} — vim notes.txt — 80×24",
        "Konsole in a directory of that name": f"{word} : bash — Konsole",
        "Nushell in the directory": f"/home/me/{word}",
        "xonsh in the directory": f"me@pc: ~/{word} | xonsh",
        "a plain shell": "bash",
    }


LF_OTHERS = dict(_others("lf"), **{
    "golf": "golf",
    "golf at a prompt": "user@host: ~/golf",
    "self-test": "self-test",
    "self-test with arguments": "self-test --all",
    "make self-test": "make self-test",
    "git lfs": "git lfs pull",
    "lfs": "lfs",
    "lf-like word": "lf-test",
    "upper case": "LF",
    "iTerm2, idle": "Default (-zsh)",
})
YAZI_OTHERS = dict(_others("yazi"), **{
    "a word with yazi inside": "yazidoc",
    "Yazi without the colon": "Yazi Downloads",
})
RANGER_OTHERS = dict(_others("ranger"), **{
    "power ranger": "vim power-ranger.txt",
    "the word in a path": "vim ~/ranger:notes",
    "rangers": "rangers",
})


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


class TuiFileManagerMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        cls.routes = cls.raw[WT_KEY]["titles-contains"]

    def test_each_program_has_one_shared_route(self):
        for first, keys in (("yazi", {"Yazi:", "yazi", "(yazi)", "(yazi", "^yazi"}),
                            ("ranger", {"ranger", "(ranger)", "(ranger", "^ranger"}),
                            ("lf", {"lf", "(lf)", "(lf", "^lf"})):
            for key in keys:
                self.assertIs(self.routes[key], self.routes[first], key)

    def test_every_named_file_exists(self):
        for f in (YAZI, RANGER, LF):
            self.assertTrue((RES / "overlays" / f).is_file(), f)

    def test_ranger_has_no_set_of_its_own_outside_its_os_branches(self):
        self.assertNotIn("overlay", self.routes["ranger"])
        self.assertEqual(set(self.routes["ranger"]["os"]), {"macos", "linux"})


class TuiFileManagerRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, title, os_name, url=None):
        m = find_matching_entry(title, self.mapping[app], url, os_name)
        return None if m is None else _files(m)

    # --- titles that show the program --------------------------------------

    def test_yazi_titles_load_the_yazi_set_everywhere(self):
        for os_name in ("windows", "macos", "linux"):
            for app in ("windowsterminal",) + OTHER_TERMINALS:
                for fmt, title in YAZI_TITLES.items():
                    self.assertEqual(self._route(app, title, os_name), [YAZI],
                                     (os_name, app, fmt))

    def test_lf_titles_load_the_lf_set_everywhere(self):
        for os_name in ("windows", "macos", "linux"):
            for app in ("windowsterminal",) + OTHER_TERMINALS:
                for fmt, title in LF_TITLES.items():
                    self.assertEqual(self._route(app, title, os_name), [LF],
                                     (os_name, app, fmt))

    def test_ranger_titles_load_the_ranger_set_on_macos_and_linux(self):
        for os_name in ("macos", "linux"):
            for app in OTHER_TERMINALS:
                for fmt, title in RANGER_TITLES.items():
                    self.assertEqual(self._route(app, title, os_name), [RANGER],
                                     (os_name, app, fmt))

    def test_ranger_titles_load_nothing_on_windows(self):
        for fmt, title in RANGER_TITLES.items():
            self.assertEqual(self._route("windowsterminal", title, "windows")[0], WT, fmt)
            self.assertIsNone(self._route("conhost", title, "windows"), fmt)

    # --- titles that only contain the word ---------------------------------

    def test_other_titles_keep_the_terminal_set(self):
        for others in (YAZI_OTHERS, RANGER_OTHERS, LF_OTHERS):
            for os_name in ("windows", "macos", "linux"):
                for fmt, title in others.items():
                    files = self._route("windowsterminal", title, os_name)
                    self.assertEqual(files[0], WT, (os_name, fmt))
                    for app in OTHER_TERMINALS:
                        self.assertIsNone(self._route(app, title, os_name),
                                          (os_name, app, fmt))

    def test_lf_does_not_match_inside_another_word(self):
        # The case the short name makes likely: the letters inside a word.
        for title in ("golf", "self-test", "make self-test", "git lfs pull"):
            self.assertIsNone(self._route("alacritty", title, "linux"), title)
            self.assertEqual(self._route("windowsterminal", title, "windows")[0], WT, title)

    # --- priority ------------------------------------------------------------

    def test_a_mode_report_takes_priority_over_the_title(self):
        for title in ("Yazi: Downloads", "ranger:/home/me", "lf", "yazi"):
            self.assertEqual(self._route("kitty", title, "linux", "vim://insert"),
                             [VIM_INSERT], title)

    def test_the_file_manager_set_layers_over_windows_terminal(self):
        m = find_matching_entry("Yazi: Downloads", self.mapping["windowsterminal"],
                                None, "windows")
        under = [str(f) for f in m["overlay"] if getattr(f, "underlay", False)]
        self.assertIn(WT, under)
        self.assertEqual(_files(m), [YAZI])


if __name__ == "__main__":
    unittest.main()
