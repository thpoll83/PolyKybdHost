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
import html
import unicodedata

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


def _is_wide(ch):
    """A Chinese, Japanese or Korean character: text in these scripts has no
    spaces, and a line may break between any two such characters."""
    return bool(ch) and unicodedata.east_asian_width(ch) in ("W", "F")


def _break_units(text, metrics, width):
    """The pieces a caption may break between, as ``(piece, glued)``: words,
    and each wide character on its own. ``glued`` marks a piece split out of
    the same word, which joins its neighbour without a space; a word keeps
    the space the text had before it. Without the split, a Japanese caption
    was one unbreakable word and was shortened even where it fits on two lines."""
    units = []
    for word in text.split():
        if any(_is_wide(c) for c in word) and metrics.horizontalAdvance(word) > width:
            pieces, run = [], ""
            for c in word:
                if _is_wide(c):
                    if run:
                        pieces.append(run)
                        run = ""
                    pieces.append(c)
                else:
                    run += c
            if run:
                pieces.append(run)
            units.extend((p, i > 0) for i, p in enumerate(pieces))
        else:
            units.append((word, False))
    return units


def wrap_caption(text, metrics, width, max_lines=2):
    """Break ``text`` into at most ``max_lines`` lines that fit ``width`` px.

    QToolButton draws its text on one line, so a long menu label under an icon
    would widen the tile. A word that does not fit is elided.
    """
    # The "…" that marks an entry opening a dialog reads as a cut-off word
    # under an icon.
    text = text.rstrip().rstrip("\u2026").rstrip(".").rstrip() if text.rstrip().endswith(("\u2026", "...")) else text
    lines, line = [], ""
    for word, glued in _break_units(text, metrics, width):
        candidate = f"{line}{'' if glued else ' '}{word}" if line else word
        if line and metrics.horizontalAdvance(candidate) > width:
            lines.append((line, glued))
            line = word
        else:
            line = candidate
    if line:
        lines.append((line, None))
    if len(lines) > max_lines:
        # Past the last line: join the rest back with the space (or none) the
        # text had at each break, and let the elision below shorten it.
        tail = lines[max_lines - 1][0]
        for (piece, _), (_, glued) in zip(lines[max_lines:], lines[max_lines - 1:]):
            tail += ("" if glued else " ") + piece
        lines = lines[:max_lines - 1] + [(tail, None)]
    lines = [ln for ln, _ in lines]
    return "\n".join(metrics.elidedText(ln, Qt.ElideRight, width) for ln in lines)


def fit_caption_width(texts, metrics, narrowest, widest, step=4):
    """The narrowest text width, from ``narrowest`` up to ``widest``, at which
    every text fits on two lines unshortened; ``widest`` when none does."""
    for width in range(narrowest, widest + 1, step):
        if all("\u2026" not in wrap_caption(t, metrics, width)
               or "\u2026" in t.rstrip(".\u2026 ")       # a label with its own …
               for t in texts):
            return width
    return widest


class TileGrid(QWidget):
    """A grid of tiles, one per bound QAction.

    A tile follows its action's text, tooltip, checked, enabled and visible
    state. A tile whose action is hidden is left out and the others close up.
    """

    def __init__(self, actions, icons, columns, icon_size, parent=None, tile_width=None,
                 max_tile_width=None):
        super().__init__(parent)
        self.setStyleSheet(_TILE_STYLE)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(px(8), px(6), px(8), px(6))
        self._grid.setSpacing(px(4))
        self._columns = columns
        self._actions = list(actions)
        # Measured before the stylesheet polishes the tile, so leave a margin.
        self._margin = px(24)
        self._width_range = ((tile_width, max_tile_width) if tile_width and max_tile_width
                             else None)
        tile_width = self._fitted_width() or tile_width
        self._text_width = (tile_width or icon_size.width() + px(20)) - self._margin
        self.tiles = []
        for action, icon in zip(self._actions, icons):
            tile = QToolButton(self)
            tile.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            tile.setAutoRaise(True)
            tile.setIconSize(icon_size)
            tile.setFixedWidth(tile_width or icon_size.width() + px(20))
            tile.setIcon(icon if icon is not None else action.icon())
            # Resync after the click: a click on the tile already chosen in an
            # exclusive group unchecks the tile, while the action stays checked
            # and emits no changed signal.
            tile.clicked.connect(
                lambda _checked=False, t=tile, a=action: (self._trigger(a), self._sync(t, a)))
            action.changed.connect(lambda t=tile, a=action: self._sync(t, a))
            self.tiles.append(tile)
            self._sync(tile, action, relayout=False)
        self._relayout()

    def _fitted_width(self):
        """The tile width at which every caption fits on two lines, between the
        narrowest and widest allowed; None for a grid of fixed width."""
        if self._width_range is None:
            return None
        lo, hi = self._width_range
        return fit_caption_width([a.iconText() for a in self._actions], self.fontMetrics(),
                                 lo - self._margin, hi - self._margin) + self._margin

    def _sync(self, tile, action, relayout=True):
        # An entry whose text changes at runtime (the firmware entry's "Update
        # firmware to v…") may need a wider tile than the grid was built with.
        width = self._fitted_width()
        if width is not None and width - self._margin != self._text_width:
            self._text_width = width - self._margin
            for t, a in zip(self.tiles, self._actions):
                t.setFixedWidth(width)
                if t is not tile:
                    self._sync(t, a, relayout=False)
            tile.setFixedWidth(width)
        text = action.iconText()
        caption = wrap_caption(text, tile.fontMetrics(), self._text_width)
        tile.setText(caption)
        # The tooltip carries what the caption leaves out: an explicit tooltip,
        # else the full menu label when a short caption (iconText) or the
        # wrap shortened it.
        full = action.text().replace("&", "").rstrip(".\u2026 ")
        tip = action.toolTip()
        # Shortened: a short caption (iconText) or an elided line. Comparing the
        # joined lines with the label would flag a cleanly wrapped CJK caption,
        # whose lines join without a space.
        shortened = (text.rstrip(".\u2026 ") != full
                     or ("\u2026" in caption and "\u2026" not in full))
        if tip and tip.rstrip(".\u2026 ") not in (text.rstrip(".\u2026 "), full):
            # An explicit tooltip (a script's preview image) does not name the
            # entry, so a shortened caption still gets its full label on top.
            if shortened:
                rich = Qt.mightBeRichText(tip)
                tip = (f"{html.escape(full)}<br>{tip}" if rich else f"{full}\n{tip}")
            tile.setToolTip(tip)
        elif shortened:
            tile.setToolTip(full)
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


def add_tiles(menu, actions, icons, columns, icon_size, labels=None, tile_width=None,
              max_tile_width=None):
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
    grid = TileGrid(actions, icons, columns, QSize(icon_size), menu, tile_width,
                    max_tile_width)
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


def _add_tiles_safely(menu, actions, icons, columns, icon_size, labels=None, tile_width=None,
                      max_tile_width=None):
    """``add_tiles`` from an aboutToShow slot, where an exception must not escape.

    PyQt5 turns an exception in a slot into sys.excepthook and then qFatal(),
    which would end the tray app on opening a menu. On a failure the menu is
    put back as it was: the grid out, the text rows in.
    """
    before = list(menu.actions())
    try:
        add_tiles(menu, actions, icons, columns, icon_size, labels, tile_width,
                  max_tile_width)
    except Exception:
        import logging
        logging.getLogger("polyhost.menu_tiles").exception("Tile grid failed; keeping the rows")
        for action in list(menu.actions()):
            if action not in before:
                menu.removeAction(action)
        for i, action in enumerate(before):
            if action not in menu.actions():
                nxt = next((a for a in before[i + 1:] if a in menu.actions()), None)
                menu.insertAction(nxt, action)


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
        _add_tiles_safely(menu, actions, icons, columns, icon_size, labels)

    menu.aboutToShow.connect(build)


# The icon tiles of the plain submenus (Updates, Maintenance, Help & About),
# at 100 %; ui_kit.px scales them.
ICON_TILE_PX = 24
ICON_TILE_WIDTH = 104       # the narrowest; it grows until every caption fits on two lines
ICON_TILE_MAX_WIDTH = 160


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
            _add_tiles_safely(menu, actions, [None] * len(actions), columns,
                              QSize(px(ICON_TILE_PX), px(ICON_TILE_PX)),
                              tile_width=px(ICON_TILE_WIDTH),
                              max_tile_width=px(ICON_TILE_MAX_WIDTH))

    menu.aboutToShow.connect(build)
