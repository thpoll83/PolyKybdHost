"""AI Agents → Install Browser Extension…: copy the PolyKybd browser extension to
a folder and show how to load it (services/browser_extension.py).

The extension reports the focused tab's address (website overlays) and switches
to a Claude Code cloud session's tab on its agent key. Until it is in the browser
stores, a Chromium browser loads it from a folder in Developer mode. The host
copies newer versions into the same folder after an update.
"""
from __future__ import annotations

import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QFileDialog,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout)

from polyhost.gui.ui_kit import (CARD_STYLE, Headline, StatusLabel, WrapLabel, card,
                                 fit_height, muted, px, set_button_icon, style_button_box)
from polyhost.i18n import _, _f
from polyhost.services import browser_extension as be

WIDTH = 560
EXTENSIONS_PAGE = "chrome://extensions"



class BrowserExtensionDialog(QDialog):
    def __init__(self, log, parent=None, receiver_port=None):
        super().__init__(parent)
        self.log = log
        self.setWindowTitle(_("Install Browser Extension"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(CARD_STYLE)
        self.setMinimumWidth(px(WIDTH))
        if receiver_port is None:
            from polyhost.settings import read_setting
            receiver_port = read_setting("browser_report_port", 50164)
        version = be.source_version()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(16), px(14), px(16), px(12))
        layout.setSpacing(px(12))
        layout.addWidget(Headline(
            _f("PolyKybd browser extension {version}", version=version or "?"),
            _("Shows website overlays for the focused browser tab, and switches to a "
              "Claude Code cloud session's tab when you press its agent key. For "
              "Chrome, Edge, Brave, Vivaldi, Opera and Arc."), kind="info", parent=self))

        folder_card, folder_lay = card(self)
        folder_lay.addWidget(self._heading(_("1. Copy it to a folder")))
        folder_lay.addWidget(muted(WrapLabel(_(
            "Choose an empty folder that stays where it is. After each update of this "
            "app, the new version is copied there too."))))
        row = QHBoxLayout()
        self.folder = QLineEdit(be.remembered_folder())
        self.folder.setPlaceholderText(_("Folder"))
        browse = set_button_icon(QPushButton(_("Choose…")), "folder")
        # noinspection PyUnresolvedReferences
        browse.clicked.connect(self._choose)
        self.copy_button = set_button_icon(QPushButton(_("Copy Extension")), "install")
        # noinspection PyUnresolvedReferences
        self.copy_button.clicked.connect(self._copy)
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        row.addWidget(self.copy_button)
        folder_lay.addLayout(row)
        layout.addWidget(folder_card)

        load_card, load_lay = card(self)
        load_lay.addWidget(self._heading(_("2. Load it in the browser")))
        steps = WrapLabel(_f(
            "Open {page} (Edge: edge://extensions), turn on Developer mode, click "
            "\"Load unpacked\" and choose the folder. In the extension's Options, the "
            "port must be {port}, the same as \"Receiver port\" in this app's settings. "
            "After an update of this app, click Reload on the extension's card.",
            page=EXTENSIONS_PAGE, port=receiver_port))
        load_lay.addWidget(steps)
        page_row = QHBoxLayout()
        copy_page = set_button_icon(QPushButton(_f("Copy \"{page}\"", page=EXTENSIONS_PAGE)),
                                    "copy")
        # noinspection PyUnresolvedReferences
        copy_page.clicked.connect(lambda: self._clip(EXTENSIONS_PAGE))
        page_row.addWidget(copy_page)
        page_row.addStretch(1)
        load_lay.addLayout(page_row)
        load_lay.addWidget(muted(WrapLabel(_(
            "Firefox keeps an extension loaded from a folder only until it restarts. "
            "Use the version from Firefox Add-ons there once it is published."))))
        layout.addWidget(load_card)

        self.status = StatusLabel("", self)
        layout.addWidget(self.status)
        buttons = style_button_box(QDialogButtonBox(QDialogButtonBox.Close))
        # noinspection PyUnresolvedReferences
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        if not version:
            self.copy_button.setEnabled(False)
            self.status.setText(_("This installation has no browser extension files."))

    def showEvent(self, event):  # noqa: N802 - Qt name
        super().showEvent(event)
        QTimer.singleShot(0, lambda: fit_height(self))     # after the text wrapped

    @staticmethod
    def _heading(text):
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    def _clip(self, text):
        QApplication.clipboard().setText(text)
        self.status.setText(_("Copied to the clipboard."))

    def _choose(self):
        start = self.folder.text() or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, _("Folder for the extension"), start)
        if folder:
            self.folder.setText(os.path.normpath(folder))

    def _copy(self):
        folder = self.folder.text().strip()
        if not folder:
            self.status.setText(_("Choose a folder first."))
            return
        try:
            version = be.deploy(folder)
            be.remember_folder(folder)
        except (be.ExtensionError, OSError) as e:
            self.status.setText(_f("Not copied: {msg}", msg=str(e)))
            return
        self.log.info("Browser extension %s copied to %s", version, folder)
        self.status.setText(_f("Copied version {version}. Now load the folder in the "
                               "browser (step 2).", version=version))
