"""The SHIPPED routing of terminal programs: htop, btop, Midnight Commander,
micro, Helix, less (and man), k9s, GDB, and Vim/Neovim with `set title`.
(lazygit and Yazi: lazygit_routing_test, tui_file_manager_routing_test.)

Only Midnight Commander writes a title of its own; the others are
seen through the shell's title (`polyhost/res/shell/`). Each route in
`&editor_titles` requires the command at the command position, optionally
after `sudo`. Drives `polyhost/res/overlay-mapping.poly.yaml` itself. The title
formats are in `polyhost/res/overlay_sources/tui/SOURCES.md`. What it pins:

* every title of every program loads that program's set, in Windows Terminal
  (with its own set dimmed underneath) and in the terminals without one;
* titles that only mention a program keep the terminal's own overlay;
* the plugin's mode report takes priority over a title;
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

# The first overlay file of each program's set, and the titles that must load it.
TITLES = {
    "htop_template": [
        "htop",
        "sudo htop",
        "htop -u me",
        "Default (htop)",
        "[pi] htop",                          # fish over SSH
    ],
    "btop_template": ["btop", "sudo btop", "Default (btop)"],
    "mc_template": [
        "mc [me@pc]:~/src",                   # mc's own title
        "mc",
        "sudo mc",
        "mc [root@pc]:/etc — Konsole",
    ],
    "micro_template": ["micro", "micro main.go", "sudo micro /etc/hosts"],
    "helix_template": ["hx", "hx src/main.rs", "helix README.md", "sudo hx /etc/fstab",
                       "~/src> hx"],
    "less_template": [
        "less",
        "less aider.log",
        "less nano.txt",
        "man nano",
        "man gemini",
        "man 3 printf",
        "Default (man)",
        "~/src> less",
    ],
    "k9s_template": ["k9s", "k9s -n kube-system", "Default (k9s)"],
    "gdb_template": [
        "gdb",
        "gdb ./a.out",
        "gdb -tui --args prog -v",
        "gdb-multiarch build/fw.elf",
        "arm-none-eabi-gdb .build/polykybd.elf",
        "aarch64-linux-gnu-gdb vmlinux",
        "riscv64-unknown-elf-gdb fw.elf",
        "gdbtui prog",
        "sudo gdb -p 1234",
        "Default (gdb)",
        # The PolyKybd GDB script's title at the prompt.
        "gdb \u23f8 a.out",
        "gdb \u23f8",
        "gdb \u23f8 fw.elf \u2014 Konsole",
    ],
    # ... and while the program runs.
    "gdb_running_template": [
        "gdb \u25b6 a.out",
        "gdb \u25b6",
        "gdb \u25b6 fw.elf \u2014 Konsole",
        "Default (gdb \u25b6 a.out)",
    ],
    "vim_normal_template": [
        "notes.txt (~) - VIM",
        "notes.txt + (~/src) - VIM",
        "main.c (~/src) - VIM — Konsole",
        "notes.txt - NVIM",
        "init.lua (~/.config/nvim) - NVIM",
    ],
}

# The program's complete set (underlays left out), keyed like TITLES.
SETS = {
    stem: [f"{stem}.mods.png"] + ([f"{stem}.combo.mods.png"] if stem in (
        "mc_template", "micro_template", "helix_template", "less_template") else [])
    for stem in TITLES
}

# Titles that mention a program, or look like one, but are not it running.
OTHER_TITLES = [
    "user@host: ~/lazygit",
    "vim htop.c",
    "cd yazi",
    "git log --grep gdb",
    "cat less.txt",
    "info man",
    "me@pc: ~/helix | xonsh",
    "/home/me/k9s",                           # Nushell, idle in ~/k9s
    "mc : bash — Konsole",                    # Konsole idle in ~/mc
    "micro — -zsh — 80×24",                   # Terminal.app idle in ~/micro
    "Yazi",
    "VIM",
    "vim notes.txt",
    "gdb.txt",
    "\u25b6 Now playing",
    "echo \u25b6",
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
    """The program's own files; a terminal's set layered underneath is left out."""
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])
            if not getattr(f, "underlay", False)]


def _underlays(entry):
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])
            if getattr(f, "underlay", False)]


class TuiMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        cls.routes = cls.raw[WT_KEY]["titles-contains"]

    def test_every_named_file_exists(self):
        for stem in TITLES:
            entries = [e for e in self.routes.values()
                       if "overlay" in e and _files(e)[0].startswith(stem)]
            self.assertTrue(entries, stem)
            for entry in entries:
                missing = [f for f in _files(entry)
                           if not (RES / "overlays" / f).is_file()]
                self.assertEqual(missing, [], stem)

    def test_each_program_has_its_parenthesised_and_caret_keys(self):
        for cmd in ("htop", "btop", "mc", "micro", "hx", "helix",
                    "less", "man", "k9s", "gdb", "gdb-multiarch", "arm-none-eabi-gdb"):
            for key in (cmd, f"({cmd})", f"({cmd}", f"^{cmd}"):
                self.assertIs(self.routes[key], self.routes[cmd], key)


class TuiRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.handler = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        cls.mapping = cls.handler.mapping

    def _route(self, app, title, url=None, os_name="windows"):
        m = find_matching_entry(title, self.mapping[app], url, os_name)
        return None if m is None else _files(m)

    def test_each_title_loads_its_set_in_windows_terminal(self):
        for stem, titles in TITLES.items():
            for title in titles:
                self.assertEqual(self._route("windowsterminal", title), SETS[stem],
                                 (stem, title))

    def test_each_title_loads_its_set_in_the_other_terminals(self):
        for os_name in ("linux", "macos"):
            for app in ("kitty", "konsole", "iterm2", "ghostty", "gnome-terminal-server",
                        "terminal", "conhost"):
                for stem, titles in TITLES.items():
                    for title in titles:
                        self.assertEqual(self._route(app, title, os_name=os_name),
                                         SETS[stem], (os_name, app, stem, title))

    def test_other_titles_keep_the_terminal_set(self):
        for title in OTHER_TITLES:
            for os_name in ("windows", "linux", "macos"):
                self.assertEqual(self._route("windowsterminal", title, os_name=os_name)[0],
                                 WT, (os_name, title))
                # konsole has no set of its own (kitty and WezTerm do).
                self.assertIsNone(self._route("konsole", title, os_name=os_name),
                                  (os_name, title))

    def test_windows_terminal_dims_its_own_set_under_a_program(self):
        for stem, titles in TITLES.items():
            m = find_matching_entry(titles[0], self.mapping["windowsterminal"], None, "windows")
            self.assertEqual(_underlays(m), [WT, "windowsterminal_template.combo.mods.png"], stem)

    def test_a_mode_report_takes_priority_over_a_title(self):
        for titles in TITLES.values():
            for title in titles:
                self.assertEqual(self._route("windowsterminal", title, "vim://insert"),
                                 [VIM_INSERT], title)


if __name__ == "__main__":
    unittest.main()
