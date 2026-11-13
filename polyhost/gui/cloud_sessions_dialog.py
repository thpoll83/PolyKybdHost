"""AI Agents → Connect Cloud Sessions…: Claude Code cloud sessions (claude.ai/code)
on the agent keys, through the relay (services/agents/cloud_relay.py).

The dialog shows what the user enters in the claude.ai cloud environment's
settings, each with a Copy button. Every core call runs off the GUI thread
(`call_async(fn, done)`, the tray's _core_click): connect and disconnect go over
the network, and in client mode every call is an RPC to the daemon.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QDialog, QGridLayout, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
                             QVBoxLayout)

from polyhost.i18n import _, _f


class CloudSessionsDialog(QDialog):
    def __init__(self, core, call_async, parent=None):
        super().__init__(parent)
        self.core = core
        self.call_async = call_async
        self.setWindowTitle(_("Connect Cloud Sessions"))
        self.setMinimumWidth(560)

        intro = QLabel(_(
            "Shows Claude Code sessions that run in the cloud (claude.ai/code, also "
            "when the desktop app shows them) on the agent keys. A key press opens the "
            "session's page. The session's state goes through the PolyKybd relay, "
            "encrypted with a key that only this computer and your cloud environment "
            "have."))
        intro.setWordWrap(True)
        self.status = QLabel()
        self.status.setWordWrap(True)

        self.steps = QLabel(_(
            "In claude.ai, open the cloud environment's settings and enter these. Use a "
            "personal environment: everyone who uses an environment can read its "
            "variables."))
        self.steps.setWordWrap(True)
        grid = QGridLayout()
        self.variable_label = QLabel(_("Environment variable"))
        self.variable = QLineEdit(readOnly=True)
        self.host_label = QLabel(_("Allowed host (when network access is Limited)"))
        self.host = QLineEdit(readOnly=True)
        self.script_label = QLabel(_("Setup script"))
        self.script = QPlainTextEdit(readOnly=True)
        self.script.setLineWrapMode(QPlainTextEdit.NoWrap)
        # Two lines of script, the frame and room for a horizontal scroll bar.
        self.script.setFixedHeight(self.script.fontMetrics().lineSpacing() * 2 + 40)
        self._copies = []
        for row, (label, field) in enumerate(((self.variable_label, self.variable),
                                              (self.host_label, self.host),
                                              (self.script_label, self.script))):
            copy = QPushButton(_("Copy"))
            # noinspection PyUnresolvedReferences
            copy.clicked.connect(lambda _c=False, f=field: self._copy(f))
            self._copies.append(copy)
            grid.addWidget(label, row * 2, 0, 1, 2)
            grid.addWidget(field, row * 2 + 1, 0)
            grid.addWidget(copy, row * 2 + 1, 1, Qt.AlignTop)
        self.after = QLabel(_("Each new cloud session of that environment then shows on "
                              "a number key."))
        self.after.setWordWrap(True)

        self.connect_button = QPushButton(_("Connect"))
        # noinspection PyUnresolvedReferences
        self.connect_button.clicked.connect(self._connect)
        self.disconnect_button = QPushButton(_("Disconnect…"))
        # noinspection PyUnresolvedReferences
        self.disconnect_button.clicked.connect(self._disconnect)
        close = QPushButton(_("Close"))
        # noinspection PyUnresolvedReferences
        close.clicked.connect(self.close)
        buttons = QHBoxLayout()
        buttons.addWidget(self.connect_button)
        buttons.addWidget(self.disconnect_button)
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.status)
        layout.addWidget(self.steps)
        layout.addLayout(grid)
        layout.addWidget(self.after)
        layout.addStretch(1)
        layout.addLayout(buttons)
        self._show({})
        self.status.setText(_("Reading the state…"))
        self._refresh()

    def _refresh(self):
        # agents_cloud_status() answers a dict, not an (ok, value) pair.
        self.call_async(lambda: (True, self.core.agents_cloud_status()), self._status_done)

    # ---- results (GUI thread) ------------------------------------------------------

    def _status_done(self, ok, info):
        self._show(info if ok and isinstance(info, dict) else {})
        if not ok:
            self.status.setText(_f("The state could not be read: {msg}", msg=info))

    def _show(self, info: dict):
        configured = bool(info.get("configured"))
        setup = info.get("setup") or {}
        self.variable.setText(f"{setup.get('variable', '')}={setup.get('config', '')}"
                              if configured else "")
        self.host.setText(setup.get("host", "") if configured else "")
        self.variable.setCursorPosition(0)     # show where the value starts
        self.script.setPlainText(setup.get("script", "") if configured else "")
        for widget in (self.steps, self.variable_label, self.variable, self.host_label,
                       self.host, self.script_label, self.script, self.after, *self._copies):
            widget.setVisible(configured)
        self.connect_button.setVisible(not configured)
        self.connect_button.setEnabled(True)
        self.disconnect_button.setVisible(configured)
        self.disconnect_button.setEnabled(True)
        # The setup fields appear after the state arrives: grow to fit them.
        self.adjustSize()
        if not configured:
            self.status.setText(_("Not connected. \"Connect\" creates a channel on the relay "
                                  "for this computer."))
            return
        state = (info.get("connection") or {}).get("state", "stopped")
        error = (info.get("connection") or {}).get("error", "")
        if not info.get("agents_enabled"):
            text = _("The agent keys are off: turn on \"Show on the Number Row\" in the "
                     "AI Agents menu.")
        elif state == "connected":
            text = _("Connected to the relay.")
        elif state == "retrying":
            text = _f("The relay cannot be reached; trying again: {error}", error=error)
        else:
            text = _("Connecting to the relay…")
        self.status.setText(text)

    # ---- actions --------------------------------------------------------------------

    def _copy(self, field):
        text = field.toPlainText() if isinstance(field, QPlainTextEdit) else field.text()
        QApplication.clipboard().setText(text)

    def _connect(self):
        self.connect_button.setEnabled(False)
        self.status.setText(_("Creating a channel on the relay…"))
        self.call_async(self.core.agents_cloud_connect, self._status_done)

    def _disconnect(self):
        answer = QMessageBox.question(
            self, _("Disconnect Cloud Sessions"),
            _("Delete the channel on the relay? The cloud sessions leave the agent keys, "
              "and the hooks in your cloud environment stop reaching this computer. "
              "Remove the environment variable there too."))
        if answer != QMessageBox.Yes:
            return
        self.disconnect_button.setEnabled(False)

        def done(ok, msg):
            if not ok:
                QMessageBox.warning(self, _("Disconnect Cloud Sessions"), str(msg))
            self._refresh()
        self.call_async(self.core.agents_cloud_disconnect, done)
