from PyQt5.QtGui import QPixmap, QPainter, QPainterPath, QColor, QBrush, QTransform, QPen, QFont, QTextOption
from PyQt5.QtCore import QPointF, QRect, Qt, pyqtSignal, QRectF

from PyQt5.QtWidgets import (
    QGraphicsObject, QGraphicsTextItem
)

KEY_MARGIN_X = 2
KEY_MARGIN_Y = 2
KEY_RADIUS = 0.1
BADGE_BOTTOM_GAP = 20  # px from tile bottom to the badge's top edge
LABEL_ONLY_NUDGE = 14  # px the label sits above the tile centre (no badge beside it)


def key_transform(info, minx, miny, scale) -> QTransform:
    """Where a KLE key sits in the scene: its position relative to the board's
    top-left, rotated about the KLE rotation origin (rx, ry) when it has one --
    the split72 thumb keys run up to 20 degrees off axis."""
    x, y = info["x"] - minx, info["y"] - miny
    r = info.get("r", 0)
    transform = QTransform()
    if r:
        rx, ry = info.get("rx", 0) - minx, info.get("ry", 0) - miny
        transform.translate(rx * scale, ry * scale)
        transform.rotate(r)
        transform.translate((x - rx) * scale, (y - ry) * scale)
    else:
        transform.translate(x * scale, y * scale)
    return transform


class RenderableKey(QGraphicsObject):
    pressed = pyqtSignal(object)

    def __init__(self, nice_name, props, scale, matrix_index=None):
        self.matrix_index = matrix_index

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

        # text label (base / tap keycode, drawn prominently in the centre)
        self.text = QGraphicsTextItem(nice_name, self)
        self.text.setFont(QFont("Arial", 10))
        self.text.setDefaultTextColor(Qt.white)
        opt = QTextOption()
        opt.setAlignment(Qt.AlignCenter)
        self.text.document().setDefaultTextOption(opt)

        # behaviour badge (held mod / target layer / one-shot …), drawn small
        # near the bottom. Empty + hidden for plain keys.
        self.badge = QGraphicsTextItem("", self)
        self.badge.setFont(QFont("Arial", 8, QFont.Bold))
        self.badge.setDefaultTextColor(QColor("#FFCC44"))
        badge_opt = QTextOption()
        badge_opt.setAlignment(Qt.AlignCenter)
        self.badge.document().setDefaultTextOption(badge_opt)
        self.badge.setVisible(False)

        self._keycap = None      # a rendered macro keycap, drawn in the display rect
        # On the rendered photo (Real mode, see real_board.py) the key is moved so its
        # display rect lands on the photographed OLED, and draws nothing of its own
        # but that panel's picture: the photo already shows the cap, switch and plate.
        self._photo = False
        self._label_only = False
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

    def display_rect(self) -> QRect:
        """The 72:40 panel rect inside the tile, in item coordinates.

        One place for it, because two things depend on it agreeing exactly: the
        tile paints the keycap there, and Real mode on the photo maps this rect
        onto the photographed OLED.
        """
        display = self.boundingRect()
        margin = 4
        inner_w = int(max(0.0, display.height() - 2.0 * margin))
        max_inner_h = max(0.0, display.height() - 2.0 * margin)
        # desired height based on ratio (width : height = 72 : 40), capped to the
        # available height so it never overflows the item
        h = int(min(inner_w * (40.0 / 72.0), max_inner_h))
        x = int(display.x() + margin + (display.width() - display.height()) / 2)
        # anchor at top; leftover space remains at bottom
        y = int(display.y() + margin)
        return QRect(x, y, inner_w, h)

    def set_photo_mode(self, on: bool) -> None:
        """Draw only the panel picture (and hover / selection), for the photo."""
        self.prepareGeometryChange()
        self._photo = bool(on)
        self._sync_labels()
        self.update()

    def set_label_only(self, on: bool) -> None:
        """Draw only the key's legend, no tile, for a key the photo shows no display for.

        On the photo the two keys without a display sit over the expansion-port
        lids; a tile there would cover the lid with a box that is not on the board.
        With a keycap preview the legend is that picture, blended onto the lid like
        a lit panel, so it reads like the displays around it; without one it is the
        text label.
        """
        self.prepareGeometryChange()
        self._label_only = bool(on)
        self._sync_labels()
        self.update_text_position()
        self.update()

    def label_anchor(self) -> QPointF:
        """The label's centre in item coordinates, fixed whatever the text, for a
        label-only key: `update_text_position` centres it there."""
        r = self.boundingRect()
        return QPointF(r.center().x(), r.center().y() - LABEL_ONLY_NUDGE)

    def _sync_labels(self):
        # The child labels sit at tile positions. On the photo the tile around
        # the panel covers caps and plate, so the badge there would float over
        # the picture: it is hidden, and the panel alone carries the key.
        self.text.setVisible(self._keycap is None and self._label_shown())
        self.badge.setVisible(bool(self.badge.toPlainText())
                              and not (self._photo or self._label_only))

    def _label_shown(self) -> bool:
        """Whether the label is drawn. A label-only key (an expansion-port lid on
        the photo) shows its legend only while hovered or selected: the lid is
        bare on the board, so a legend there all the time puts something on the
        photo that the keyboard does not have. Its hit area stays, so hovering the
        lid still finds it."""
        return not self._label_only or self._hovered or self.isSelected()

    def _label_rect(self) -> QRectF:
        if self._keycap is not None:
            # the legend picture, display-sized and centred where the label sits
            r = QRectF(self.display_rect())
            r.moveCenter(self.label_anchor())
            return r.adjusted(-3, -3, 3, 3)
        return self.text.mapRectToParent(self.text.boundingRect()).adjusted(-3, -3, 3, 3)

    def shape(self) -> QPainterPath:
        # On the photo only the panel is drawn, and the tile around it would sit
        # over the neighbouring keys' caps: hover and clicks there must not land
        # on this key. The ring margin keeps the selection ring itself clickable.
        path = QPainterPath()
        if self._photo:
            path.addRect(QRectF(self.display_rect()).adjusted(-3, -3, 3, 3))
        elif self._label_only:
            path.addRect(self._label_rect())
        else:
            path.addRect(self.boundingRect())
        return path

    def _paint_photo(self, painter):
        r = self.display_rect()
        if self._keycap is not None and r.width() > 0 and r.height() > 0:
            painter.save()
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(r, self._keycap)
            painter.restore()
        if self.isSelected() or self._hovered:
            ring = QRectF(r).adjusted(-3, -3, 3, 3)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(self.pen_selected if self.isSelected() else self.pen_hover)
            painter.drawRoundedRect(ring, 3, 3)

    # noinspection PyTypeChecker
    def paint(self, painter, option, widget):
        # enable antialiasing for smooth rounded corners
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.boundingRect()
        if self._photo:
            self._paint_photo(painter)
            return
        if self._label_only:
            if not self._label_shown():
                return
            if self._keycap is not None:
                # The same simulated panel the displays show, but with no panel:
                # LIGHTEN keeps the lit pixels and their glow and drops the panel's
                # dark ground (darker than the lid), so the legend reads as lit on
                # the lid rather than as a box on it. SCREEN lightened the ground
                # too and left a faint rectangle.
                r = self._label_rect().adjusted(3, 3, -3, -3)
                painter.save()
                painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                painter.setCompositionMode(QPainter.CompositionMode_Lighten)
                painter.drawPixmap(r, self._keycap, QRectF(self._keycap.rect()))
                painter.restore()
            if self.isSelected() or self._hovered:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(self.pen_selected if self.isSelected() else self.pen_hover)
                painter.drawRoundedRect(self._label_rect(), 3, 3)
            return

        # background
        painter.setBrush(self.bg_brush)
        painter.setPen(self.pen_normal)
        # default rounded rect
        radius = min(rect.width(), rect.height()) * KEY_RADIUS
        painter.drawRoundedRect(rect, radius, radius)

        painter.setBrush(self.display_brush)
        panel = self.display_rect()
        x, y, inner_w, h = panel.x(), panel.y(), panel.width(), panel.height()

        # draw the rectangle (use drawRoundedRect(...) if you prefer rounded corners)
        painter.drawRoundedRect(x, y, inner_w, h, 0.05, 0.05)
        # A macro key paints its real keycap into that same rect. The tile already
        # reserved a 72:40 box for a mock panel, so the picture goes exactly where the
        # placeholder was -- no layout change, and a non-macro key is untouched.
        if self._keycap is not None and inner_w > 0 and h > 0:
            # ⚠️ Smoothed, because this is always a DOWNSCALE: a 72x40 keycap lands in
            # a tile roughly 50px wide, and Qt's default nearest-neighbour drops whole
            # pixel rows -- enough to break a small glyph's stems, so the editor showed
            # a mangled letter the keyboard draws cleanly. It matters more again for
            # the OLED simulation, which is rendered several times larger still.
            painter.save()
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(QRect(x, y, inner_w, h), self._keycap)
            painter.restore()
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
        self._sync_labels()     # a label-only key's text label shows on hover
        self.update()  # schedule repaint
        super().hoverEnterEvent(ev)

    def hoverLeaveEvent(self, ev):
        self._hovered = False
        self._sync_labels()
        self.update()
        super().hoverLeaveEvent(ev)

    def itemChange(self, change, value):
        if change == self.ItemSelectedHasChanged:
            self._sync_labels()     # ... and while selected
        return super().itemChange(change, value)

    # Make clicking focus the item (so keyboard focus can be shown if desired)
    def mousePressEvent(self, ev):
        # ensure the item gets focus when clicked
        # noinspection PyTypeChecker
        self.setFocus(Qt.MouseFocusReason)
        self.pressed.emit(self)

        # allow default behavior (selection)
        super().mousePressEvent(ev)

    def setKeycode(self, nice_name, name, keycode, font_size_hint=None):
        # Legacy single-line setter (kept for compatibility). Prefer set_display.
        self.set_display(nice_name, "", None, font_size_hint)

    def set_keycap(self, pixmap):
        """Show a rendered keycap in the display rect instead of the placeholder fill.

        The centre TEXT is hidden while one is set: the keycap already carries the
        caption, and `MACRO(3)` drawn over it is both redundant and unreadable. Pass
        None to go back to the plain tile -- every reassignment must do that, or a key
        that stops being a macro keeps the old picture.
        """
        if self._label_only:
            self.prepareGeometryChange()        # the hit area follows the picture
        self._keycap = pixmap
        self._sync_labels()
        self.update()

    def set_display(self, main_text, badge_text="", badge_color=None, font_size_hint=None):
        """Update the tile to show a base/tap label plus an optional behaviour badge."""
        self.nice_name = main_text
        self.text.document().setPlainText(main_text or "")
        if font_size_hint is not None and isinstance(font_size_hint, (int, float)):
            self.text.setFont(QFont("Arial", int(font_size_hint)))

        has_badge = bool(badge_text)
        self.badge.document().setPlainText(badge_text or "")
        self.badge.setVisible(has_badge)    # for the layout below; _sync_labels settles it
        if has_badge and badge_color:
            self.badge.setDefaultTextColor(QColor(badge_color))

        self.update_text_position()
        self._sync_labels()
        self.update()

    def update_text_position(self):
        rect = self.boundingRect()
        bounding = self.text.boundingRect()
        # Nudge the main label up a little when a badge is shown so the two
        # lines sit either side of the tile's display area.
        y_nudge = LABEL_ONLY_NUDGE if self._label_only else 18 if self.badge.isVisible() else 14
        self.text.setPos(rect.x() + (rect.width() - bounding.width())/2,
                         rect.y() + (rect.height() - bounding.height())/2 - y_nudge)
        self.text.setTextWidth(bounding.width())

        badge_bounds = self.badge.boundingRect()
        # Anchor the badge a fixed distance from the tile bottom (not by its own
        # height) so ASCII tags ("MO", "L2") and the taller Unicode modifier
        # glyphs (⇧⌃⌥⌘) all sit on exactly the same line regardless of colour.
        self.badge.setPos(rect.x() + (rect.width() - badge_bounds.width())/2,
                          rect.y() + rect.height() - BADGE_BOTTOM_GAP)
        self.badge.setTextWidth(badge_bounds.width())
