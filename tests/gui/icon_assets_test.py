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

# The brand mark is a different kind of artwork from the menu glyphs: a
# generated multi-layer mark (tools/gen_brand_icons.py), not a single-fill
# Material Symbol, and its .svg is a master for docs/store use rather than
# something get_icon() ever names. BrandMarkTest covers it instead.
BRAND_VARIANTS = ("pcolor", "pgray", "pthink", "pwarn")
BRAND_SVG = {f"{v}.svg" for v in BRAND_VARIANTS}
BRAND_LADDER = (16, 24, 32, 48, 64, 128, 256)
BRAND_ICO_SIZES = (16, 20, 24, 32, 48, 64, 128, 256)
# "HOST" is stamped into the bottom-right keys only where it can be read.
BRAND_STAMP_MIN = 128

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
            p.name
            for p in ICON_DIR.glob("*.svg")
            if p.name not in referenced and p.name not in BRAND_SVG
        )
        self.assertEqual(orphans, [], "unreferenced icons -- wire them up or delete them")


class IconFormatTest(unittest.TestCase):
    """The set is Material Symbols at optical size 48 on a shared viewBox. The
    geometry differs per optical size, so a 24px-cut file dropped in here would
    render noticeably bolder than its neighbours in the same menu.
    """

    # Pre-existing: source symbol unidentified, so it could not be re-cut at 48.
    _KNOWN_OFF_STANDARD = {"log.svg"} | BRAND_SVG

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


class BrandMarkTest(unittest.TestCase):
    """The tray/app mark is generated as a set -- an SVG master, a canonical
    PNG, the size ladder get_icon() feeds to QIcon, and the packaging formats.
    A half-finished generator run leaves some of those stale, which shows up
    only as a blurry tray icon on somebody else's machine.
    """

    def test_every_variant_ships_the_whole_set(self):
        missing = [
            f"{v}{suffix}"
            for v in BRAND_VARIANTS
            for suffix in (".svg", ".png", "@1024.png", ".ico", ".icns")
            if not (ICON_DIR / f"{v}{suffix}").is_file()
        ]
        missing += [
            f"{v}_{size}.png"
            for v in BRAND_VARIANTS
            for size in BRAND_LADDER
            if not (ICON_DIR / f"{v}_{size}.png").is_file()
        ]
        self.assertEqual(missing, [], "run tools/gen_brand_icons.py")

    def test_the_ladder_files_are_the_size_they_claim(self):
        """A PNG's dimensions live in the IHDR at a fixed offset, so this needs
        no image library -- and it is the check that catches a ladder built by
        copying one file, which is exactly as blurry as having no ladder."""
        import struct

        wrong = []
        for v in BRAND_VARIANTS:
            for size in BRAND_LADDER:
                data = (ICON_DIR / f"{v}_{size}.png").read_bytes()[:24]
                w, h = struct.unpack(">II", data[16:24])
                if (w, h) != (size, size):
                    wrong.append((f"{v}_{size}.png", w, h))
        self.assertEqual(wrong, [], "ladder PNGs whose pixels do not match their name")


    def test_every_ico_carries_the_whole_size_set(self):
        """Pillow's ICO writer SKIPS any requested size larger than the base
        image and reports nothing, so a generator that hands it the 16 px render
        first writes a single-entry 16x16 .ico that Windows then upscales into a
        blur. Read the ICONDIR count directly -- no image library needed."""
        import struct

        wrong = []
        for v in BRAND_VARIANTS:
            data = (ICON_DIR / f"{v}.ico").read_bytes()
            count = struct.unpack("<H", data[4:6])[0]
            sizes = sorted(
                data[6 + i * 16] or 256 for i in range(count)
            )
            if sizes != sorted(BRAND_ICO_SIZES):
                wrong.append((f"{v}.ico", sizes))
        self.assertEqual(wrong, [], "ICOs missing sizes -- see the Pillow base-image trap")

    def test_the_stamp_appears_only_where_it_can_be_read(self):
        """Below 128 px the stamped letters are mush, so those renders come from
        the unstamped master. Measured as dark pixels inside a LIT bottom-row
        key, which nothing but the punched-out lettering can produce -- and only
        on the two variants with no dimming overlay over that key."""
        from PIL import Image

        wrong = []
        for v in ("pcolor", "pgray"):
            for size in BRAND_LADDER:
                im = Image.open(ICON_DIR / f"{v}_{size}.png").convert("RGBA")
                box = tuple(round(c * size / 1024) for c in (787, 787, 904, 904))
                px = list(im.crop(box).getdata())
                ink = sum(1 for r, g, b, a in px if a > 128 and r + g + b < 200)
                stamped = ink > 0
                if stamped != (size >= BRAND_STAMP_MIN):
                    wrong.append((f"{v}_{size}.png", "stamped" if stamped else "plain"))
        self.assertEqual(wrong, [], "stamp present at the wrong sizes")


if __name__ == "__main__":
    unittest.main()
