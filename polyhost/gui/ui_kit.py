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

import logging

from PyQt5.QtCore import QEvent, QObject, QSize, Qt
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import (QBoxLayout, QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
                             QLabel, QLayout, QMainWindow, QPlainTextEdit, QPushButton,
                             QVBoxLayout, QWidget)

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


def fit_height(dialog):
    """Grow `dialog` to the height its wrapped text needs, and keep it from
    being made smaller.

    A dialog opens, or adjustSize() sizes it, at a height computed before its
    WrapLabels measured their text, and minimumSizeHint() keeps that old
    value. A long translated text (German) then ran under the widget below it.
    The layout's height for the real width is right once the layouts are
    invalidated. Call it after the dialog is shown, through
    QTimer.singleShot(0, ...), when the labels have their width.
    """
    lay = dialog.layout()
    if lay is None:
        return
    for child in dialog.findChildren(QLayout):
        child.invalidate()
    lay.invalidate()
    need = lay.totalHeightForWidth(dialog.width()) if lay.hasHeightForWidth() else -1
    if need <= 0:
        return
    dialog.setMinimumHeight(need)
    if need > dialog.height():
        dialog.resize(dialog.width(), need)


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


# ── Matching button widths ────────────────────────────────────────────────────

def _button_groups(layout):
    """The runs of text buttons in a row, split where a stretch or another
    widget stands between them. A fixed gap does not split a run."""
    groups, run = [], []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        w = item.widget()
        if w is not None and w.isHidden():
            continue
        if (isinstance(w, QPushButton)
                and len(w.text().replace("&", "").strip()) > 1):
            run.append(w)
            continue
        if isinstance(w, QDialogButtonBox):
            # A Close kept in its own button box beside the action buttons
            # (report a problem, log bundle) belongs to the same row.
            run.extend(b for b in w.buttons()
                       if not b.isHidden() and len(b.text().replace("&", "").strip()) > 1)
            continue
        spacer = item.spacerItem()
        if spacer is not None and not spacer.expandingDirections() & Qt.Horizontal:
            continue    # a fixed gap, such as QDialogButtonBox puts between roles
        if run:
            groups.append(run)
        run = []
    if run:
        groups.append(run)
    return [g for g in groups if len(g) > 1]


def match_button_widths(window):
    """Give buttons that sit next to each other the width of the widest one.

    Each horizontal layout (a QDialogButtonBox has one too) is a row. A stretch
    or any other widget splits a row, so a Close set apart from the actions
    keeps its own width. A button whose text is one character (the macro
    editor's arrows) is left out. The window widens when the row no longer fits.
    """
    # A button in a QDialogButtonBox beside other buttons is in two groups:
    # the box's own row and the outer row. Merge groups that share a button,
    # so each button gets one width; two different ones would be set in turn
    # on every pass, and each would post a new layout request.
    merged = []
    for layout in window.findChildren(QBoxLayout):
        if layout.direction() not in (QBoxLayout.LeftToRight, QBoxLayout.RightToLeft):
            continue
        for group in _button_groups(layout):
            members = set(group)
            for other in [m for m in merged if m & members]:
                members |= other
                merged.remove(other)
            merged.append(members)
    for group in merged:
        for w in group:
            w.ensurePolished()      # the style sheet's padding is in the hint
        widest = max(max(w.sizeHint().width(), w.minimumSizeHint().width())
                     for w in group)
        for w in group:
            if w.minimumWidth() != widest:   # unchanged: no new layout request
                w.setMinimumWidth(widest)
    # A row can also grow after the dialog opened (the log bundle's "Show in
    # Folder" appears after a save). Widen the window to what its layout needs,
    # or Qt squeezes the buttons into each other.
    if window.layout() is not None:
        window.layout().activate()
        need = window.minimumSizeHint().width()
        if need > window.width() and window.maximumWidth() >= need:
            window.resize(need, window.height())


class _ButtonWidthFilter(QObject):
    """Runs match_button_widths when a dialog or main window is shown, and
    again when its layout changes while it is open (a button shown or hidden,
    a text changed)."""

    _busy = False

    def eventFilter(self, obj, event):  # noqa: N802 - Qt name
        kind = event.type()
        if (kind == QEvent.Show
                or (kind == QEvent.LayoutRequest and obj.isWidgetType() and obj.isVisible())) \
                and isinstance(obj, (QDialog, QMainWindow)) and not self._busy:
            self._busy = True     # the pass itself can post a layout request
            try:
                match_button_widths(obj)
            except Exception:   # a cosmetic pass must never break a dialog
                logging.getLogger("PolyHost").debug("match_button_widths failed", exc_info=True)
            finally:
                self._busy = False
        return False


def install_button_width_matching(app):
    """Match button widths in every dialog the app shows (once per app).

    apply_theme() calls this on every tray menu open; the filter is kept on
    the app object, so it is installed once and not garbage-collected.
    """
    if getattr(app, "_polyhost_button_widths", None) is None:
        app._polyhost_button_widths = _ButtonWidthFilter()
        app.installEventFilter(app._polyhost_button_widths)
