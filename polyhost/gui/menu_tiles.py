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
from polyhost.gui.ui_kit import px
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


def wrap_caption(text, metrics, width, max_lines=3):
    """Break ``text`` into at most ``max_lines`` lines that fit ``width`` px.

    QToolButton draws its text on one line, so a long menu label under an icon
    would widen the tile. A word that does not fit is elided.
    """
    # The "…" that marks an entry opening a dialog reads as a cut-off word
    # under an icon.
    text = text.rstrip().rstrip("\u2026").rstrip(".").rstrip() if text.rstrip().endswith(("\u2026", "...")) else text
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and metrics.horizontalAdvance(candidate) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + [" ".join(lines[max_lines - 1:])]
    return "\n".join(metrics.elidedText(ln, Qt.ElideRight, width) for ln in lines)


class TileGrid(QWidget):
    """A grid of tiles, one per bound QAction.

    A tile follows its action's text, tooltip, checked, enabled and visible
    state. A tile whose action is hidden is left out and the others close up.
    """

    def __init__(self, actions, icons, columns, icon_size, parent=None, tile_width=None):
        super().__init__(parent)
        self.setStyleSheet(_TILE_STYLE)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(px(8), px(6), px(8), px(6))
        self._grid.setSpacing(px(4))
        self._columns = columns
        # Measured before the stylesheet polishes the tile, so leave a margin.
        self._text_width = (tile_width or icon_size.width() + px(20)) - px(24)
        self.tiles = []
        self._actions = list(actions)
        for action, icon in zip(self._actions, icons):
            tile = QToolButton(self)
            tile.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            tile.setAutoRaise(True)
            tile.setIconSize(icon_size)
            tile.setFixedWidth(tile_width or icon_size.width() + px(20))
            tile.setIcon(icon if icon is not None else action.icon())
            tile.clicked.connect(lambda _checked=False, a=action: self._trigger(a))
            action.changed.connect(lambda t=tile, a=action: self._sync(t, a))
            self.tiles.append(tile)
            self._sync(tile, action, relayout=False)
        self._relayout()

    def _sync(self, tile, action, relayout=True):
        text = action.iconText()
        caption = wrap_caption(text, tile.fontMetrics(), self._text_width)
        tile.setText(caption)
        tip = action.toolTip()
        if tip and tip != text:
            tile.setToolTip(tip)
        elif caption.replace("\n", " ") != text.rstrip(".\u2026 "):
            tile.setToolTip(text)    # the caption was shortened: show it whole
        else:
            tile.setToolTip("")
        tile.setCheckable(action.isCheckable())
        tile.setChecked(action.isChecked())
        # Qt reports a hidden action as disabled; the tile is hidden instead.
        tile.setEnabled(action.isEnabled() or not action.isVisible())
        if tile.isHidden() == action.isVisible() and relayout:
            self._relayout()

    def _relayout(self):
        for tile in self.tiles:
            self._grid.removeWidget(tile)
        shown = [(t, a) for t, a in zip(self.tiles, self._actions) if a.isVisible()]
        for tile, action in zip(self.tiles, self._actions):
            tile.setVisible(action.isVisible())
        for i, (tile, _action) in enumerate(shown):
            self._grid.addWidget(tile, i // self._columns, i % self._columns)
        self.adjustSize()

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


def add_tiles(menu, actions, icons, columns, icon_size, labels=None, tile_width=None):
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
    grid = TileGrid(actions, icons, columns, QSize(icon_size), menu, tile_width)
    holder = QWidgetAction(menu)
    holder.setDefaultWidget(grid)
    # The grid goes first; a submenu row (Fix Left/Right Side) sits under it.
    first = menu.actions()[0] if menu.actions() else None
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


# The icon tiles of the plain submenus (Updates, Maintenance, Help & About),
# at 100 %; ui_kit.px scales them.
ICON_TILE_PX = 32
ICON_TILE_WIDTH = 150


def add_icon_tiles_on_first_show(menu, columns=3):
    """Tiles for a menu's own entries, from their Material icons.

    Built on the first show, so it takes every entry added by then, including
    ones added after the menu was created. A submenu entry (Fix Left/Right Side)
    stays a row under the grid, because a tile cannot open a submenu.
    """
    if not tiles_supported():
        return
    state = {"done": False}

    def build():
        if state["done"]:
            return
        state["done"] = True
        actions = [a for a in menu.actions()
                   if not a.isSeparator() and a.menu() is None
                   and not isinstance(a, QWidgetAction)]
        if actions:
            add_tiles(menu, actions, [None] * len(actions), columns,
                      QSize(px(ICON_TILE_PX), px(ICON_TILE_PX)), tile_width=px(ICON_TILE_WIDTH))

    menu.aboutToShow.connect(build)
