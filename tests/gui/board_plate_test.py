"""board_plate — the board the layout editor draws its keys on.

The plate is decoration, so what matters is that it cannot get in the way: it
must sit BEHIND every key, take no input, and disappear rather than raise when
the shipped description is missing.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
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

    def test_a_screen_image_is_SCALED_to_the_lit_rectangle(self):
        """The pixmap stays at its native 128x64 and the ITEM scales, so zooming in
        resolves more panel; the check is that what lands on screen is the lit
        rectangle either way."""
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
            got = item.sceneBoundingRect()
            self.assertAlmostEqual(got.x(), x * 80.0, places=3)
            self.assertAlmostEqual(got.width(), w * 80.0, places=2)

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
