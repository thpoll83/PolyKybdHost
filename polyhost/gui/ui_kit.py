"""Shared pieces for the dialogs: button icons, the headline, cards, grey text.

The settings dialog set the look (cards, a grey description under each title,
one button row). These helpers give the other dialogs the same parts, so a
change of style is made once.

Button icons are Material Symbols from res/icons, tinted with the tray menu's
palette (gui/get_icon.py): green accepts, grey closes or cancels, red deletes or
stops, blue copies, opens or saves. Fusion draws its own green check and red X
on some standard buttons and nothing on the others; ``set_button_icon`` and
``style_button_box`` replace that with one set, so every button in a row has an
icon.
"""

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import (QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
                             QPlainTextEdit, QVBoxLayout, QWidget)

from polyhost.gui.get_icon import get_icon

# Sizes at 100 % (96 dpi). Read them through px(), button_icon_size() and
# headline_icon_px(), which scale them with the display.
BUTTON_ICON_PX = 18
HEADLINE_ICON_PX = 36


def ui_scale():
    """The display scale Qt applies to its own sizes, 1.0 at 100 %.

    The app does not turn on Qt's high-DPI scaling, so Qt 5 draws in device
    pixels and the style scales its own metrics from the logical DPI instead:
    Fusion's button icon is 16 px at 100 % and 24 px at 150 %. A size we set
    in pixels does not follow unless it is multiplied by this, and a fixed
    18 px icon then looked smaller than the 24 px one it replaced.
    """
    from PyQt5.QtWidgets import QApplication, QStyle
    app = QApplication.instance()
    if app is None:
        return 1.0
    return max(1.0, app.style().pixelMetric(QStyle.PM_ButtonIconSize) / 16)


def px(value):
    """A size given at 100 %, in pixels at the display's scale."""
    return int(round(value * ui_scale()))


def button_icon_size():
    return QSize(px(BUTTON_ICON_PX), px(BUTTON_ICON_PX))


def headline_icon_px():
    return px(HEADLINE_ICON_PX)

# What a button does -> its icon. A dialog names the kind; the file and the
# colour follow from it. ⚠️ Every name here must exist in res/icons
# (tests/gui/icon_assets_test.py reads the get_icon literals below).
_BUTTON_ICONS = {
    "accept": lambda: get_icon("check.svg"),
    "close": lambda: get_icon("close.svg"),
    "cancel": lambda: get_icon("close.svg"),
    "delete": lambda: get_icon("delete.svg"),
    "copy": lambda: get_icon("content_copy.svg"),
    "report": lambda: get_icon("bug_report.svg"),
    "open": lambda: get_icon("open_in_new.svg"),
    "save": lambda: get_icon("download.svg"),
    "start": lambda: get_icon("play_circle.svg"),
    "stop": lambda: get_icon("stop_circle.svg"),
    "reset": lambda: get_icon("restart_alt.svg"),
    "install": lambda: get_icon("download.svg"),
    "update": lambda: get_icon("update.svg"),
    "folder": lambda: get_icon("file_open.svg"),
    "reload": lambda: get_icon("sync.svg"),
    "edit": lambda: get_icon("edit.svg"),
    "image": lambda: get_icon("image.svg"),
    "left": lambda: get_icon("arrow_back.svg"),
    "right": lambda: get_icon("arrow_forward.svg"),
}

# The icon a QDialogButtonBox standard button gets.
_STANDARD_KINDS = {
    QDialogButtonBox.Ok: "accept",
    QDialogButtonBox.Yes: "accept",
    QDialogButtonBox.Save: "save",
    QDialogButtonBox.Apply: "accept",
    QDialogButtonBox.Cancel: "cancel",
    QDialogButtonBox.No: "cancel",
    QDialogButtonBox.Close: "close",
    QDialogButtonBox.Discard: "delete",
    QDialogButtonBox.RestoreDefaults: "reset",
    QDialogButtonBox.Reset: "reset",
    QDialogButtonBox.Open: "folder",
}

# Headline kinds -> icon file.
_HEADLINE_ICONS = {
    "info": lambda: get_icon("info.svg"),
    "warning": lambda: get_icon("warning.svg"),
    "error": lambda: get_icon("error.svg"),
    "question": lambda: get_icon("help.svg"),
    "update": lambda: get_icon("update.svg"),
}


def headline_icon(kind):
    """The QIcon for a headline kind ("info", "warning", "error", "question")."""
    return _HEADLINE_ICONS[kind]()


def button_icon(kind):
    """The QIcon for a button kind ("accept", "close", "copy", ...)."""
    return _BUTTON_ICONS[kind]()


def set_button_icon(button, kind):
    """Give ``button`` the icon for ``kind`` and return the button."""
    button.setIcon(button_icon(kind))
    button.setIconSize(button_icon_size())
    return button


def style_button_box(box, kinds=None):
    """Give every button of a QDialogButtonBox an icon from the shared set.

    Standard buttons get theirs by role; ``kinds`` maps a custom button (as
    returned by ``box.addButton(text, role)``) to a kind. A custom button with
    no kind is left without an icon, which the dialog tests catch.
    """
    for std, kind in _STANDARD_KINDS.items():
        btn = box.button(std)
        if btn is not None:
            set_button_icon(btn, kind)
    for btn, kind in (kinds or {}).items():
        set_button_icon(btn, kind)
    return box


def muted(label):
    """Grey a label's text the way the settings dialog greys its descriptions."""
    pal = label.palette()
    pal.setColor(QPalette.WindowText, pal.color(QPalette.Disabled, QPalette.WindowText))
    label.setPalette(pal)
    return label


class WrapLabel(QLabel):
    """A word-wrapped label that is always tall enough for its text.

    A layout does not ask a label for its height-for-width once the label sits
    inside a frame or below the top level, so a plain wrapped label inside a
    card was squeezed and its lines overlapped. This one sets its minimum
    height from its width on every resize (the update dialog's _WrapLabel,
    shared).
    """

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)

    def resizeEvent(self, event):  # noqa: N802 - Qt name
        super().resizeEvent(event)
        old = self.minimumHeight()
        self.setMinimumHeight(0)
        h = self.heightForWidth(self.width())
        self.setMinimumHeight(h if h > 0 else old)


class StatusLabel(QLabel):
    """A grey one-line status ("Copied to the clipboard.") that takes no room
    while it is empty, so a dialog does not open with a blank line above its
    buttons."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        muted(self)
        self.setWordWrap(True)
        self.setVisible(bool(text))

    def setText(self, text):  # noqa: N802 - Qt name
        super().setText(text)
        self.setVisible(bool(text))


class Headline(QWidget):
    """An icon, a bold title and an optional grey line under it.

    Replaces Qt's message-box pixmaps (the yellow triangle, the "?" bubble),
    which belong to an older look than the rest of the app. ``title`` and
    ``text`` stay readable and settable through ``set_title`` / ``set_text``.
    """

    def __init__(self, title="", text="", kind="info", parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 4)
        row.setSpacing(12)
        self.icon = QLabel(self)
        size = headline_icon_px()
        self.icon.setPixmap(_HEADLINE_ICONS[kind]().pixmap(size, size))
        self.icon.setFixedSize(size, size)
        row.addWidget(self.icon, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = QLabel(title, self)
        self.title.setWordWrap(True)
        self.title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        font = self.title.font()
        font.setPointSizeF(font.pointSizeF() * 1.15)
        font.setBold(True)
        self.title.setFont(font)
        col.addWidget(self.title)
        self.text = muted(QLabel(text, self))
        self.text.setWordWrap(True)
        self.text.setVisible(bool(text))
        col.addWidget(self.text)
        row.addLayout(col, 1)

    def set_title(self, title):
        self.title.setText(title)

    def set_text(self, text):
        self.text.setText(text)
        self.text.setVisible(bool(text))


# The card look of the settings dialog. Every colour is a palette role, so the
# light and the dark theme both apply.
CARD_STYLE = """
QFrame#uiCard {
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 8px;
}
"""


def card(parent=None):
    """A rounded frame on the base colour, with a vertical layout inside.

    Returns ``(frame, layout)``. The caller adds ``CARD_STYLE`` to the dialog's
    stylesheet once.
    """
    frame = QFrame(parent)
    frame.setObjectName("uiCard")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(6)
    return frame, lay


def fit_text_lines(edit, min_lines=3, max_lines=14):
    """Size a read-only QPlainTextEdit to its text, between two line counts.

    A details box that opens at a fixed 300 px is mostly empty for a two-line
    message; one that grows without a cap pushes the buttons off screen.
    """
    lines = max(1, edit.document().lineCount())
    if isinstance(edit, QPlainTextEdit) and edit.lineWrapMode() != QPlainTextEdit.NoWrap:
        # Wrapped lines are counted as blocks; a rough width estimate keeps
        # a long line from being counted as one. Before the dialog is shown
        # the viewport reports Qt's default (~100 px), so the window's own
        # width, less the dialog margins and the frame, stands in for it.
        width = edit.viewport().width()
        if not edit.isVisible():
            win = edit.window()
            width = max(width, max(win.width(), win.minimumWidth()) - 40)
        width = max(width, 400)
        chars = max(20, width // max(1, edit.fontMetrics().averageCharWidth()))
        lines = sum(max(1, -(-len(b) // chars)) for b in edit.toPlainText().split("\n"))
    shown = min(max(lines, min_lines), max_lines)
    frame = edit.frameWidth() * 2 + int(edit.document().documentMargin() * 2) + 6
    edit.setFixedHeight(edit.fontMetrics().lineSpacing() * shown + frame)
    return edit
