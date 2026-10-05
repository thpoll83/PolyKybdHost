"""A failure dialog whose details can be copied.

A plain message box shows an error as a label: it is clipped when long and
the user cannot select or copy it. The update failure is the case that needed
this, since pip's output is long and the line that matters is near the end.
Both tray apps (``host.py`` and ``forwarder.py``) open it, so it lives here
rather than as two copies.
"""

from PyQt5.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                             QPlainTextEdit, QPushButton, QStyle, QVBoxLayout)


class CopyableErrorDialog(QDialog):
    """Headline, a read-only scrollable details box, Copy and Close."""

    def __init__(self, title: str, headline: str, details: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(560, 300)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        icon = QLabel(self)
        icon.setPixmap(self.style().standardPixmap(QStyle.SP_MessageBoxWarning))
        top.addWidget(icon, 0)
        self.headline = QLabel(headline, self)
        self.headline.setWordWrap(True)
        top.addWidget(self.headline, 1)
        layout.addLayout(top)

        self.detail = QPlainTextEdit(self)
        self.detail.setReadOnly(True)
        self.detail.setPlainText(details)
        self.detail.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        layout.addWidget(self.detail, 1)

        self.status = QLabel("", self)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.copy_btn = QPushButton("Copy to Clipboard", self)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        buttons.addWidget(self.copy_btn)
        buttons.addStretch(1)
        close = QPushButton("Close", self)
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def text(self) -> str:
        """What the Copy button puts on the clipboard: headline and details."""
        return f"{self.headline.text()}\n\n{self.detail.toPlainText()}"

    def copy_to_clipboard(self) -> None:
        QApplication.clipboard().setText(self.text())
        self.status.setText("Copied to the clipboard.")


def show_copyable_error(title: str, headline: str, details: str, parent=None) -> None:
    """Open the dialog modally and return once the user closes it."""
    CopyableErrorDialog(title, headline, details, parent).exec_()
