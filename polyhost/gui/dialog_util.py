"""Shared GUI dialog helpers (Qt)."""

from PyQt5.QtWidgets import QApplication


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
