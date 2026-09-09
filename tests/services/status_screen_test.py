"""The status-OLED panel the editor draws, pinned to the FIRMWARE's own renderer.

`polyhost/services/status_screen.py` is a port of
`qmk_firmware/keyboards/polykybd/tools/status_oled_preview.py`, and the only claim
worth making about a port is that it draws the same pixels. So the core of this file
is a comparison against `status_panel_golden.json` -- generated from the firmware tool
by `scripts/gen_status_panel_golden.py` and shipped, so the pin holds on a machine with
no firmware checkout. The last test re-derives the fixture live when a checkout IS
present, which is what catches the firmware moving a row.

⚠️ A structural comparison would be worthless here: both sides are Python and both
would be re-read from the same coordinates. The pixels are the contract.
"""
import json
import pathlib
import sys
import unittest
import warnings

from polyhost.services import preview_data as pd
from polyhost.services import status_screen as ss

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
GOLDEN = HERE / "status_panel_golden.json"

sys.path.insert(0, str(REPO / "scripts"))
import gen_status_panel_golden as gen           # noqa: E402


def faces():
    """The faces the panel draws with, out of the shipped export.

    The icon and globe faces are found by COVERAGE, mirroring
    `StatusScreenRenderer.from_preview_data` -- the firmware tool names them, the host
    has no names for pack fonts.
    """
    d = pd.PreviewData()
    if not d.load():
        return None
    ui = d.ui_fonts or {}

    def covering(cp):
        return next((f for f in d.fonts if f.first <= cp <= f.last), None)

    return {"icons": covering(0x80), "globe": covering(0x1F310),
            "mid": ui.get("NotoSans_Regular_Mid_19px7b"),
            "small": ui.get("NotoSans_Regular_Small_15px7b"),
            "tiny": ui.get("NotoSans_Regular_Nano_10px7b")}


class GoldenTest(unittest.TestCase):
    """Every case the fixture covers, pixel for pixel."""

    @classmethod
    def setUpClass(cls):
        cls.faces = faces()
        if cls.faces is None:
            raise unittest.SkipTest("no shipped preview data")
        missing = [k for k, v in cls.faces.items() if v is None]
        if missing:
            raise unittest.SkipTest("the export lacks %s" % ", ".join(missing))
        cls.golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    def test_the_port_draws_WHAT_THE_FIRMWARE_TOOL_DREW(self):
        """The whole reason this module exists rather than a hand-written subset.

        ⚠️ The fixture's layer is always 0 -- `build_panel` takes no layer -- so the
        digit is pinned separately below. Everything else on both panels, in both RGB
        states and at both a saturating and a NON-saturating brightness/HSV, is here;
        the generator's own comment says why the second pair had to exist.
        """
        self.assertEqual(len(self.golden["cases"]), len(gen.CASES))
        for case in self.golden["cases"]:
            with self.subTest(side=case["side"], rgb=case["rgb"],
                              b=case.get("brightness", 50)):
                want = gen.unpack(case["bitmap"])
                rgb = None
                if case["rgb"]:
                    rgb = gen.RGB_MID if case.get("hsv") == "mid" else gen.RGB_DEFAULT
                got = ss.render("left" if case["side"] == "L" else "right",
                                self.faces, layer=0, layout=case["layout"],
                                brightness=case.get("brightness", 50), rgb=rgb,
                                lang=case.get("lang", "en-US"),
                                wpm=case.get("wpm", 0))
                self.assertTrue(want, "the fixture case is empty")
                self.assertEqual(got, want,
                                 "%d missing / %d extra pixels"
                                 % (len(want - got), len(got - want)))

    def test_the_fixture_records_the_firmware_it_was_taken_FROM(self):
        """A frozen artifact with no provenance cannot be re-derived or aged."""
        self.assertRegex(self.golden["firmware"], r"^\d+\.\d+\.\d+$")
        self.assertIn("status_oled_preview.py", self.golden["source"])


class RenderTest(unittest.TestCase):
    """The parts the fixture cannot reach: the layer digit, and degradation."""

    @classmethod
    def setUpClass(cls):
        cls.faces = faces()
        if cls.faces is None:
            raise unittest.SkipTest("no shipped preview data")
        missing = [k for k, v in cls.faces.items() if v is None]
        if missing:
            raise unittest.SkipTest("the export lacks %s" % ", ".join(missing))

    def test_the_coordinates_are_the_FIRMWARES_OWN_NUMBERS(self):
        """Pinned as LITERALS, against `split72/status_oled.c`.

        ⚠️ Asserting the ink against `ss.TOP_BASE` instead reads as a placement check
        and is not one: move the constant and the expectation moves with it, so the
        row can slide anywhere and the suite stays green (measured -- that mutation
        escaped until this test was written this way).
        """
        self.assertEqual((ss.TOP_BASE, ss.LOCK_ROW_B, ss.LOCK_ROW_C, ss.LOCK_ROW_D),
                         (15, 29, 48, 63))
        self.assertEqual((ss.RGB_ROW_B, ss.RGB_ROW_C, ss.RGB_ROW_D), (30, 45, 63))
        self.assertEqual(ss.SIDE_MARKER_BASE, 63)
        self.assertEqual((ss.PANEL_W, ss.PANEL_H), (128, 64))

    def test_a_two_digit_layer_is_drawn_in_HEX(self):
        """Twelve layers and one character of room, which is why the firmware prints
        hex -- a decimal '11' would be two glyphs and run into the role word.

        ⚠️ Checked against what each scheme WOULD draw, not by comparing `render(10)`
        with `render(0xA)`: those are the same integer, so both sides move together
        under a decimal mutation and the comparison is vacuous (measured -- it escaped
        exactly that way). A width heuristic is no good either: 'B' is a wide glyph
        and '1' a narrow one, so both measure 10 px.
        """
        base = ss.render("left", self.faces, layer=0, layout="")
        got = ss.render("left", self.faces, layer=11, layout="")

        def digits(text):
            pts = set()
            ss.draw(lambda x, y: pts.add((x, y)), self.faces["mid"], 20, ss.TOP_BASE,
                    [ord(c) for c in text])
            return pts

        # `base` is the whole panel at layer 0, so removing the '0' ink leaves
        # everything the digit is NOT, and each candidate can be put back in its place.
        rest = base - digits("0")
        self.assertEqual(got, rest | digits("B"))
        self.assertNotEqual(got, rest | digits("11"))

    def test_nothing_is_drawn_outside_the_panel(self):
        """The hardware's SET_PIXEL_CLIPPED drops such pixels, so a long name has to
        go missing here the same way rather than wrapping or widening the image."""
        pts = ss.render("left", self.faces, layer=11,
                        layout="WWWWWWWWWWWWWWWWWWWW")
        for x, y in pts:
            self.assertTrue(0 <= x < ss.PANEL_W and 0 <= y < ss.PANEL_H)

    def test_a_MISSING_face_drops_only_what_it_draws(self):
        """The faces come from the preview export, and an older one has fewer. Losing
        the small-face rows is worth having the layer digit; failing outright is not.

        ⚠️ With NO faces at all the panel is not empty, and expecting that was wrong:
        the role icons, the brightness gauge and the speed box are BITMAPS and drawn
        rectangles, so they survive every missing font. That is the property worth
        pinning -- a face is a strict subtraction, never a precondition.
        """
        whole = ss.render("left", self.faces, layer=2, layout="Qwerty")
        for drop in ("small", "mid", "icons", "tiny"):
            with self.subTest(missing=drop):
                less = ss.render("left", dict(self.faces, **{drop: None}), layer=2,
                                 layout="Qwerty")
                self.assertLess(len(less), len(whole),
                                "dropping %s drew nothing away" % drop)
                self.assertTrue(less.issubset(whole),
                                "dropping %s changed other rows" % drop)
        bare = ss.render("left", {}, layer=2, layout="Qwerty")
        self.assertTrue(bare.issubset(whole) and bare != whole,
                        "no faces at all is not a strict subtraction")
        self.assertTrue(bare, "the drawn chrome does not depend on a font")

    def test_an_unknown_side_draws_the_LAYOUT_panel_rather_than_raising(self):
        """`lock_panel = side != "right"`, so anything unexpected falls to the half
        that carries the layer name -- a blank board would read as a broken editor."""
        self.assertEqual(ss.render("middle", self.faces, layer=0, layout="Qwerty"),
                         ss.render("left", self.faces, layer=0, layout="Qwerty"))


class FixtureIsCurrentTest(unittest.TestCase):
    """Re-derive the fixture from a firmware checkout, when there is one.

    This is the half that catches the FIRMWARE moving: the golden comparison above
    only proves the port still matches what was frozen, which stays true forever if
    `status_oled.c` changes and nobody regenerates.
    """

    def test_the_golden_matches_a_LIVE_firmware_tool(self):
        pk = gen.firmware_dir()
        if not (pk / "tools" / "status_oled_preview.py").exists():
            raise unittest.SkipTest("no firmware checkout beside this repo")
        try:
            from PIL import Image  # noqa: F401  (the tool imports Pillow at module load)
        except ImportError:
            raise unittest.SkipTest("Pillow unavailable")
        # The firmware tool leaves its font headers open; that is its file handling,
        # not something this repo can fix, and the warnings would otherwise land in
        # every full-suite run on a machine that has a checkout.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            fresh = {(c["side"], c["rgb"]): c["bitmap"] for c in gen.build(pk)}
        old = json.loads(GOLDEN.read_text(encoding="utf-8"))
        have = {(c["side"], c["rgb"]): c["bitmap"] for c in old["cases"]}
        self.assertEqual(fresh, have,
                         "the firmware panel moved -- re-run "
                         "scripts/gen_status_panel_golden.py")


if __name__ == "__main__":
    unittest.main()
