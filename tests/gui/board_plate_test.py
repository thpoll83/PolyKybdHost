"""board_plate — the board the layout editor draws its keys on.

The plate is decoration, so what matters is that it cannot get in the way: it
must sit BEHIND every key, take no input, and disappear rather than raise when
the shipped description is missing.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
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
        # plate + (glass, active area, caption) per panel
        self.assertEqual(len(board.halves) + panels * 3, len(items))
        self.assertEqual(len(items), len(self.scene.items()))

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
