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

⚠️ The status panel's side bezel is NOT DRAWN -- the glass is exactly as wide as the
screen, so `w == aw` and only the height carries glass -- and the panel therefore stops
one module bezel short of the housing rather than meeting it. That comes out of the
exporter, not from here.

The screen itself can carry a picture: `set_screen_images` paints a rendered panel into
the lit rectangle (see `status_screen_render`), which is how the editor shows the layer
being edited on the board rather than on a flat teal rectangle. It is optional -- with
no image the lit rectangle is drawn plain, as it always was.

⚠️ The tiles are drawn dark in BOTH themes (`RenderableKey` hardcodes its
greys), so the plate has to work under dark keys either way: a graphite-blue
board in the dark theme, a pale one in the light theme, keeping the same blue ->
cyan sweep the brand mark uses.
"""
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QLinearGradient, QPainterPath, QPen, QPolygonF
from PyQt5.QtWidgets import (QGraphicsPathItem, QGraphicsPixmapItem,
                             QGraphicsRectItem)

from polyhost.services import board_outline as bo

#: Behind every key (which sit at the default Z of 0), and the plate behind the
#: screens that stand on it. The rendered screen sits above its own glass.
Z_PLATE = -20
Z_DISPLAY = -10
Z_SCREEN = -9

#: Qt item data slots on a screen item: which half it belongs to, and the lit
#: rectangle it has to fill. The items are handed back as one flat list, so the tag is
#: what lets a caller repaint the right panel later -- a mode or layer change must not
#: have to rebuild the whole board. The box is carried too because the item's own
#: geometry is the PIXMAP's once one is set, not the rectangle it was placed in.
SCREEN_SIDE, SCREEN_BOX = 0, 1

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
    "plate_top": "#ADADAD", "plate_bottom": "#909090", "edge": "#5E8AA1",
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
            items.extend(_display(scene, display, scale, offset_x, offset_y, ink,
                                  half.side))
    return items


def set_screen_images(items, images):
    """Paint `images` (side -> QImage or None) into the screens among `items`.

    Separate from `add_board` because the picture changes far more often than the
    board does: the layer being edited and the Symbol/Preview/Real mode both move it,
    and rebuilding 74 keys and two outlines to repaint two rectangles would be absurd.
    A side with no image is cleared back to the plain lit rectangle.

    ⚠️ The pixmap is left at its NATIVE size and scaled by the item, so zooming the
    view in resolves more of the panel instead of enlarging a blurred copy -- the same
    reason the keycaps render larger than their tile.
    """
    from PyQt5.QtGui import QPixmap

    for item in items:
        side = item.data(SCREEN_SIDE)
        if side is None:
            continue
        img = (images or {}).get(side)
        if img is None:
            item.setPixmap(QPixmap())
            continue
        item.setPixmap(QPixmap.fromImage(img))
        box = item.data(SCREEN_BOX)
        item.setScale(box[2] / img.width() if img.width() else 1.0)
        item.setPos(box[0], box[1])


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


def _display(scene, display, scale, ox, oy, ink, side=None):
    def rect(r):
        x, y, w, h = r
        return QRectF((x - ox) * scale, (y - oy) * scale, w * scale, h * scale)

    glass = QGraphicsRectItem(rect(display.rect))
    glass.setBrush(QBrush(QColor(ink["glass"])))
    glass.setPen(QPen(QColor(ink["glass_edge"]), 1.2))
    glass.setZValue(Z_DISPLAY)
    scene.addItem(glass)

    lit = rect(display.active_rect)
    active = QGraphicsRectItem(lit)
    active.setBrush(QBrush(QColor(ink["active"])))
    active.setPen(QPen(QColor(ink["active_edge"]), 1.0))
    active.setZValue(Z_DISPLAY)
    scene.addItem(active)

    # Always created, even with nothing to show: `set_screen_images` needs something
    # to paint into, and an empty pixmap draws nothing at all.
    shot = QGraphicsPixmapItem()
    shot.setTransformationMode(Qt.SmoothTransformation)
    shot.setData(SCREEN_SIDE, side)
    shot.setData(SCREEN_BOX, (lit.x(), lit.y(), lit.width()))
    shot.setPos(lit.x(), lit.y())
    shot.setZValue(Z_SCREEN)
    scene.addItem(shot)

    return [glass, active, shot]
