from PyQt5.QtCore import QEvent, QSize
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QPushButton, QSizePolicy, QStyle, QStyleOptionButton

from polyhost.gui.layout_dialog.text_fit import fit_pixel_size

BUTTON_SIDE = 72
MAX_PX = 16     # the "ideal" size: 12 pt at 96 dpi
MIN_PX = 6      # legibility limit
INSET = 2       # keep the text off the button's bevel
# The app theme pads every QPushButton 12 px left and right (gui/theme.py), which
# left a 72 px tile ~46 px for its caption: ACCELERATION did not fit even at the
# 6 px floor. A browser tile is a square label, not a dialog button, so it keeps the
# theme's colours and border and takes a small padding of its own.
TILE_STYLE = "QPushButton { padding: 2px; }"


class KeycodeBrowserButton(QPushButton):

    def __init__(self, text, keycode, parent=None):
        super().__init__(text, parent)
        self.current_size = MAX_PX

        self.setToolTip(f"<b>{keycode}</b>")
        self.setStyleSheet(TILE_STYLE)

        # Set a fixed square size
        self.setFixedSize(BUTTON_SIDE, BUTTON_SIDE)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.adjust_font_size()

    def sizeHint(self):
        return QSize(BUTTON_SIDE, BUTTON_SIDE)

    def minimumSizeHint(self):
        return QSize(BUTTON_SIDE, BUTTON_SIDE)

    def get_font_size(self):
        """The label's pixel size."""
        return self.current_size

    def label_rect(self):
        """Where the style draws the label: the button minus its frame and margin."""
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        r = self.style().subElementRect(QStyle.SE_PushButtonContents, opt, self)
        return r.adjusted(INSET, INSET, -INSET, -INSET)

    def adjust_font_size(self):
        """Largest pixel size at which every line of the caption fits the label rect."""
        text = self.text()
        if not text:
            return
        # A stylesheet (the app theme's padding, TILE_STYLE) applies at polish time,
        # which comes after __init__: unpolished, the label rect is the theme's
        # 42 px instead of 62, and the size picked for it is wrong.
        self.ensurePolished()
        r = self.label_rect()
        font = QFont(self.font())
        self.current_size = fit_pixel_size(font, text, r.width(), r.height(), MAX_PX, MIN_PX)
        font.setPixelSize(self.current_size)
        self.setFont(font)

    def changeEvent(self, event):
        # The tray re-applies the theme on every menu open; refit when the style
        # changes. (setFont raises FontChange, not StyleChange, so this cannot loop.)
        super().changeEvent(event)
        if event.type() == QEvent.StyleChange:
            self.adjust_font_size()

    # Re-run adjustment if text is changed via code
    def setText(self, text):
        super().setText(text)
        self.adjust_font_size()
