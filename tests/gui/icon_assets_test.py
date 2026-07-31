"""Icon filenames are passed to get_icon() as plain string literals at ~50 call
sites. A typo there is silent: QIcon() on a missing path yields an empty icon,
so the menu entry just renders without one and nothing raises. These tests turn
that into a build-time failure.

Deliberately Qt-free (no QApplication, no display) so they run in the normal
suite rather than only under xvfb.
"""
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
PKG = REPO / "polyhost"
ICON_DIR = PKG / "res" / "icons"

# res/overlay_sources holds per-app artwork fetch scripts that reference icon
# files of their own; they have nothing to do with the tray menu.
_SKIP = ("res/overlay_sources",)

_GET_ICON = re.compile(r'get_icon\(\s*"([^"]+)"')
_ICON_LITERAL = re.compile(r'"([A-Za-z0-9_]+\.(?:svg|png))"')


def _sources():
    for path in sorted(PKG.rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        if any(s in rel for s in _SKIP):
            continue
        yield rel, path.read_text(encoding="utf-8", errors="ignore")


class IconAssetsTest(unittest.TestCase):
    def test_every_get_icon_name_exists(self):
        """Each get_icon("x.svg") literal names a file that is actually there."""
        missing = [
            (rel, name)
            for rel, text in _sources()
            for name in _GET_ICON.findall(text)
            if not (ICON_DIR / name).is_file()
        ]
        self.assertEqual(missing, [], f"get_icon() names with no file in {ICON_DIR}")

    def test_status_icon_names_exist(self):
        """The reconnect decision tree names status icons as bare strings that
        reach get_icon() later (core/decisions.py, client/remote_core.py), so
        they bypass the check above."""
        missing = []
        for rel, text in _sources():
            for name in _ICON_LITERAL.findall(text):
                if name.startswith("sync") and not (ICON_DIR / name).is_file():
                    missing.append((rel, name))
        self.assertEqual(missing, [], "status icon names with no file")

    def test_no_unreferenced_svg(self):
        """Every shipped .svg is used. Guards against orphans piling up again --
        11 unreferenced icons had accumulated before this was cleaned up.

        Only .svg is checked: the .ico/.icns tray/app variants are consumed by
        packaging, not by name from Python.
        """
        referenced = set()
        for _rel, text in _sources():
            referenced |= set(_GET_ICON.findall(text))
            referenced |= set(_ICON_LITERAL.findall(text))
        orphans = sorted(
            p.name for p in ICON_DIR.glob("*.svg") if p.name not in referenced
        )
        self.assertEqual(orphans, [], "unreferenced icons -- wire them up or delete them")


class IconFormatTest(unittest.TestCase):
    """The set is Material Symbols at optical size 48 on a shared viewBox. The
    geometry differs per optical size, so a 24px-cut file dropped in here would
    render noticeably bolder than its neighbours in the same menu.
    """

    # Pre-existing: source symbol unidentified, so it could not be re-cut at 48.
    _KNOWN_OFF_STANDARD = {"log.svg"}

    def test_uniform_viewbox_and_size(self):
        wrong = []
        for path in sorted(ICON_DIR.glob("*.svg")):
            if path.name in self._KNOWN_OFF_STANDARD:
                continue
            head = path.read_text(encoding="utf-8")[:400]
            if 'viewBox="0 -960 960 960"' not in head:
                wrong.append((path.name, "viewBox"))
            elif 'height="48px"' not in head or 'width="48px"' not in head:
                wrong.append((path.name, "not 48px"))
        self.assertEqual(wrong, [], "icons off the Material Symbols opsz48 standard")

    def test_single_fill_on_the_svg_element(self):
        """Each icon carries exactly one fill, on <svg>, so the tint palette in
        get_icon.py is greppable and a re-tint is a one-token edit."""
        wrong = []
        for path in sorted(ICON_DIR.glob("*.svg")):
            if path.name in self._KNOWN_OFF_STANDARD:
                continue
            text = path.read_text(encoding="utf-8")
            if len(re.findall(r'fill="#[0-9A-Fa-f]{3,6}"', text)) != 1:
                wrong.append(path.name)
        self.assertEqual(wrong, [], "icons without exactly one fill on <svg>")


if __name__ == "__main__":
    unittest.main()
