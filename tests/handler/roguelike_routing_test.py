"""The SHIPPED routing of the roguelike games in `overlay-mapping.poly.yaml`.

A graphical build has a process name of its own. A console build runs in a
terminal and writes no window title, so it is seen through the shell's title:
its route in `&editor_titles` requires the command at the command position,
as the htop route does (tui_routing_test). What it pins:

* every process name of a graphical build loads the game's set on all three
  platforms;
* every terminal title of a console build loads the game's set, in Windows
  Terminal and in the terminals without a set of their own;
* a title that only mentions a game keeps the terminal's own overlay;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
WT_KEY = "windowsterminal,wt"
WT = "windowsterminal_template.mods.png"

DCSS = ["dcss_template.mods.png"]
CDDA = ["cdda_template.mods.png"]

# Process name (as the host reports it, lower case) -> (window title, set).
PROCESSES = {
    "crawl": ("Dungeon Crawl Stone Soup 0.34.1", DCSS),
    "crawl.exe": ("Dungeon Crawl Stone Soup 0.34.1", DCSS),
    "crawl-tiles": ("Dungeon Crawl Stone Soup 0.34.1", DCSS),
    "crawl-tiles.exe": ("Dungeon Crawl Stone Soup 0.34.1", DCSS),
    "dungeon crawl stone soup - tiles": ("Dungeon Crawl Stone Soup 0.34.1", DCSS),
    "cataclysm-tiles": ("Cataclysm: Dark Days Ahead - 0.I", CDDA),
    "cataclysm-tiles.exe": ("Cataclysm: Dark Days Ahead - 0.I", CDDA),
    "org.cataclysmdda.cataclysmdda": ("Cataclysm: Dark Days Ahead - 0.I", CDDA),
    "cataclysm": ("Cataclysm: Dark Days Ahead - 0.I", CDDA),
}

# Process names that serve another program too; their set needs the title.
SHARED_PROCESSES = set()

# The first key of each console route -> (its set, the titles that must load it).
TITLES = {
    "crawl": (DCSS, [
        "crawl",
        "crawl -name Mu",
        "sudo crawl",
        "Default (crawl)",
        "[pi] crawl",                         # fish over SSH
        "~/games> crawl",                     # Nushell
        "crawl-console",
        "C:\\WINDOWS\\system32\\cmd.exe - crawl-console",
    ]),
    "cataclysm": (CDDA, [
        "cataclysm",
        "cataclysm --world Test",
        "Default (cataclysm)",
        "~/cdda> cataclysm",
    ]),
}

# The other keys that must be the same route as the first key.
ALIASES = {
    "crawl": ["crawl-console"],
    "cataclysm": [],
}

# Titles that mention a game, or look like one, but are not it running.
OTHER_TITLES = [
    "vim crawl.txt",
    "git log --grep crawl",
    "user@host: ~/crawl",
    "cd crawl",
    "/home/me/crawl",                         # Nushell, idle in ~/crawl
    "crawl : bash — Konsole",                 # Konsole idle in ~/crawl
    "crawl.log",
    "cataclysm-launcher",
    "vim cataclysm.txt",
    "user@host: ~/cataclysm",
    "bash",
]


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as emulator_routing_test)."""
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}") from e
    except Exception as e:
        if not ((isinstance(e, ModuleNotFoundError)
                 and not (e.name or "").startswith("polyhost"))
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}") from e
    return OverlayHandler


def _files(entry):
    """The matched entry's own files; a terminal's set layered underneath is
    left out."""
    ov = entry["overlay"]
    return [str(f) for f in (ov if isinstance(ov, list) else [ov])
            if not getattr(f, "underlay", False)]


class RoguelikeMappingFileTest(unittest.TestCase):
    """Properties of the raw YAML; no window backend needed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        cls.routes = cls.raw[WT_KEY]["titles-contains"]

    def test_every_named_file_exists(self):
        named = {f for _, files in PROCESSES.values() for f in files}
        named |= {f for files, _ in TITLES.values() for f in files}
        missing = sorted(f for f in named if not (RES / "overlays" / f).is_file())
        self.assertEqual(missing, [])

    def test_each_command_has_its_parenthesised_and_caret_keys(self):
        for first, others in ALIASES.items():
            for cmd in [first, *others]:
                for key in (cmd, f"({cmd})", f"({cmd}", f"^{cmd}"):
                    self.assertIs(self.routes[key], self.routes[first], key)


class RoguelikeRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, title, os_name):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else _files(m)

    def test_each_process_name_loads_its_set(self):
        for app, (title, files) in PROCESSES.items():
            for os_name in ("windows", "macos", "linux"):
                with self.subTest(app=app, os=os_name):
                    self.assertEqual(self._route(app, title, os_name), files)

    def test_a_process_name_needs_no_title(self):
        """An empty title, and no title, still load the set of a process that
        is not shared with another program."""
        for app, (_, files) in PROCESSES.items():
            if app in SHARED_PROCESSES:
                continue
            for title in ("", None):
                with self.subTest(app=app, title=title):
                    self.assertEqual(self._route(app, title, "linux"), files)

    def test_each_title_loads_its_set_in_windows_terminal(self):
        for first, (files, titles) in TITLES.items():
            for title in titles:
                with self.subTest(route=first, title=title):
                    self.assertEqual(self._route("windowsterminal", title, "windows"), files)

    def test_each_title_loads_its_set_in_the_other_terminals(self):
        for os_name in ("linux", "macos"):
            for app in ("kitty", "konsole", "iterm2", "ghostty", "gnome-terminal-server",
                        "terminal", "conhost"):
                for first, (files, titles) in TITLES.items():
                    for title in titles:
                        with self.subTest(os=os_name, app=app, title=title):
                            self.assertEqual(self._route(app, title, os_name), files)

    def test_a_title_that_only_mentions_a_game_keeps_the_terminal(self):
        for title in OTHER_TITLES:
            with self.subTest(title=title):
                self.assertEqual(self._route("windowsterminal", title, "windows")[0], WT)
                self.assertIsNone(self._route("konsole", title, "linux"))


if __name__ == "__main__":
    unittest.main()
