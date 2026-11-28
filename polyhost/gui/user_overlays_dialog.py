"""The list of the user's overlay sets, with Remove (docs/mcp-server-plan.md, v2).

An AI assistant makes these sets through the MCP server (`polyctl mcp`); this
dialog lets the user see and remove them without the assistant. Every core call
goes through ``run_async(fn, done)`` (``host._core_click``), so it works in client
mode without blocking the GUI thread.
"""
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                             QVBoxLayout, QWidget)

from polyhost.gui.ui_kit import CARD_STYLE, WrapLabel, card, muted
from polyhost.i18n import _, _f

ALL_APPS = "*"


def set_title(app):
    return _("Every app") if app == ALL_APPS else app


class UserOverlaysDialog(QDialog):

    def __init__(self, core, run_async, parent=None):
        super().__init__(parent)
        self.core = core
        self.run_async = run_async
        self.setWindowTitle(_("Overlays made by AI assistants"))
        self.setStyleSheet(CARD_STYLE)
        self.resize(520, 420)
        main = QVBoxLayout(self)
        intro = WrapLabel(_(
            "Key drawings and overlay sets that an AI assistant made through the MCP "
            "server. A set for an app is drawn over that app's own icons; the set for "
            "every app fills the keys an app leaves empty."))
        main.addWidget(intro)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        main.addWidget(self.scroll, 1)
        self.status = WrapLabel("")
        muted(self.status)
        main.addWidget(self.status)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton(_("Close"))
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        main.addLayout(buttons)

    def load(self):
        """Read the list off the GUI thread; called after show()."""
        self.status.setText(_("Reading the overlay sets..."))
        self.run_async(self.core.user_overlay_list, self._loaded)

    def _loaded(self, ok, sets):
        if not ok or not isinstance(sets, list):
            self.status.setText(_f("Cannot read the overlay sets: {error}", error=sets))
            return
        self.status.setText("")
        page = QWidget()
        rows = QVBoxLayout(page)
        if not sets:
            empty = WrapLabel(_("There are no overlay sets. Ask an AI assistant that has "
                                "the PolyKybd MCP server to draw on a key."))
            muted(empty)
            rows.addWidget(empty)
        for s in sets:
            app = str(s.get("app"))
            box, inner = card()
            line = QHBoxLayout()
            text = QVBoxLayout()
            title = QLabel(set_title(app))
            title.setStyleSheet("font-weight: 600;")
            text.addWidget(title)
            count = QLabel(_f("Keys: {n}", n=int(s.get("keys", 0))))
            muted(count)
            text.addWidget(count)
            line.addLayout(text, 1)
            remove = QPushButton(_("Remove"))
            remove.setToolTip(_f("Remove the overlay set for {app}.", app=set_title(app)))
            remove.clicked.connect(lambda _checked=False, a=app, b=remove: self._remove(a, b))
            line.addWidget(remove)
            inner.addLayout(line)
            rows.addWidget(box)
        rows.addStretch(1)
        self.scroll.setWidget(page)

    def _remove(self, app, button):
        button.setEnabled(False)
        self.run_async(lambda: self.core.user_overlay_clear(app), self._removed)

    def _removed(self, ok, result):
        if not ok:
            # Keep the error visible: a refresh would overwrite it. The row's button
            # is enabled again by reloading the list only after a success.
            self.status.setText(_f("Cannot remove the overlay set: {error}", error=result))
            for button in self.scroll.widget().findChildren(QPushButton):
                button.setEnabled(True)
            return
        self.load()
