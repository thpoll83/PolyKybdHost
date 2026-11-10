"""A failure dialog whose details can be copied.

A plain message box shows an error as a label: it is clipped when long and
the user cannot select or copy it. The update failure is the case that needed
this, since pip's output is long and the line that matters is near the end.
Both tray apps (``host.py`` and ``forwarder.py``) open it, so it lives here
rather than as two copies.
"""

from PyQt5.QtWidgets import (QApplication, QDialog, QHBoxLayout, QPlainTextEdit,
                             QPushButton, QVBoxLayout)

from polyhost.gui.ui_kit import Headline, StatusLabel, fit_text_lines, set_button_icon
from polyhost.i18n import _


class CopyableErrorDialog(QDialog):
    """Headline, a read-only scrollable details box, Copy and Close.

    ``commands``, when given, adds a button that copies only those lines: the
    steps can say to quit the app, which closes this dialog with it.
    """

    def __init__(self, title: str, headline: str, details: str, parent=None,
                 commands: str = ""):
        super().__init__(parent)
        self._commands = commands
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        self.resize(680, 10)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        self._head = Headline(headline, kind="warning", parent=self)
        self.headline = self._head.title
        layout.addWidget(self._head)

        self.detail = QPlainTextEdit(self)
        self.detail.setReadOnly(True)
        self.detail.setPlainText(details)
        self.detail.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        fit_text_lines(self.detail, min_lines=3, max_lines=16)
        layout.addWidget(self.detail)

        self.status = StatusLabel("", self)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.copy_btn = set_button_icon(QPushButton(_("Copy to Clipboard"), self), "copy")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        buttons.addWidget(self.copy_btn)
        self.copy_cmds_btn = None
        if commands:
            self.copy_cmds_btn = set_button_icon(
                QPushButton(_("Copy Fix Commands"), self), "copy")
            self.copy_cmds_btn.setToolTip(
                _("Copy only the commands, to paste into a terminal after quitting."))
            self.copy_cmds_btn.clicked.connect(self.copy_commands)
            buttons.addWidget(self.copy_cmds_btn)
        buttons.addStretch(1)
        close = set_button_icon(QPushButton(_("Close"), self), "close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def text(self) -> str:
        """What the Copy button puts on the clipboard: headline and details."""
        return f"{self.headline.text()}\n\n{self.detail.toPlainText()}"

    def copy_to_clipboard(self) -> None:
        QApplication.clipboard().setText(self.text())
        self.status.setText(_("Copied to the clipboard."))


    def copy_commands(self) -> None:
        QApplication.clipboard().setText(self._commands)
        self.status.setText(_("Commands copied. Paste them into a terminal."))


def show_copyable_error(title: str, headline: str, details: str, parent=None,
                        commands: str = "") -> None:
    """Open the dialog modally and return once the user closes it."""
    CopyableErrorDialog(title, headline, details, parent, commands).exec_()
