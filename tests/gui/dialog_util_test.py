"""position_near_tray — shared corner-snapping helper.

The host-update / firmware-release progress dialogs and HidFwUpDialog all snap
to the screen corner nearest the tray icon through this one helper. Verifies the
corner math against a synthetic screen, and the no-tray fallback (bottom-right).
Construction needs only PyQt5, so it runs under the offscreen Qt platform.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QRect, QPoint
    from PyQt5.QtWidgets import QApplication, QWidget
    from polyhost.gui import dialog_util
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e


class _FakeTray:
    def __init__(self, rect):
        self._rect = rect

    def geometry(self):
        return self._rect


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TestPositionNearTray(unittest.TestCase):

    def setUp(self):
        self.w = QWidget()
        self.addCleanup(self.w.deleteLater)
        # Pin the frame size so the corner math is exact (offscreen frame
        # geometry is otherwise unstable by a pixel after move()).
        self.w.frameGeometry = lambda: QRect(0, 0, 200, 100)
        # Drive the screen geometry deterministically rather than depending on
        # whatever offscreen reports.
        self._avail = QRect(0, 0, 1000, 800)
        self._patch_screen()

    def _patch_screen(self):
        screen = _APP.primaryScreen()
        self._orig_screen_at = QApplication.screenAt
        self._orig_avail = screen.availableGeometry
        avail = self._avail
        QApplication.screenAt = staticmethod(lambda pt: screen)
        screen.availableGeometry = lambda: avail
        self.addCleanup(setattr, QApplication, "screenAt", self._orig_screen_at)
        self.addCleanup(setattr, screen, "availableGeometry", self._orig_avail)

    def _move_pos(self):
        moved = {}
        self.w.move = lambda x, y: moved.update(x=x, y=y)
        return moved

    def test_bottom_right_tray(self):
        moved = self._move_pos()
        # tray near bottom-right of the available area
        tray = _FakeTray(QRect(960, 770, 16, 16))
        dialog_util.position_near_tray(self.w, tray, margin=12)
        # QRect.right()/bottom() are inclusive (x + w - 1), so 999/799 here.
        self.assertEqual(moved["x"], 999 - 200 - 12)
        self.assertEqual(moved["y"], 799 - 100 - 12)

    def test_top_left_tray(self):
        moved = self._move_pos()
        tray = _FakeTray(QRect(0, 0, 16, 16))
        dialog_util.position_near_tray(self.w, tray, margin=12)
        self.assertEqual(moved["x"], 12)
        self.assertEqual(moved["y"], 12)

    def test_no_tray_falls_back_bottom_right(self):
        moved = self._move_pos()
        dialog_util.position_near_tray(self.w, None, margin=12)
        # QRect.right()/bottom() are inclusive (x + w - 1), so 999/799 here.
        self.assertEqual(moved["x"], 999 - 200 - 12)
        self.assertEqual(moved["y"], 799 - 100 - 12)


if __name__ == "__main__":
    unittest.main()
