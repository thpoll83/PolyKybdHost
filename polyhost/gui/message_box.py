"""The app's message box: Qt's QMessageBox calls, drawn like the other dialogs.

QMessageBox shows the platform's old pixmaps (the yellow triangle, the "?"
bubble) and, under Fusion, a green check or a red X on some buttons only. This
dialog has the ui_kit icon in the tray palette and an icon on every button.

The module functions take the arguments of QMessageBox's static functions and
return the same ``QMessageBox.StandardButton`` codes, so a call site changes
only its prefix: ``QMessageBox.question(...)`` becomes
``message_box.question(...)``. QMessageBox and QDialogButtonBox share the
numeric values of their standard buttons and of their button roles, so either
enum may be passed.

⚠️ A test that answers a box patches ``polyhost.gui.message_box.question``
(or ``information``, ``warning``, ``critical``). Patching
``QMessageBox.question`` no longer reaches these calls, and the dialog then
waits for a click that never comes.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QHBoxLayout,
                             QLabel, QMessageBox, QScrollArea, QVBoxLayout, QWidget)

from polyhost.gui import ui_kit

# The dialog's width at 100 % (ui_kit.px scales it). Qt's own box grows to
# about this for a paragraph.
WIDTH = 460

# QMessageBox icon -> ui_kit headline kind.
_KINDS = {
    QMessageBox.Information: "info",
    QMessageBox.Warning: "warning",
    QMessageBox.Critical: "error",
    QMessageBox.Question: "question",
}

# The button that answers Escape or the window's close button, in the order
# QMessageBox picks it.
_ESCAPE_ORDER = (QMessageBox.Cancel, QMessageBox.No, QMessageBox.Close,
                 QMessageBox.Abort, QMessageBox.Ok)

# Buttons that count as "yes" when the dialog is accepted without a click on
# a particular button (a test, or Enter with nothing focused).
_ACCEPT_ORDER = (QMessageBox.Yes, QMessageBox.Ok, QMessageBox.Save,
                 QMessageBox.Open, QMessageBox.Apply)


class MessageBox(QDialog):
    """An icon, the text and a row of buttons.

    ``text`` is the message. With ``informative`` set, ``text`` is drawn bold
    as a headline and ``informative`` under it, like QMessageBox's
    ``setInformativeText``. ``exec_()`` returns the code of the standard
    button that was clicked; for a button added with ``add_button`` read
    ``clicked_button()``.
    """

    def __init__(self, icon, title, text, buttons=QMessageBox.Ok, parent=None,
                 informative="", default=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._buttons = int(buttons)
        self._clicked = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(ui_kit.px(16), ui_kit.px(16), ui_kit.px(16), ui_kit.px(12))
        outer.setSpacing(ui_kit.px(12))

        row = QHBoxLayout()
        row.setSpacing(ui_kit.px(12))
        self.icon = QLabel(self)
        kind = _KINDS.get(icon, icon if isinstance(icon, str) else "info")
        px = ui_kit.headline_icon_px()
        self.icon.setPixmap(ui_kit.headline_icon(kind).pixmap(px, px))
        self.icon.setFixedSize(px, px)
        row.addWidget(self.icon, 0, Qt.AlignTop)

        body = QWidget(self)
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(ui_kit.px(6))
        self.text = self._label(text, body)
        if informative:
            font = self.text.font()
            font.setBold(True)
            self.text.setFont(font)
        col.addWidget(self.text)
        self.informative = self._label(informative, body)
        self.informative.setVisible(bool(informative))
        col.addWidget(self.informative)
        col.addStretch(1)
        self._body = body
        self._row = row
        row.addWidget(body, 1)
        outer.addLayout(row, 1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButtons(self._buttons), self)
        self.button_box.clicked.connect(self._on_clicked)
        ui_kit.style_button_box(self.button_box)
        outer.addWidget(self.button_box)
        self._outer = outer

        target = default
        if target is None or not (self._buttons & int(target)):
            target = next((b for b in _ACCEPT_ORDER if self._buttons & b), None)
        if target is not None:
            self.set_default(self.button_box.button(QDialogButtonBox.StandardButton(int(target))))

    @staticmethod
    def _label(text, parent):
        label = QLabel(text, parent)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        label.setOpenExternalLinks(True)
        return label

    def add_button(self, text, role, kind=None):
        """Add a button with its own text, as QMessageBox.addButton does."""
        btn = self.button_box.addButton(text, QDialogButtonBox.ButtonRole(int(role)))
        if kind is not None:
            ui_kit.set_button_icon(btn, kind)
        return btn

    def set_default(self, button):
        if button is not None:
            button.setDefault(True)
            button.setFocus()

    def clicked_button(self):
        """The button that closed the dialog, or None for Escape."""
        return self._clicked

    def _on_clicked(self, btn):
        self._clicked = btn
        std = int(self.button_box.standardButton(btn))
        if std:
            self.done(std)
        elif self.button_box.buttonRole(btn) in (QDialogButtonBox.RejectRole,
                                                 QDialogButtonBox.NoRole):
            self.done(QDialog.Rejected)
        else:
            self.done(QDialog.Accepted)

    def escape_code(self):
        return next((int(b) for b in _ESCAPE_ORDER if self._buttons & b), QDialog.Rejected)

    def accept_code(self):
        return next((int(b) for b in _ACCEPT_ORDER if self._buttons & b), QDialog.Accepted)

    def reject(self):
        # Escape and the close button: answer like QMessageBox, with Cancel or No.
        self.done(self.escape_code())

    def showEvent(self, event):  # noqa: N802 - Qt name
        if not getattr(self, "_fitted", False):
            self._fit()
        super().showEvent(event)

    def _fit(self):
        """Fixed width, the height of the text. A message taller than most of
        the screen scrolls, so the buttons stay on screen.

        A top-level layout does not ask a wrapped label for its
        height-for-width, so the height is computed here (the old host
        ``_msgbox`` cut a long warning to its first third without this).
        """
        self._fitted = True
        m = self._outer.contentsMargins()
        width = ui_kit.px(WIDTH)
        text_w = width - m.left() - m.right() - self.icon.width() - self._row.spacing()
        labels = [lbl for lbl in (self.text, self.informative) if not lbl.isHidden()]
        body_h = sum(lbl.heightForWidth(text_w) for lbl in labels)
        body_h += self._body.layout().spacing() * (len(labels) - 1)
        body_h = max(self.icon.height(), body_h)
        need_h = (m.top() + m.bottom() + body_h + self._outer.spacing()
                  + self.button_box.sizeHint().height())
        screen = QApplication.primaryScreen()
        max_h = int(screen.availableGeometry().height() * 0.8) if screen else need_h
        if need_h > max_h:
            self._row.removeWidget(self._body)
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setWidget(self._body)
            self._row.addWidget(scroll, 1)
            need_h = max_h
        self.setFixedSize(width, need_h)


def message(icon, title, text, buttons=QMessageBox.Ok, default=None, parent=None,
            informative=""):
    """Show a modal box and return the clicked standard button's code.

    For a box with buttons from ``MessageBox.add_button``, build the box and
    read ``clicked_button()`` instead: this returns only standard codes.
    """
    box = MessageBox(icon, title, text, buttons, parent, informative, default)
    result = box.exec_()
    # exec_() returns the button code from _on_clicked/reject. A plain
    # accept()/reject() (a test, or a platform close) gives 1 or 0.
    if result == QDialog.Accepted:
        return box.accept_code()
    if result == QDialog.Rejected:
        return box.escape_code()
    return result


def information(parent, title, text, buttons=QMessageBox.Ok, default=None):
    return message(QMessageBox.Information, title, text, buttons, default, parent)


def warning(parent, title, text, buttons=QMessageBox.Ok, default=None):
    return message(QMessageBox.Warning, title, text, buttons, default, parent)


def critical(parent, title, text, buttons=QMessageBox.Ok, default=None):
    return message(QMessageBox.Critical, title, text, buttons, default, parent)


def question(parent, title, text, buttons=QMessageBox.Yes | QMessageBox.No, default=None):
    return message(QMessageBox.Question, title, text, buttons, default, parent)
