"""gui/menu_tiles.py: tiles bound to a menu's actions, and where they are used."""
import os
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QAction, QActionGroup, QApplication, QMenu  # noqa: E402

from polyhost.gui import keycap_tiles, menu_tiles  # noqa: E402

_APP = QApplication.instance() or QApplication([])


class SupportTest(unittest.TestCase):

    def test_windows_yes_macos_no(self):
        self.assertTrue(menu_tiles.tiles_supported("win32", env={}))
        self.assertFalse(menu_tiles.tiles_supported("darwin", env={}))

    def test_linux_follows_the_status_notifier_host(self):
        with mock.patch.object(menu_tiles, "_status_notifier_host", return_value=True):
            self.assertFalse(menu_tiles.tiles_supported("linux", env={}))
        with mock.patch.object(menu_tiles, "_status_notifier_host", return_value=False):
            self.assertTrue(menu_tiles.tiles_supported("linux", env={}))

    def test_the_environment_overrides(self):
        self.assertTrue(menu_tiles.tiles_supported("darwin", env={"POLYHOST_MENU_TILES": "1"}))
        self.assertFalse(menu_tiles.tiles_supported("win32", env={"POLYHOST_MENU_TILES": "0"}))


class TileGridTest(unittest.TestCase):

    def setUp(self):
        self.menu = QMenu()
        self.addCleanup(self.menu.deleteLater)
        group = QActionGroup(self.menu)
        self.actions = []
        for i, text in enumerate(("Small", "Medium", "Large")):
            act = QAction(text, self.menu, checkable=True)
            act.setData(i)
            group.addAction(act)
            self.menu.addAction(act)
            self.actions.append(act)
        self.menu.addSeparator()
        self.other = self.menu.addAction("Back to automatic")
        icons = [keycap_tiles.to_icon(p) for p in keycap_tiles.size_panels([0, 1, 2])]
        with mock.patch.dict(os.environ, {"POLYHOST_MENU_TILES": "1"}):
            self.holder = menu_tiles.add_tiles(self.menu, self.actions, icons, 3,
                                               keycap_tiles.TILE_SIZE, labels=["S", "M", "L"])
        self.tiles = self.holder.defaultWidget().tiles

    def test_the_rows_are_replaced_by_the_grid(self):
        self.assertEqual(self.menu.actions()[0], self.holder)
        for act in self.actions:
            self.assertNotIn(act, self.menu.actions())
        self.assertIn(self.other, self.menu.actions())

    def test_a_click_triggers_the_action(self):
        seen = []
        self.actions[2].triggered.connect(lambda: seen.append(2))
        self.tiles[2].click()
        self.assertEqual(seen, [2])
        self.assertTrue(self.actions[2].isChecked())

    def test_tiles_follow_the_actions(self):
        self.actions[1].setChecked(True)
        self.assertTrue(self.tiles[1].isChecked())
        self.assertFalse(self.tiles[0].isChecked())
        self.actions[0].setEnabled(False)
        self.assertFalse(self.tiles[0].isEnabled())
        self.assertEqual([t.text() for t in self.tiles], ["S", "M", "L"])

    def test_a_disabled_action_is_not_triggered(self):
        seen = []
        self.actions[0].triggered.connect(lambda: seen.append(0))
        self.actions[0].setEnabled(False)
        menu_tiles.TileGrid._trigger(self.actions[0])
        self.assertEqual(seen, [])

    def test_nothing_is_added_where_tiles_are_not_supported(self):
        menu = QMenu()
        self.addCleanup(menu.deleteLater)
        act = menu.addAction("x")
        with mock.patch.dict(os.environ, {"POLYHOST_MENU_TILES": "0"}):
            self.assertIsNone(menu_tiles.add_tiles(menu, [act], [None], 1, keycap_tiles.TILE_SIZE))
        self.assertEqual(menu.actions(), [act])


class PanelTest(unittest.TestCase):

    def test_every_panel_has_ink_except_off(self):
        panels = (keycap_tiles.size_panels([0, 1, 2])
                  + [keycap_tiles.brightness_panel(v) for v in (2, 25, 50)]
                  + [keycap_tiles.idle_panel(s) for s in range(4)]
                  + [keycap_tiles.script_panel(0)])
        for panel in panels:
            self.assertEqual(panel.size, (keycap_tiles.PANEL_W, keycap_tiles.PANEL_H))
            self.assertGreater(panel.getextrema()[1], 0)

    def test_sizes_grow(self):
        heights = [p.getbbox()[3] - p.getbbox()[1] for p in keycap_tiles.size_panels([0, 1, 2])]
        self.assertLess(heights[0], heights[1])
        self.assertLess(heights[1], heights[2])

    def test_brightness_rises_with_the_level(self):
        tops = [keycap_tiles.brightness_panel(v).getextrema()[1] for v in (2, 25, 50)]
        self.assertEqual(tops, sorted(tops))
        self.assertLess(tops[0], tops[2])


if __name__ == "__main__":
    unittest.main()
