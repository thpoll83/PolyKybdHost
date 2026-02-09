from PyQt5.QtCore import QSize
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import QPushButton, QSizePolicy


class KeycodeBrowserButton(QPushButton):

    def __init__(self, text, keycode, parent=None):
        super().__init__(text, parent)
        self.max_font_size = 12  # The "ideal" size
        self.min_font_size = 7 # Legibility limit
        self.current_size = self.min_font_size

        self.setToolTip(f"<b>{keycode}</b>")

        # Set a fixed square size
        self.setFixedSize(72, 72)
        self.setMinimumSize(72, 72)
        self.setMaximumSize(72, 72)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.adjust_font_size()

    def sizeHint(self):
        s = super().sizeHint()
        side = max(s.width(), s.height())
        return QSize(side, side)

    def minimumSizeHint(self):
        side = max(
            super().minimumSizeHint().width(),
            super().minimumSizeHint().height()
        )
        return QSize(side, side)


    def get_text_width(self, font, text):
        """Helper to handle Qt 5.11+ vs older versions"""
        metrics = QFontMetrics(font)
        if hasattr(metrics, 'horizontalAdvance'):
            return metrics.horizontalAdvance(text)
        return metrics.width(text)

    def get_font_size(self):
        return self.current_size

    def adjust_font_size(self):
        text = self.text()
        if not text:
            return

        self.current_size = self.max_font_size
        font = self.font()

        # Buffer: Subtract padding so text doesn't touch the button border
        padding = 4
        available_width = self.width() - padding

        # Loop to shrink font until it fits
        while self.current_size > self.min_font_size:
            font.setPointSize(self.current_size)
            if self.get_text_width(font, text) <= available_width:
                break
            self.current_size -= 1

        self.setFont(font)

    # Re-run adjustment if text is changed via code
    def setText(self, text):
        super().setText(text)
        self.adjust_font_size()