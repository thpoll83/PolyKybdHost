"""Shared GUI dialog helpers (Qt)."""

import sys

from PyQt5.QtCore import QEvent, QObject, Qt, QTimer
from PyQt5.QtWidgets import QApplication, QWidget


def position_near_tray(widget, tray_icon, margin: int = 12):
    """Move ``widget`` to the screen corner nearest the system-tray icon.

    Picks the screen that contains the tray icon (falling back to primary) and
    snaps the widget to whichever corner of that screen's available area the
    tray icon sits in. With no usable tray geometry it lands bottom-right.

    Call after the widget is shown so its frame size is finalised (defer one
    event-loop tick via ``QTimer.singleShot(0, ...)`` if needed).
    """
    tray_geom = tray_icon.geometry() if tray_icon else None

    # Find the screen that contains the tray icon, fall back to primary.
    screen = None
    if tray_geom and not tray_geom.isEmpty():
        screen = QApplication.screenAt(tray_geom.center())
    if screen is None:
        screen = QApplication.primaryScreen()
    if screen is None:
        return

    avail = screen.availableGeometry()
    dw    = widget.frameGeometry().width()
    dh    = widget.frameGeometry().height()

    if tray_geom and not tray_geom.isEmpty():
        # Snap to whichever corner of the available area the tray icon is in.
        right  = tray_geom.center().x() >= avail.center().x()
        bottom = tray_geom.center().y() >= avail.center().y()
        x = avail.right()  - dw - margin if right  else avail.left() + margin
        y = avail.bottom() - dh - margin if bottom else avail.top()  + margin
    else:
        x = avail.right()  - dw - margin
        y = avail.bottom() - dh - margin

    widget.move(x, y)


def wants_front(widget) -> bool:
    """Is this a window the user opened, rather than transient chrome?

    Pure so the rule can be tested without a Mac. Popups, tooltips, splash
    screens and drag shadows all arrive as top-level widgets and must NOT
    promote the application — a tooltip that steals focus is worse than the bug
    being fixed.
    """
    if widget is None or not isinstance(widget, QWidget) or not widget.isWindow():
        return False
    # ⚠️ Compare the MASKED type, not a bit test: the types are overlapping
    # values, not flags (Popup 0x9, Tool 0xb, ToolTip 0xd, SplashScreen 0xf),
    # so `flags & Qt.Popup` is true for a Tool and for a real Dialog alike and
    # would suppress the very windows this exists for.
    kind = widget.windowFlags() & Qt.WindowType_Mask
    return kind not in (Qt.Popup, Qt.ToolTip, Qt.SplashScreen,
                        Qt.SubWindow, Qt.Desktop)


def bring_to_front(widget):
    """Put `widget` in front of whatever the user is looking at.

    ⚠️ **On macOS `raise_()` + `activateWindow()` is NOT enough, and that is the
    whole reason this exists.** A tray app is an ACCESSORY application — it owns
    no Dock tile, and the `.app` launcher says so outright with `LSUIElement` —
    and macOS does not make an accessory the ACTIVE application just because it
    opened a window. Qt then raises the window correctly *within our own
    process* while the process itself is still behind, so the window lands under
    whatever the user was in. Reported from the field for "Log file...", and it
    was never specific to that window: every window the tray opens does it
    (2026-09-21).

    `activateIgnoringOtherApps_(True)` is what promotes the process, and it runs
    BEFORE the Qt raise so the window ordering settles once the app is already
    frontmost.
    """
    from polyhost.util.macos_ui import activate_app
    activate_app()                      # no-op off macOS
    widget.raise_()
    widget.activateWindow()


def any_real_window_visible(widgets) -> bool:
    """Is any of `widgets` a user-facing window that is still on screen?"""
    return any(wants_front(w) and w.isVisible() for w in widgets)


class _FrontOnShow(QObject):
    """Brings the app forward when a real window is shown, and gives it a Dock
    icon for as long as one is open.

    ⚠️ The Dock icon is not decoration. An ACCESSORY app is never reported as
    the frontmost application, so the window tracker saw the app behind our
    window instead (Terminal, measured 2026-09-23) and PolyHost's own windows
    could never get their ESC mark. As a REGULAR app the process is frontmost
    like any other, and `handler.own_process` names it. See
    `macos_ui.show_dock_icon`.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._regular = False

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Show and wants_front(obj):
            if not self._regular:
                from polyhost.util.macos_ui import show_dock_icon
                self._regular = show_dock_icon()
            bring_to_front(obj)
        elif kind in (QEvent.Hide, QEvent.Close) and self._regular \
                and wants_front(obj):
            # Deferred one tick: during Hide the window still reports itself
            # visible, and a dialog that closes as another opens must not
            # flicker the Dock icon.
            QTimer.singleShot(0, self._drop_dock_icon_if_idle)
        return False

    def _drop_dock_icon_if_idle(self):
        if not self._regular:
            return
        if any_real_window_visible(QApplication.topLevelWidgets()):
            return
        from polyhost.util.macos_ui import hide_dock_icon
        # A refused switch leaves the app regular; the next Hide retries it.
        if hide_dock_icon():
            self._regular = False


def install_front_on_show(app):
    """macOS: make every window the tray opens come to the front.

    ⚠️ **A FILTER, not a call at each `show()`.** There are a dozen window-
    opening sites across the two tray apps and `.exec_()` modals among them, so
    a per-site fix is the enumerating-guard shape this repo keeps getting caught
    by -- the thirteenth window would be added without it and nobody would
    notice until a user reported the same bug again. One filter covers every
    window, including the ones nobody has written yet.

    ⚠️ Installed on macOS ONLY. Windows and Linux already raise these windows
    correctly, and calling `activateWindow()` on every show there would be a
    behaviour change nobody asked for.

    ⚠️ The filter is kept alive on `app`: a `QObject` that only Qt references is
    garbage-collected, and an event filter that has been collected silently
    stops filtering.
    """
    if sys.platform != "darwin" or app is None:
        return None
    existing = getattr(app, "_poly_front_filter", None)
    if existing is not None:
        return existing
    flt = _FrontOnShow(app)
    app.installEventFilter(flt)
    app._poly_front_filter = flt
    return flt
