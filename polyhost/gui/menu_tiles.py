"""Tray submenus drawn as tiles: a keycap preview per choice instead of a text row.

A tile grid is a QWidgetAction, and a widget inside a menu shows only where Qt
draws that menu itself (read from qtbase 5.15.2, not tried on each desktop):

- Windows: a widgets app gets no native tray menu (QWindowsTheme's "auto" menus),
  so QSystemTrayIcon pops up the QMenu. Tiles show.
- Linux with a StatusNotifier host (KDE Plasma, GNOME with the AppIndicator
  extension): the menu is exported over DBusMenu, which carries label, icon,
  check and enabled state only. The grid would arrive as an empty row.
- Linux without one (XEmbed tray): Qt pops up the QMenu. Tiles show.
- macOS: Qt can embed a widget in the native tray menu
  (qmenu_mac.mm moveWidgetToPlatformItem), but QTBUG-63578 reports such a widget
  invisible from the second open on. Off until tried on a Mac.

``tiles_supported()`` decides, and where it says no, nothing here runs and the
menu keeps its text entries.

The grid does not replace the menu's QActions. Each tile is bound to one action:
a click triggers the action, and the tile follows the action's checked, enabled,
text and tooltip state, so the code that ticks the current choice on each show
works unchanged. The bound actions are taken out of the menu (not hidden:
Qt disables a hidden action) while the grid is shown.

``POLYHOST_MENU_TILES=1`` (or ``0``) overrides the platform check, to try the
tiles on a Mac or to turn them off.
"""

import os
import sys

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (QApplication, QGridLayout, QToolButton, QWidget,
                             QWidgetAction)

_ENV = "POLYHOST_MENU_TILES"

# Tile look: the checked tile gets the highlight ring the mockup showed. Every
# colour is a palette role, so the light and the dark theme both apply.
_TILE_STYLE = """
QToolButton { padding: 4px; border: 2px solid transparent; border-radius: 6px; }
QToolButton:hover { background: palette(midlight); }
QToolButton:checked { border-color: palette(highlight); background: palette(base); }
QToolButton:disabled { color: palette(mid); }
"""


def _status_notifier_host():
    """True when Qt 5 hands the tray menu to the desktop over DBusMenu.

    The same test as Qt's own ``isDBusTrayAvailable()`` (qtbase 5.15,
    dbustray/qdbustrayicon.cpp): a StatusNotifierWatcher on the session bus that
    reports ``IsStatusNotifierHostRegistered``. Then QDBusTrayIcon exports the
    menu, and a QWidgetAction reaches the desktop as an item with the action's
    text only (QDBusMenuItem has no field for a widget). Without one, Qt uses
    the XEmbed tray and pops up the QMenu itself.
    """
    try:
        from PyQt5.QtDBus import QDBusConnection, QDBusInterface
    except ImportError:
        return True     # cannot tell; assume the menu is exported
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False
    watcher = QDBusInterface("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher",
                             "org.kde.StatusNotifierWatcher", bus)
    if not watcher.isValid():
        return False
    value = watcher.property("IsStatusNotifierHostRegistered")
    return bool(value) if value is not None else True


def tiles_supported(platform=None, env=None):
    """Whether Qt draws the tray menu here, so a tile grid can show."""
    env = os.environ if env is None else env
    forced = env.get(_ENV, "").strip()
    if forced in ("0", "1"):
        return forced == "1"
    platform = platform or sys.platform
    if platform == "win32":
        return True
    if platform.startswith("linux"):
        return not _status_notifier_host()
    return False


class TileGrid(QWidget):
    """A grid of tiles, one per bound QAction."""

    def __init__(self, actions, icons, columns, icon_size, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_TILE_STYLE)
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setSpacing(4)
        self.tiles = []
        for i, (action, icon) in enumerate(zip(actions, icons)):
            tile = QToolButton(self)
            tile.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            tile.setAutoRaise(True)
            tile.setIconSize(icon_size)
            tile.setFixedWidth(icon_size.width() + 20)
            if icon is not None:
                tile.setIcon(icon)
            tile.clicked.connect(lambda _checked=False, a=action: self._trigger(a))
            action.changed.connect(lambda t=tile, a=action: self._sync(t, a))
            self._sync(tile, action)
            grid.addWidget(tile, i // columns, i % columns)
            self.tiles.append(tile)

    @staticmethod
    def _sync(tile, action):
        tile.setText(action.iconText())
        tile.setToolTip(action.toolTip() if action.toolTip() != action.iconText() else "")
        tile.setCheckable(action.isCheckable())
        tile.setChecked(action.isChecked())
        tile.setEnabled(action.isEnabled())

    @staticmethod
    def _trigger(action):
        # A widget in a menu does not close it; close every open popup the way
        # a click on a normal entry does, then run the action.
        for _ in range(8):
            popup = QApplication.activePopupWidget()
            if popup is None:
                break
            popup.close()
        if action.isEnabled():
            action.trigger()


def add_tiles(menu, actions, icons, columns, icon_size, labels=None):
    """Put a tile grid for ``actions`` at the top of ``menu`` and hide the
    actions' own rows. ``labels`` (optional) gives a tile a shorter caption
    than the menu entry, set as the action's iconText.

    Returns the QWidgetAction, or None where tiles are not supported.
    """
    if not tiles_supported():
        return None
    actions = list(actions)
    for i, action in enumerate(actions):
        if labels and labels[i]:
            action.setIconText(labels[i])
    grid = TileGrid(actions, icons, columns, QSize(icon_size), menu)
    holder = QWidgetAction(menu)
    holder.setDefaultWidget(grid)
    first = next((a for a in menu.actions() if a in actions), None)
    menu.insertAction(first, holder)
    # Take the rows out of the menu rather than hiding them: Qt disables a
    # hidden action (setVisible(False) forces isEnabled() to False), and a
    # disabled action ignores trigger(), so every tile would be dead.
    for action in actions:
        menu.removeAction(action)
    # A separator between two hidden rows now sits next to another one; QMenu
    # collapses neighbouring separators (separatorsCollapsible, on by default).
    return holder


def add_tiles_on_first_show(menu, actions, make_icons, columns, icon_size, labels=None):
    """``add_tiles``, deferred to the menu's first show.

    The previews decode font data, so a user who never opens the submenu pays
    nothing at startup. ``make_icons()`` returns one QIcon (or None) per action.
    """
    if not tiles_supported():
        return
    state = {"done": False}

    def build():
        if state["done"]:
            return
        state["done"] = True
        try:
            icons = make_icons()
        except Exception:   # a preview must never break the menu
            import logging
            logging.getLogger("polyhost.menu_tiles").exception("Tile previews failed")
            return
        add_tiles(menu, actions, icons, columns, icon_size, labels)

    menu.aboutToShow.connect(build)
