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
greys), so the plate has to work under dark keys either way: a graphite board in the
dark theme, a grey one in the light theme. Both are NEUTRAL and every outline is
near-black -- see the palette note below for why the blue left.
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
#: rectangle `(x, y, w, h)` it has to fit inside. The items are handed back as one flat
#: list, so the tag is what lets a caller repaint the right panel later -- a mode or
#: layer change must not have to rebuild the whole board. The box is carried too
#: because the item's own geometry is the PIXMAP's once one is set, not the rectangle
#: it was placed in.
#: ⚠️ The HEIGHT is part of it. Scaling the picture by width alone was enough while
#: the lit rectangle had the panel's own 2:1 aspect, and the moment anything reshapes
#: it -- which dropping the side bezel already did -- the image runs out of its
#: rectangle and over the frame with nothing to stop it.
SCREEN_SIDE, SCREEN_BOX = 0, 1

#: Scene ground, plate, edge, screen glass and lit area -- dark theme then light.
#: A `scene` of None leaves the view's own background alone.
#: ⚠️ The two themes are NOT the same palette at different lightnesses. Dark puts a
#: graphite board on the view's default ground; light puts a GREY board on a blue
#: ground -- the blue moved to the background so the board reads as the object rather
#: than as the biggest coloured shape on screen.
#: ⚠️ **The board itself is NEUTRAL and every outline is near-black.** The plate, the
#: screen bezel and all three strokes used to carry the brand's blue -> cyan sweep,
#: which on a real keyboard reads as a lit edge rather than as an anodised case; the
#: blue survives only as the light theme's GROUND, which is the one place it is
#: describing the page and not the object. So a channel spread in anything but
#: `scene` is a regression, and `test_the_board_and_its_outlines_are_NEUTRAL` fails
#: on it.
DARK = {
    "scene": None,
    "plate_top": "#2E2E2E", "plate_bottom": "#1F1F1F", "edge": "#0C0C0C",
    "glass": "#101010", "glass_edge": "#2C2C2C", "active": "#0A0A0A",
    "active_edge": "#333333",
}
LIGHT = {
    "scene": "#D9E5ED",
    "plate_top": "#9E9E9E", "plate_bottom": "#828282", "edge": "#2B2B2B",
    "glass": "#1A1A1A", "glass_edge": "#3A3A3A", "active": "#0A0A0A",
    "active_edge": "#4A4A4A",
}

#: Pen widths, in scene pixels -- named because the screen picture has to inset by
#: them (see `set_screen_images`), so a stroke and the inset that clears it cannot
#: drift apart.
PLATE_PEN, GLASS_PEN, ACTIVE_PEN = 2.0, 1.2, 1.0


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

    ⚠️ **It is FITTED inside the lit rectangle and inset clear of the frame, not
    stretched to its width.** Two separate ways the old width-only scale put the
    picture on top of the bezel, and each is invisible in the code:

    * the panel is 2:1 and the lit rectangle no longer has to be -- dropping the side
      bezel narrowed it -- so a width-derived height simply overflows;
    * the frame's pen is CENTRED on the rectangle's edge, so half of it lies inside,
      and a picture that exactly fills the rectangle covers that half. The screen then
      reads as bleeding over its own bezel, which is what it was reported as.

    So the scale is `min` over both axes of the INSET box and the result is centred:
    the stroke stays visible all the way round, and a future geometry of any aspect
    still cannot escape. The inset costs about a pixel of picture -- it does not move
    or resize the screen, which is a decision from the exporter.
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
        box = item.data(SCREEN_BOX)
        if not img.width() or not img.height() or box is None:
            item.setPixmap(QPixmap())
            continue
        item.setPixmap(QPixmap.fromImage(img))
        x, y, w, h = box
        w, h = max(0.0, w - ACTIVE_PEN), max(0.0, h - ACTIVE_PEN)
        scale = min(w / img.width(), h / img.height())
        item.setScale(scale)
        item.setPos(x + (box[2] - img.width() * scale) / 2.0,
                    y + (box[3] - img.height() * scale) / 2.0)


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
    pen = QPen(QColor(ink["edge"]), PLATE_PEN)
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
    glass.setPen(QPen(QColor(ink["glass_edge"]), GLASS_PEN))
    glass.setZValue(Z_DISPLAY)
    scene.addItem(glass)

    lit = rect(display.active_rect)
    active = QGraphicsRectItem(lit)
    active.setBrush(QBrush(QColor(ink["active"])))
    active.setPen(QPen(QColor(ink["active_edge"]), ACTIVE_PEN))
    active.setZValue(Z_DISPLAY)
    scene.addItem(active)

    # Always created, even with nothing to show: `set_screen_images` needs something
    # to paint into, and an empty pixmap draws nothing at all.
    shot = QGraphicsPixmapItem()
    shot.setTransformationMode(Qt.SmoothTransformation)
    shot.setData(SCREEN_SIDE, side)
    shot.setData(SCREEN_BOX, (lit.x(), lit.y(), lit.width(), lit.height()))
    shot.setPos(lit.x(), lit.y())
    shot.setZValue(Z_SCREEN)
    scene.addItem(shot)

    return [glass, active, shot]
