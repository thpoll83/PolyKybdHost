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
                                               keycap_tiles.tile_size(), labels=["S", "M", "L"])
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
            self.assertIsNone(menu_tiles.add_tiles(menu, [act], [None], 1, keycap_tiles.tile_size()))
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


class IconTilesTest(unittest.TestCase):
    """add_icon_tiles_on_first_show: the plain entries of a static submenu."""

    def _menu(self):
        menu = QMenu()
        self.addCleanup(menu.deleteLater)
        sub = menu.addMenu("Fix Left/Right Side")
        a = menu.addAction("Reset overlays")
        menu.addSeparator()
        b = menu.addAction("Flash firmware file (.bin)\u2026")
        hidden = menu.addAction("Allow access to the keyboard (udev rule)\u2026")
        hidden.setVisible(False)
        return menu, sub, [a, b, hidden]

    def _show(self, menu):
        with mock.patch.dict(os.environ, {"POLYHOST_MENU_TILES": "1"}):
            menu_tiles.add_icon_tiles_on_first_show(menu)
            menu.aboutToShow.emit()
            menu.aboutToShow.emit()     # a second show builds nothing more
        _APP.processEvents()
        return [a for a in menu.actions() if isinstance(a, menu_tiles.QWidgetAction)]

    def test_plain_entries_become_tiles_and_a_submenu_stays_a_row(self):
        menu, sub, actions = self._menu()
        holders = self._show(menu)
        self.assertEqual(len(holders), 1)
        self.assertEqual(menu.actions()[:2], [holders[0], sub.menuAction()])
        for act in actions:
            self.assertNotIn(act, menu.actions())

    def test_a_hidden_entry_has_no_tile_until_it_is_shown(self):
        menu, _sub, actions = self._menu()
        grid = self._show(menu)[0].defaultWidget()
        self.assertTrue(grid.tiles[2].isHidden())
        actions[2].setVisible(True)
        self.assertFalse(grid.tiles[2].isHidden())
        self.assertTrue(grid.tiles[2].isEnabled())

    def test_the_dialog_ellipsis_is_dropped_from_the_caption(self):
        menu, _sub, _actions = self._menu()
        grid = self._show(menu)[0].defaultWidget()
        self.assertNotIn("\u2026", grid.tiles[1].text())
        self.assertIn("firmware", grid.tiles[1].text())


class WrapCaptionTest(unittest.TestCase):

    def test_long_text_wraps_and_is_elided_past_three_lines(self):
        from PyQt5.QtGui import QFontMetrics, QFont
        fm = QFontMetrics(QFont())
        out = menu_tiles.wrap_caption("Check for keyboard firmware update and more words here",
                                      fm, 90)
        lines = out.split("\n")
        self.assertLessEqual(len(lines), 3)
        for ln in lines:
            self.assertLessEqual(fm.horizontalAdvance(ln), 90)


class ScaleTest(unittest.TestCase):
    """Sizes set in pixels follow the display scale, as Qt's own metrics do."""

    def test_sizes_grow_with_the_scale(self):
        from polyhost.gui import ui_kit
        with mock.patch.object(ui_kit, "ui_scale", return_value=1.5):
            self.assertEqual(ui_kit.px(18), 27)
            self.assertEqual(ui_kit.button_icon_size().width(), 27)
            self.assertEqual(ui_kit.headline_icon_px(), 54)
            self.assertEqual(keycap_tiles.tile_scale(), 3)
            self.assertEqual(keycap_tiles.tile_size().width(), 216)
        with mock.patch.object(ui_kit, "ui_scale", return_value=1.0):
            self.assertEqual(keycap_tiles.tile_size().width(), 144)

    def test_the_scale_follows_the_style(self):
        from PyQt5.QtWidgets import QStyle
        from polyhost.gui import ui_kit
        style = _APP.style()
        with mock.patch.object(type(style), "pixelMetric",
                               side_effect=lambda m, *a: 24 if m == QStyle.PM_ButtonIconSize else 0):
            self.assertEqual(ui_kit.ui_scale(), 1.5)


class ReviewFixesTest(unittest.TestCase):
    """Three defects CodeRabbit found on #775."""

    def test_a_dim_level_is_not_dimmed_twice(self):
        # 1 % maps to grey 70 + 185 * sqrt(2/50) = 107.
        self.assertEqual(keycap_tiles.brightness_panel(2).getextrema()[1], 107)

    def test_a_dim_ghost_does_not_cover_the_bright_legend(self):
        panel = keycap_tiles.idle_panel(0)
        self.assertEqual(panel.getextrema()[1], 255)
        self.assertIn(70, set(panel.tobytes()))

    def test_clicking_the_chosen_tile_keeps_it_chosen(self):
        menu = QMenu()
        self.addCleanup(menu.deleteLater)
        group = QActionGroup(menu)
        actions = []
        for text in "ab":
            act = QAction(text, menu, checkable=True)
            group.addAction(act)
            menu.addAction(act)
            actions.append(act)
        actions[0].setChecked(True)
        with mock.patch.dict(os.environ, {"POLYHOST_MENU_TILES": "1"}):
            holder = menu_tiles.add_tiles(menu, actions, [None, None], 2, keycap_tiles.tile_size())
        tile = holder.defaultWidget().tiles[0]
        tile.click()
        self.assertTrue(actions[0].isChecked())
        self.assertTrue(tile.isChecked())

    def test_a_failing_grid_leaves_the_rows(self):
        menu = QMenu()
        self.addCleanup(menu.deleteLater)
        rows = [menu.addAction("a"), menu.addAction("b")]
        with mock.patch.dict(os.environ, {"POLYHOST_MENU_TILES": "1"}), \
                mock.patch.object(menu_tiles.TileGrid, "_relayout", side_effect=RuntimeError("x")), \
                self.assertLogs("polyhost.menu_tiles", "ERROR"):
            menu_tiles.add_icon_tiles_on_first_show(menu)
            menu.aboutToShow.emit()
        self.assertEqual(menu.actions(), rows)


if __name__ == "__main__":
    unittest.main()
