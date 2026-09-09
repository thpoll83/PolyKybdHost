"""board_plate — the board the layout editor draws its keys on.

The plate is decoration, so what matters is that it cannot get in the way: it
must sit BEHIND every key, take no input, and disappear rather than raise when
the shipped description is missing.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QRectF
    from PyQt5.QtGui import QColor, QImage
    from PyQt5.QtWidgets import QApplication, QGraphicsScene
except ImportError as e:  # pragma: no cover - PyQt5 not installed
    _IMPORT_ERR = e
else:
    _IMPORT_ERR = None
    from polyhost.gui.layout_dialog import board_plate as bp
    from polyhost.gui.layout_dialog.renderable_key import RenderableKey
    from polyhost.services import board_outline as bo

_APP = None


def setUpModule():
    global _APP
    if _IMPORT_ERR is None:
        _APP = QApplication.instance() or QApplication([])


@unittest.skipIf(_IMPORT_ERR is not None, "PyQt5 not installed")
class AddBoardTest(unittest.TestCase):
    def setUp(self):
        self.scene = QGraphicsScene()

    def test_it_draws_a_plate_per_half_and_a_screen_per_display(self):
        board = bo.load()
        if board is None:
            self.skipTest("no board outline shipped")
        items = bp.add_board(self.scene, 80.0, dark=True)
        panels = sum(len(h.displays) for h in board.halves)
        # plate per half + (glass, lit area, screen) per panel -- no caption
        self.assertEqual(len(board.halves) + panels * 3, len(items))
        self.assertEqual(len(items), len(self.scene.items()))

    def test_a_screen_item_is_TAGGED_with_its_half(self):
        """`add_board` hands back one flat list, so the tag is the only thing that
        can route a repaint to the right panel -- and an untagged item is skipped
        entirely by `set_screen_images`, which fails as a picture that never
        appears rather than as an error."""
        board = bo.load()
        if board is None:
            self.skipTest("no board outline shipped")
        items = bp.add_board(self.scene, 80.0, dark=True)
        tagged = [i.data(bp.SCREEN_SIDE) for i in items
                  if i.data(bp.SCREEN_SIDE) is not None]
        self.assertEqual(sorted(tagged),
                         sorted(h.side for h in board.halves for _ in h.displays))

    def test_a_screen_image_FILLS_the_lit_rectangle_but_for_the_stroke(self):
        """The pixmap stays at its native 128x64 and the ITEM scales, so zooming in
        resolves more panel; the check is that what lands on screen is the lit
        rectangle, less the frame's stroke, and centred in it.

        ⚠️ This used to assert the picture filled the rectangle EXACTLY, which is the
        defect it now guards: the frame's pen is centred on the edge, so half of it
        lies inside, and a picture that reaches the edge covers that half and reads as
        bleeding over the bezel. The near-miss is what makes it worth pinning both
        ways -- an inset that grew to swallow the picture would be just as wrong, so
        the width is bounded above AND below.
        """
        board = bo.load()
        if board is None:
            self.skipTest("no board outline shipped")
        items = bp.add_board(self.scene, 80.0, dark=True)
        img = QImage(128, 64, QImage.Format_RGB32)
        img.fill(0)
        bp.set_screen_images(items, {h.side: img for h in board.halves})
        lit = {h.side: h.displays[0].active_rect for h in board.halves
               if h.displays}
        for item in items:
            side = item.data(bp.SCREEN_SIDE)
            if side is None:
                continue
            self.assertFalse(item.pixmap().isNull(), "%s screen is blank" % side)
            x, _y, w, _h = lit[side]
            lit_x, lit_w = x * 80.0, w * 80.0
            got = item.sceneBoundingRect()
            with self.subTest(side=side):
                self.assertLessEqual(got.width(), lit_w - bp.ACTIVE_PEN + 0.01,
                                     "the picture reaches the frame")
                # 2 px of slack, not 0: the lit rectangle's aspect (2.002) is a
                # hair wider than the panel's (2.000), so HEIGHT binds and the
                # width comes out a fraction under the inset one. Tight enough to
                # catch an inset that ran away, loose enough not to encode which
                # axis happens to bind for today's geometry.
                self.assertGreater(got.width(), lit_w - bp.ACTIVE_PEN - 2.0,
                                   "the picture no longer fills the screen")
                self.assertAlmostEqual(got.left() - lit_x,
                                       (lit_x + lit_w) - got.right(), places=3,
                                       msg="the picture is not centred")

    def test_a_side_with_NO_image_is_cleared_rather_than_left_stale(self):
        """A mode switch back to Symbol has to take the picture away; leaving the
        last one is the same defect the keycap caches have to drop on a mode
        change."""
        items = bp.add_board(self.scene, 80.0, dark=True)
        if not items:
            self.skipTest("no board outline shipped")
        img = QImage(128, 64, QImage.Format_RGB32)
        img.fill(0)
        bp.set_screen_images(items, {"left": img, "right": img})
        bp.set_screen_images(items, {})
        for item in items:
            if item.data(bp.SCREEN_SIDE) is not None:
                self.assertTrue(item.pixmap().isNull())

    def test_every_item_sits_behind_the_keys(self):
        items = bp.add_board(self.scene, 80.0, dark=True)
        if not items:
            self.skipTest("no board outline shipped")
        key = RenderableKey("A", {"w": 1.0, "h": 1.0}, 80.0, matrix_index=0)
        for item in items:
            self.assertLess(item.zValue(), key.zValue(),
                            "%r would draw over a key" % item)

    def test_no_item_can_take_a_click_or_the_selection(self):
        items = bp.add_board(self.scene, 80.0, dark=True)
        if not items:
            self.skipTest("no board outline shipped")
        for item in items:
            self.assertFalse(item.flags() & item.ItemIsSelectable, repr(item))
            self.assertFalse(item.flags() & item.ItemIsFocusable, repr(item))
            self.assertFalse(item.acceptHoverEvents(), repr(item))

    def test_a_missing_description_costs_the_picture_and_nothing_else(self):
        self.assertEqual([], bp.add_board(self.scene, 80.0, dark=True, board=_Absent()))
        self.assertEqual([], self.scene.items())

    def test_the_two_themes_differ_and_both_are_complete(self):
        self.assertEqual(set(bp.DARK), set(bp.LIGHT))
        self.assertNotEqual(bp.DARK, bp.LIGHT)

    def test_only_the_LIGHT_theme_repaints_the_scene_ground(self):
        """Dark leaves the view's own background alone; light moves the blue there
        and takes the plate to grey, so a `scene` of None must stay a no-op."""
        before = QGraphicsScene().backgroundBrush()
        for dark, expect_default in ((True, True), (False, False)):
            scene = QGraphicsScene()
            if not bp.add_board(scene, 80.0, dark=dark):
                self.skipTest("no board outline shipped")
            self.assertEqual(scene.backgroundBrush() == before, expect_default,
                             "dark=%s repainted the ground the wrong way" % dark)

    def test_the_light_plate_is_GREY_and_its_ground_is_the_blue(self):
        """The swap, pinned as a relation rather than as two literals: a plate whose
        channels differ is not grey, and a ground that is not bluer than the plate
        has not taken the colour over."""
        plate = QColor(bp.LIGHT["plate_top"])
        ground = QColor(bp.LIGHT["scene"])
        self.assertEqual((plate.red(), plate.green()), (plate.green(), plate.blue()),
                         "the light plate is not grey: %s" % bp.LIGHT["plate_top"])
        self.assertGreater(ground.blue() - ground.red(), 8,
                           "the light ground is not blue: %s" % bp.LIGHT["scene"])
        # And the plate is the DARKER of the two, by enough to read as an object
        # sitting on the ground rather than as a slightly different white.
        self.assertGreater(ground.lightness() - plate.lightness(), 15,
                           "the light plate (%s) is not darker than its ground (%s)"
                           % (bp.LIGHT["plate_top"], bp.LIGHT["scene"]))

    def test_the_board_and_its_outlines_are_NEUTRAL(self):
        """Every colour but the light theme's GROUND is grey.

        The board wore the brand's blue -> cyan sweep -- plate, screen bezel and all
        three strokes -- which on a picture of a keyboard reads as a lit edge rather
        than as a case. Pinned as a channel-spread bound rather than as literals, so a
        re-tint is caught while a lightness tweak is not; `scene` is exempt because
        the blue deliberately lives there and one test above requires it.
        """
        for name, ink in (("DARK", bp.DARK), ("LIGHT", bp.LIGHT)):
            for key, value in ink.items():
                if key == "scene" or value is None:
                    continue
                c = QColor(value)
                with self.subTest(theme=name, key=key):
                    self.assertLessEqual(
                        max(c.red(), c.green(), c.blue())
                        - min(c.red(), c.green(), c.blue()), 4,
                        "%s[%r] = %s is not neutral" % (name, key, value))

    def test_every_OUTLINE_is_DARK(self):
        """"Dark grey or black", which is what was asked for and what the cyan
        strokes were not.

        ⚠️ Bounded, NOT stated as "darker than its fill" -- that rule was written
        first and is wrong for the screen: the bezel is the darkest thing on the
        board, so a stroke darker than it would be invisible and `glass_edge` is
        deliberately the lighter of the two, separating the bezel from the plate. The
        property that holds for all three is simply that none of them is bright.
        """
        for name, ink in (("DARK", bp.DARK), ("LIGHT", bp.LIGHT)):
            for stroke in ("edge", "glass_edge", "active_edge"):
                with self.subTest(theme=name, stroke=stroke):
                    self.assertLessEqual(QColor(ink[stroke]).lightness(), 90,
                                         "%s[%r] = %s is not a dark outline"
                                         % (name, stroke, ink[stroke]))
        # The plate's own edge additionally has to READ as an edge against it.
        for name, ink in (("DARK", bp.DARK), ("LIGHT", bp.LIGHT)):
            with self.subTest(theme=name):
                self.assertLess(QColor(ink["edge"]).lightness(),
                                QColor(ink["plate_bottom"]).lightness() - 10,
                                "%s: the plate edge does not separate it" % name)

    def test_the_screen_picture_stays_INSIDE_the_lit_rectangle(self):
        """The reported defect: the panel drew over its own bezel.

        Two independent causes, so this asserts CONTAINMENT rather than either fix --
        the picture is 2:1 while the lit rectangle need not be (dropping the side
        bezel already reshaped it), and the frame's pen is centred on the edge, so a
        picture that exactly fills the rectangle covers the half of the stroke that
        lies inside it.

        ⚠️ A tall image is fed deliberately. With the shipped geometry the aspects
        very nearly agree, so a width-only scale overflows by a fraction of a pixel
        and a test using only the real panel passes against the bug.
        """
        board = bo.load()
        if board is None:
            self.skipTest("no board outline shipped")
        items = bp.add_board(self.scene, 80.0, dark=True)
        screens = [i for i in items if i.data(bp.SCREEN_SIDE) is not None]
        self.assertTrue(screens)
        # ⚠️ The rectangle is derived from the DESCRIPTION, never read back off the
        # item. Taking it from `SCREEN_BOX` makes the check self-consistent with
        # whatever the item cached, so a wrong box passes: measured, substituting
        # `width/2` for the real height escaped exactly that way, because the lit
        # rectangle's aspect (2.002) is a hair off the panel's 2.000 and the error is
        # a fraction of a pixel. So the cache is asserted against the description too.
        want = {h.side: h.displays[0].active_rect for h in board.halves if h.displays}
        for item in screens:
            x, y, w, h = [v * 80.0 for v in want[item.data(bp.SCREEN_SIDE)]]
            self.assertEqual([round(v, 6) for v in item.data(bp.SCREEN_BOX)],
                             [round(v, 6) for v in (x, y, w, h)],
                             "the cached box is not the lit rectangle")
        for shape in ((128, 64), (128, 128), (256, 64)):
            imgs = {i.data(bp.SCREEN_SIDE): QImage(shape[0], shape[1],
                                                   QImage.Format_RGB32)
                    for i in screens}
            for im in imgs.values():
                im.fill(0xFFFFFFFF)
            bp.set_screen_images(items, imgs)
            for item in screens:
                x, y, w, h = [v * 80.0 for v in want[item.data(bp.SCREEN_SIDE)]]
                lit = QRectF(x, y, w, h)
                got = item.sceneBoundingRect()
                with self.subTest(side=item.data(bp.SCREEN_SIDE), image=shape):
                    self.assertTrue(lit.contains(got),
                                    "%s escapes the lit rect %s" % (got, lit))
                    # …and clear of the stroke, which is centred on the edge.
                    inset = bp.ACTIVE_PEN / 2.0
                    self.assertGreaterEqual(got.left() - lit.left(), inset - 0.01)
                    self.assertGreaterEqual(lit.right() - got.right(), inset - 0.01)

    def test_the_offset_moves_the_plate_by_exactly_that_much(self):
        """The keys are shifted by the layout origin; the board must follow, or
        it lands somewhere else entirely."""
        board = bo.load()
        if board is None:
            self.skipTest("no board outline shipped")
        # Hold the scenes: they own the items, and a temporary one takes its
        # QGraphicsPathItem down with it the moment the expression ends.
        s1, s2 = QGraphicsScene(), QGraphicsScene()
        a = bp.add_board(s1, 80.0, 0.0, 0.0, dark=True)[0].boundingRect()
        b = bp.add_board(s2, 80.0, 1.0, 0.5, dark=True)[0].boundingRect()
        self.assertAlmostEqual(a.x() - 80.0, b.x(), places=3)
        self.assertAlmostEqual(a.y() - 40.0, b.y(), places=3)


class _Absent:
    """Stands in for "no board description" without touching the shipped file.

    `add_board(board=None)` means "load the shipped one", so a sentinel is the
    only way to exercise the empty path; the loader's own None return is
    covered in the service tests.
    """
    halves = ()


if __name__ == "__main__":
    unittest.main()
