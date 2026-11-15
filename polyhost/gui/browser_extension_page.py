"""Integrations > Browser: copy the PolyKybd browser extension to a folder and
show how to load it (services/browser_extension.py).

The extension reports the focused tab's address (website overlays) and switches
to a Claude Code cloud session's tab on its agent key. Until it is in the browser
stores, a Chromium browser loads it from a folder in Developer mode. The host
copies newer versions into the same folder after an update.
"""
from __future__ import annotations

import os

from PyQt5.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QVBoxLayout, QWidget)

from polyhost.gui.ui_kit import (Headline, StatusLabel, WrapLabel, card, muted,
                                 set_button_icon)
from polyhost.i18n import _, _f
from polyhost.services import browser_extension as be

EXTENSIONS_PAGE = "chrome://extensions"



class BrowserPage(QWidget):
    def __init__(self, log, parent=None, receiver_port=None):
        super().__init__(parent)
        self.log = log
        # A fixed port (tests) is kept; otherwise reopen() reads the setting
        # again, since the dialog is kept and the port can change meanwhile.
        self._fixed_port = receiver_port
        version = be.source_version()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        head = QLabel(_("Browser"))
        head.setObjectName("settingsSectionTitle")
        layout.addWidget(head)
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
        self.steps = steps = WrapLabel(self._steps_text())
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
        layout.addStretch(1)
        if not version:
            self.copy_button.setEnabled(False)
            self.status.setText(_("This installation has no browser extension files."))

    def _receiver_port(self):
        if self._fixed_port is not None:
            return self._fixed_port
        from polyhost.settings import read_setting
        return read_setting("browser_report_port", 50164)

    def _steps_text(self):
        return _f(
            "Open {page} (Edge: edge://extensions), turn on Developer mode, click "
            "\"Load unpacked\" and choose the folder. In the extension's Options, the "
            "port must be {port}, the same as \"Receiver port\" in this app's settings. "
            "After an update of this app, click Reload on the extension's card.",
            page=EXTENSIONS_PAGE, port=self._receiver_port())

    def reopen(self):
        """The dialog opens again: show the receiver port as it is now."""
        self.steps.setText(self._steps_text())
        self.status.setText("")

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
