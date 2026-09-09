"""Draw the split72 board under the editor's keys: the plate, and the screens.

The editor used to show 74 tiles floating in space, which says nothing about
which half a key is on, where the thumb clusters sit relative to the case, or
that there are two status displays at all. This adds the board they are mounted
on -- the real `Edge.Cuts` outline of each half (see
`scripts/export_board_outline.py`) plus the optional 0.96" status panels -- as
plain background items behind the keys.

Two things it deliberately is NOT:

* **not interactive.** Every item is drawn at a negative Z with no flags, so it
  cannot take a click, a hover or the selection away from a key. The editor's
  job is assigning keycodes and nothing here may get in the way of that.
* **not a source of truth.** It is decoration, so `add_board` returns quietly
  when the shipped description is missing -- see `services.board_outline`.

⚠️ The status panel has NO side bezel: its screen spans the corner and meets the
housing left and right, so `w == aw` and only the height carries glass. That comes
out of the exporter, not from here.

⚠️ The tiles are drawn dark in BOTH themes (`RenderableKey` hardcodes its
greys), so the plate has to work under dark keys either way: a graphite-blue
board in the dark theme, a pale one in the light theme, keeping the same blue ->
cyan sweep the brand mark uses.
"""
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QLinearGradient, QPainterPath, QPen, QPolygonF
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsRectItem

from polyhost.services import board_outline as bo

#: Behind every key (which sit at the default Z of 0), and the plate behind the
#: screens that stand on it.
Z_PLATE = -20
Z_DISPLAY = -10

#: Scene ground, plate, edge, screen glass and lit area -- dark theme then light.
#: A `scene` of None leaves the view's own background alone.
#: ⚠️ The two themes are NOT the same palette at different lightnesses. Dark puts a
#: graphite-blue board on the view's default ground; light puts a GREY board on a
#: blue ground -- the blue moved to the background so the board reads as the object
#: rather than as the biggest coloured shape on screen.
DARK = {
    "scene": None,
    "plate_top": "#26333D", "plate_bottom": "#1B2429", "edge": "#4E869F",
    "glass": "#0E1417", "glass_edge": "#3E525C", "active": "#0B2A31",
    "active_edge": "#2E7F91",
}
LIGHT = {
    "scene": "#D9E5ED",
    "plate_top": "#ECECEC", "plate_bottom": "#D6D6D6", "edge": "#5E8AA1",
    "glass": "#2A343A", "glass_edge": "#8AA3B0", "active": "#111C21",
    "active_edge": "#4E9FB2",
}


def add_board(scene, scale, offset_x=0.0, offset_y=0.0, dark=True, board=None):
    """Add the plate and the status screens to `scene`. Returns the items added.

    `scale` is pixels per key unit and `offset_x`/`offset_y` the layout origin
    the keys were shifted by, so the board lands in the same frame as they do.
    """
    board = board if board is not None else bo.load()
    if board is None:
        return []

    ink = DARK if dark else LIGHT
    if ink["scene"]:
        scene.setBackgroundBrush(QBrush(QColor(ink["scene"])))
    items = []
    for half in board.halves:
        items.append(_plate(scene, half, scale, offset_x, offset_y, ink))
        for display in half.displays:
            items.extend(_display(scene, display, scale, offset_x, offset_y, ink))
    return items


def _plate(scene, half, scale, ox, oy, ink):
    poly = QPolygonF([QPointF((x - ox) * scale, (y - oy) * scale)
                      for x, y in half.outline])
    path = QPainterPath()
    path.addPolygon(poly)
    path.closeSubpath()

    item = QGraphicsPathItem(path)
    box = path.boundingRect()
    # Top-to-bottom rather than corner-to-corner: the halves are mirror images,
    # so a diagonal sweep would run opposite ways on the two boards and read as
    # a lighting mistake rather than a finish.
    grad = QLinearGradient(box.topLeft(), box.bottomLeft())
    grad.setColorAt(0.0, QColor(ink["plate_top"]))
    grad.setColorAt(1.0, QColor(ink["plate_bottom"]))
    item.setBrush(QBrush(grad))
    pen = QPen(QColor(ink["edge"]), 2.0)
    pen.setJoinStyle(Qt.RoundJoin)
    item.setPen(pen)
    item.setZValue(Z_PLATE)
    scene.addItem(item)
    return item


def _display(scene, display, scale, ox, oy, ink):
    def rect(r):
        x, y, w, h = r
        return QRectF((x - ox) * scale, (y - oy) * scale, w * scale, h * scale)

    glass = QGraphicsRectItem(rect(display.rect))
    glass.setBrush(QBrush(QColor(ink["glass"])))
    glass.setPen(QPen(QColor(ink["glass_edge"]), 1.2))
    glass.setZValue(Z_DISPLAY)
    scene.addItem(glass)

    active = QGraphicsRectItem(rect(display.active_rect))
    active.setBrush(QBrush(QColor(ink["active"])))
    active.setPen(QPen(QColor(ink["active_edge"]), 1.0))
    active.setZValue(Z_DISPLAY)
    scene.addItem(active)

    return [glass, active]
