from PyQt5.QtGui import QPixmap, QPainter, QColor, QBrush, QTransform, QPen, QFont, QTextOption
from PyQt5.QtCore import Qt, pyqtSignal, QRectF

from PyQt5.QtWidgets import (
    QGraphicsObject, QGraphicsSimpleTextItem, QGraphicsTextItem
)

KEY_MARGIN_X = 2
KEY_MARGIN_Y = 2
KEY_RADIUS = 0.1


class RenderableKey(QGraphicsObject):
    pressed = pyqtSignal(object)

    def __init__(self, nice_name, props, scale):

        # compute reduced size if you use KEY_MARGIN
        full_w = props['w'] * scale
        full_h = props['h'] * scale
        self.w = max(2.0, full_w - 2 * KEY_MARGIN_X)
        self.h = max(2.0, full_h - 2 * KEY_MARGIN_Y)

        # create base rect; children (text) are positioned relative to this
        super().__init__()
        self.nice_name = nice_name

        # store brushes / pens
        self.bg_brush = QBrush(QColor("#353535"))
        self.display_brush = QBrush(QColor("#202020"))
        self.pen_normal = QPen(QColor("#111111"))
        self.pen_selected = QPen(QColor("#FFE100"), 2.5)
        self.pen_hover = QPen(QColor("#66C2FF"), 2.0)

        # enable interactivity
        self.setFlag(self.ItemIsSelectable, True)
        self.setFlag(self.ItemIsFocusable, True)
        self.setAcceptHoverEvents(True)

        # text label
        self.text = QGraphicsTextItem(nice_name, self)
        self.text.setFont(QFont("Arial", 10))
        self.text.setDefaultTextColor(Qt.white)
        opt = QTextOption()
        opt.setAlignment(Qt.AlignCenter)
        self.text.document().setDefaultTextOption(opt)
        self.update_text_position()

        # hover state
        self._hovered = False

        tile_size = 16               # tile resolution (adjust for crispness)
        stripe_width = 4             # width of the dark stripe in pixels
        light = QColor("#404040")   # light grey
        dark = QColor("#505050")   # dark grey

        # build tile: light background + vertical dark stripes
        pix = QPixmap(tile_size, tile_size)
        pix.fill(light)
        p = QPainter(pix)
        p.setPen(Qt.NoPen)
        # draw repeating vertical stripes; start negative to ensure seamless tiling
        for x_off in range(-tile_size, tile_size * 2, stripe_width * 2):
            p.fillRect(x_off, 0, stripe_width, tile_size, dark)
        p.end()

        # create brush and rotate the pattern 135 degrees
        self.display_attachment = QBrush(pix)
        transform = QTransform()
        transform.rotate(135)
        self.display_attachment.setTransform(transform)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.w, self.h)

    # noinspection PyTypeChecker
    def paint(self, painter, option, widget):
        # enable antialiasing for smooth rounded corners
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.boundingRect()

        # background
        painter.setBrush(self.bg_brush)
        painter.setPen(self.pen_normal)
        # default rounded rect
        radius = min(rect.width(), rect.height()) * KEY_RADIUS
        painter.drawRoundedRect(rect, radius, radius)

        painter.setBrush(self.display_brush)
        display = self.boundingRect()
        margin = 4
        inner_w = int(max(0.0, display.height() - 2.0 * margin))
        max_inner_h = max(0.0, display.height() - 2.0 * margin)

        # desired height based on ratio (width : height = 72 : 40)
        desired_h = inner_w * (40.0 / 72.0)

        # cap to available height so we never overflow the item
        h = int(min(desired_h, max_inner_h))

        x = int(display.x() + margin + (display.width()-display.height())/2)
        # anchor at top; leftover space remains at bottom
        y = int(display.y() + margin)

        # draw the rectangle (use drawRoundedRect(...) if you prefer rounded corners)
        painter.drawRoundedRect(x, y, inner_w, h, 0.05, 0.05)
        painter.setBrush(self.display_attachment)
        painter.drawRoundedRect(x, y+h, inner_w, int(h/2), 0.05, 0.05)

        # overlay when hovered
        if self._hovered and not self.isSelected():
            painter.setBrush(QBrush(QColor(100, 180, 255, 25)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, radius, radius)

        # overlay / border when selected
        if self.isSelected():

            # emphasize border (draw on top)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(self.pen_selected)
            painter.drawRoundedRect(rect, radius + 1, radius + 1)
        elif self._hovered:
            # draw hover border (when not selected)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(self.pen_hover)
            painter.drawRoundedRect(rect, radius, radius)

        # Note: don't call super().paint since we handle drawing and child text will be drawn automatically

    # Hover events to toggle hover state
    def hoverEnterEvent(self, ev):
        self._hovered = True
        self.update()  # schedule repaint
        super().hoverEnterEvent(ev)

    def hoverLeaveEvent(self, ev):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(ev)

    # Make clicking focus the item (so keyboard focus can be shown if desired)
    def mousePressEvent(self, ev):
        # ensure the item gets focus when clicked
        # noinspection PyTypeChecker
        self.setFocus(Qt.MouseFocusReason)
        self.pressed.emit(self)

        # allow default behavior (selection)
        super().mousePressEvent(ev)

    def setKeycode(self, nice_name, name, keycode, font_size_hint=None):
        self.nice_name = nice_name
        self.text.document().setPlainText(nice_name)
        if font_size_hint is not None and font_size_hint.is_integer():
            self.text.setFont(QFont("Arial", font_size_hint))
        self.update_text_position()
        self.update()

    def update_text_position(self):
        rect = self.boundingRect()
        bounding = self.text.boundingRect()
        self.text.setPos(rect.x() + (rect.width() - bounding.width())/2,
                         rect.y() + (rect.height() - bounding.height())/2 - 14)
        self.text.setTextWidth(bounding.width())
