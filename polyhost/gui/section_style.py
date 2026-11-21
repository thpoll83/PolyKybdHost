"""The coloured sections of the Settings, Integrations and Tutorials dialogs.

A dialog with a sidebar gives each sidebar entry a colour (gui/section_colors.py).
The entry gets a stripe of the colour, and a tint of it when selected or under the
mouse. The section it opens gets the same tint behind its content and its title on
a band of the full colour, so the entry and the section read as one.

* :func:`style_nav` sets up a ``QListWidget`` as such a sidebar, and
  :func:`add_nav_item` adds an entry with its colour.
* :class:`ColorSection` is a section: the title band, a layout for controls
  on its right end (``head_layout``), and a body layout (``body_layout``) for
  the content.
* :func:`dialog_is_dark` tells which of the two colour schemes a widget needs.
"""
from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPalette
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidgetItem, QStyle, QStyledItemDelegate,
                             QVBoxLayout, QWidget)

from polyhost.gui import section_colors
from polyhost.gui.theme import is_dark
from polyhost.gui.ui_kit import px

# The width the sidebar is measured with when the view has no width yet.
_FALLBACK_WIDTH = 210


def dialog_is_dark(widget):
    """Whether ``widget`` shows the dark theme (the dark colour scheme)."""
    return is_dark(widget.palette())


class NavDelegate(QStyledItemDelegate):
    """A sidebar entry: a stripe in its section's colour (the item's
    ``Qt.UserRole``), and a tint of that colour when it is selected (stronger)
    or under the mouse (weaker). The text stays in the palette's text colour;
    the selected entry is bold."""

    PAD_X, PAD_Y, STRIPE = 14, 7, 4

    def _text_rect(self, rect):
        return rect.adjusted(px(self.PAD_X), px(self.PAD_Y), -px(6), -px(self.PAD_Y))

    def paint(self, painter, option, index):
        color = QColor(index.data(Qt.UserRole) or option.palette.highlight().color())
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver)
        rect = option.rect.adjusted(0, px(1), 0, -px(1))
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        if selected or hover:
            fill = QColor(color)
            fill.setAlpha(section_colors.TINT_ALPHA if selected else section_colors.HOVER_ALPHA)
            painter.setBrush(fill)
            painter.drawRoundedRect(QRectF(rect), px(6), px(6))
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(rect.left() + px(3), rect.top() + px(6), px(self.STRIPE),
                                       rect.height() - px(12)), px(2), px(2))
        font = QFont(option.font)
        font.setBold(selected)
        painter.setFont(font)
        painter.setPen(option.palette.color(QPalette.Text))
        painter.drawText(self._text_rect(rect), Qt.AlignVCenter | Qt.TextWordWrap,
                         index.data(Qt.DisplayRole) or "")
        painter.restore()

    def sizeHint(self, option, index):
        font = QFont(option.font)
        font.setBold(True)     # measure the widest form, so selecting never re-wraps
        view = self.parent()
        width = (view.viewport().width() if view is not None and view.viewport().width() > 0
                 else px(_FALLBACK_WIDTH)) - px(self.PAD_X) - px(6)
        text = QFontMetrics(font).boundingRect(0, 0, max(width, 10), 10_000, Qt.TextWordWrap,
                                               index.data(Qt.DisplayRole) or "")
        return QSize(width, text.height() + 2 * px(self.PAD_Y) + px(2))


def style_nav(nav):
    """Make ``nav`` (a QListWidget) a coloured sidebar."""
    nav.setItemDelegate(NavDelegate(nav))
    nav.setMouseTracking(True)


def add_nav_item(nav, title, color):
    """Add a sidebar entry ``title`` in ``color`` (a hex string, or None for
    the palette's highlight)."""
    item = QListWidgetItem(title)
    item.setData(Qt.UserRole, color)
    nav.addItem(item)
    return item


class ColorSection(QFrame):
    """A section in its colour: a light tint behind its content and its title
    on a band of the full colour. Add the content to ``body_layout``."""

    def __init__(self, title, color=None, parent=None):
        super().__init__(parent)
        self.title = title
        self.color = color
        self.setObjectName("colorSection")
        radius = px(10)
        if color:
            self.setStyleSheet(
                f"QFrame#colorSection {{ border: none; "
                f"border-radius: {radius}px; background: {section_colors.tint(color)}; }}"
                f"QLabel#colorSectionTitle {{ background: {color}; "
                f"color: {section_colors.title_ink(color)}; "
                f"font-size: 15pt; font-weight: 600; "
                f"border-top-left-radius: {radius}px; "
                f"border-top-right-radius: {radius}px; "
                f"padding: {px(6)}px {px(14)}px; }}")
        outer = QVBoxLayout(self)
        # The band spans the section's full width, from its top edge.
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.head = QLabel(title)
        self.head.setObjectName("colorSectionTitle")
        if not color:
            self.head.setContentsMargins(px(14), px(6), px(14), 0)
            font = self.head.font()
            font.setPointSizeF(15)
            font.setBold(True)
            self.head.setFont(font)
        outer.addWidget(self.head)
        # Controls on the right end of the title band (Settings: the
        # Advanced switch). The title text stays the label's own.
        self.head_layout = QHBoxLayout(self.head)
        self.head_layout.setContentsMargins(0, 0, px(10), 0)
        self.head_layout.addStretch(1)
        body = QWidget()
        body.setAttribute(Qt.WA_TranslucentBackground)
        outer.addWidget(body)
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(px(12), px(12), px(12), px(12))
        self.body_layout.setSpacing(14)

    def set_title(self, title):
        self.title = title
        self.head.setText(title)


def accent_checkbox(box, color):
    """A checkbox whose box is filled with ``color`` while it is checked, with the
    tick in the matching ink (Fusion draws the box in Base and the tick in Text).
    Unchecked, it keeps the palette's look."""
    if not color:
        return
    base_pal = QPalette(box.palette())

    def paint(checked):
        pal = QPalette(base_pal)
        if checked:
            for group in (QPalette.Active, QPalette.Inactive):
                pal.setColor(group, QPalette.Base, QColor(color))
                pal.setColor(group, QPalette.Text, QColor(section_colors.title_ink(color)))
        box.setPalette(pal)
    paint(box.isChecked())
    # noinspection PyUnresolvedReferences
    box.toggled.connect(paint)


def accent_button_style(color):
    """The style sheet of a main action button in ``color`` (Install, Start)."""
    ink = section_colors.title_ink(color)
    return (f"QPushButton {{ background: {color}; color: {ink}; border: 1px solid {color}; "
            f"border-radius: {px(6)}px; padding: {px(4)}px {px(14)}px; font-weight: 600; }}"
            f"QPushButton:hover {{ border: 2px solid {ink}; }}"
            f"QPushButton:disabled {{ background: {section_colors.tint(color)}; "
            f"color: palette(mid); border: 1px solid {section_colors.tint(color)}; }}")


def mark_accent_button(button):
    """Mark ``button`` as its section's main action; ColorSection.adopt colours it."""
    button.setProperty("sectionAccent", True)
    return button


def adopt(widget, color):
    """Colour the controls under ``widget`` with ``color``: checkboxes (not the
    Settings switches, which take the colour themselves) and the buttons marked
    with :func:`mark_accent_button`."""
    if not color:
        return
    from PyQt5.QtWidgets import QCheckBox, QPushButton
    for box in widget.findChildren(QCheckBox):
        if type(box) is QCheckBox and not box.property("sectionAccentDone"):
            box.setProperty("sectionAccentDone", True)
            accent_checkbox(box, color)
    for button in widget.findChildren(QPushButton):
        if button.property("sectionAccent"):
            button.setStyleSheet(accent_button_style(color))
