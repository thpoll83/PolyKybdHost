"""AI Agents → Connect Cloud Sessions…: Claude Code cloud sessions (claude.ai/code)
on the agent keys, through the relay (services/agents/cloud_relay.py).

Built from the ui_kit parts (docs/tray-ui.md): a headline with the connection
state and the explanation in grey, one card with what the user enters in the
claude.ai cloud environment's settings (each with a Copy button), a status line
and one button row with icons. Every core call runs off the GUI thread
(`call_async(fn, done)`, the tray's _core_click): connect and disconnect go over
the network, and in client mode every call is an RPC to the daemon.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QGridLayout, QLabel,
                             QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
                             QVBoxLayout)

from polyhost.gui import message_box
from polyhost.gui.ui_kit import (CARD_STYLE, Headline, StatusLabel, WrapLabel, card,
                                 fit_height, headline_icon, headline_icon_px, muted, px,
                                 set_button_icon, style_button_box)
from polyhost.i18n import _, _f

# The dialog's width at 100 % (px() scales it): the setup values are long, and
# the variable field shows their start.
WIDTH = 600
# While the dialog is open, the state is read again this often, so "Connecting"
# turns into "Connected" or the relay's error without a click. No network I/O:
# the core answers from memory (an RPC in client mode).
REFRESH_MS = 2000


class CloudSessionsDialog(QDialog):
    def __init__(self, core, call_async, parent=None):
        super().__init__(parent)
        self.core = core
        self.call_async = call_async
        self.setWindowTitle(_("Connect Cloud Sessions"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(CARD_STYLE)
        self.setMinimumWidth(px(WIDTH))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(16), px(14), px(16), px(12))
        layout.setSpacing(px(12))

        # The bold line is the connection state; the grey text explains the feature.
        self.head = Headline(_("Reading the state…"), _(
            "Shows Claude Code sessions that run in the cloud (claude.ai/code, also "
            "when the desktop app shows them) on the agent keys. A key press brings the "
            "session's browser window or the Claude app to the front. The session's "
            "state goes through the PolyKybd relay, "
            "encrypted with a key that only this computer and your cloud environment "
            "have."), kind="info", parent=self)
        layout.addWidget(self.head)

        self.setup_card, card_lay = card(self)
        card_lay.addWidget(self._heading(_("Cloud environment settings")))
        card_lay.addWidget(muted(WrapLabel(_(
            "In claude.ai, open the cloud environment's settings and enter these. Use a "
            "personal environment: everyone who uses an environment can read its "
            "variables."))))
        grid = QGridLayout()
        grid.setColumnStretch(0, 1)
        grid.setHorizontalSpacing(px(8))
        grid.setVerticalSpacing(px(4))
        self.variable = QLineEdit(readOnly=True)
        self.host = QLineEdit(readOnly=True)
        self.script = QPlainTextEdit(readOnly=True)
        self.script.setLineWrapMode(QPlainTextEdit.NoWrap)
        # Two lines of script, the frame and room for a horizontal scroll bar.
        self.script.setFixedHeight(self.script.fontMetrics().lineSpacing() * 2 + px(40))
        self._copies = []
        rows = ((_("Environment variable"), self.variable),
                (_("Allowed host (when network access is Limited)"), self.host),
                (_("Setup script"), self.script))
        for row, (label, field) in enumerate(rows):
            # A value and a shell script read left to right in every language.
            field.setLayoutDirection(Qt.LeftToRight)
            copy = set_button_icon(QPushButton(_("Copy")), "copy")
            # noinspection PyUnresolvedReferences
            copy.clicked.connect(lambda _c=False, f=field: self._copy(f))
            self._copies.append(copy)
            grid.addWidget(QLabel(label), row * 2, 0, 1, 2)
            grid.addWidget(field, row * 2 + 1, 0)
            grid.addWidget(copy, row * 2 + 1, 1, Qt.AlignTop)
        card_lay.addLayout(grid)
        card_lay.addWidget(muted(WrapLabel(_(
            "Each new cloud session of that environment then shows on a number key."))))
        layout.addWidget(self.setup_card)

        self.status = StatusLabel("", self)
        layout.addWidget(self.status)
        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.connect_button = set_button_icon(QPushButton(_("Connect")), "start")
        self.disconnect_button = set_button_icon(QPushButton(_("Disconnect…")), "delete")
        buttons.addButton(self.connect_button, QDialogButtonBox.ActionRole)
        buttons.addButton(self.disconnect_button, QDialogButtonBox.ActionRole)
        style_button_box(buttons)
        # noinspection PyUnresolvedReferences
        buttons.rejected.connect(self.close)
        # noinspection PyUnresolvedReferences
        self.connect_button.clicked.connect(self._connect)
        # noinspection PyUnresolvedReferences
        self.disconnect_button.clicked.connect(self._disconnect)
        layout.addWidget(buttons)

        self._in_flight = False     # a status request is out
        self._busy = False          # a connect or disconnect is running
        self._error = None          # a failed connect, kept until a retry or a channel
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(REFRESH_MS)
        # noinspection PyUnresolvedReferences
        self._refresh_timer.timeout.connect(self._refresh)
        self._show({})
        self._set_state(_("Reading the state…"))
        self._refresh()

    def showEvent(self, event):  # noqa: N802 - Qt name
        super().showEvent(event)
        self._refresh_timer.start()
        QTimer.singleShot(0, lambda: fit_height(self))

    def hideEvent(self, event):  # noqa: N802 - Qt name
        self._refresh_timer.stop()
        super().hideEvent(event)

    @staticmethod
    def _heading(text):
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    def _set_state(self, text, kind="info"):
        self.head.set_title(text)
        size = headline_icon_px()
        self.head.icon.setPixmap(headline_icon(kind).pixmap(size, size))

    def _refresh(self):
        if self._in_flight:
            return          # one request at a time: a slow daemon is not queued up
        self._in_flight = True
        # agents_cloud_status() answers a dict, not an (ok, value) pair.
        self.call_async(lambda: (True, self.core.agents_cloud_status()), self._status_done)

    # ---- results (GUI thread) ------------------------------------------------------

    def _status_done(self, ok, info):
        self._in_flight = False
        if self._busy:
            return          # a connect or disconnect is running; its answer comes next
        configured = ok and isinstance(info, dict) and info.get("configured")
        if self._error is not None and not configured:
            return          # "Not connected" would hide why the connect failed
        self._error = None
        self._show_result(ok, info)

    def _show_result(self, ok, info):
        self._show(info if ok and isinstance(info, dict) else {})
        if not ok:
            self._set_state(_f("The state could not be read: {msg}", msg=info), "error")

    def _show(self, info: dict):
        configured = bool(info.get("configured"))
        setup = info.get("setup") or {}
        self.variable.setText(f"{setup.get('variable', '')}={setup.get('config', '')}"
                              if configured else "")
        self.variable.setCursorPosition(0)     # show where the value starts
        self.host.setText(setup.get("host", "") if configured else "")
        self.script.setPlainText(setup.get("script", "") if configured else "")
        self.setup_card.setVisible(configured)
        self.connect_button.setVisible(not configured)
        self.connect_button.setEnabled(True)
        self.disconnect_button.setVisible(configured)
        self.disconnect_button.setEnabled(True)
        # The setup card appears after the state arrives: grow to fit it, and
        # again once its text has wrapped (ui_kit.fit_height).
        self.adjustSize()
        QTimer.singleShot(0, lambda: fit_height(self))
        if not configured:
            self._set_state(_("Not connected. \"Connect\" creates a channel on the relay "
                              "for this computer."))
            return
        state = (info.get("connection") or {}).get("state", "stopped")
        error = (info.get("connection") or {}).get("error", "")
        if not info.get("agents_enabled"):
            self._set_state(_("The agent keys are off: turn on \"Show on the Number Row\" in "
                              "the AI Agents menu."), "warning")
        elif state == "connected":
            self._set_state(_("Connected to the relay."))
        elif state == "retrying":
            self._set_state(_f("The relay cannot be reached; trying again: {error}",
                               error=error), "warning")
        else:
            self._set_state(_("Connecting to the relay…"))

    # ---- actions --------------------------------------------------------------------

    def _copy(self, field):
        text = field.toPlainText() if isinstance(field, QPlainTextEdit) else field.text()
        QApplication.clipboard().setText(text)
        self.status.setText(_("Copied to the clipboard."))

    def _connect(self):
        self._busy = True
        self.connect_button.setEnabled(False)
        self._set_state(_("Creating a channel on the relay…"))

        def done(ok, info):
            self._busy = False
            if ok:
                self._error = None
                self._show_result(ok, info)
                return
            self._error = str(info) if info else ""
            self._show({})
            self._set_state(_f("Could not connect: {msg}", msg=self._error), "error")
        self._error = None
        self.call_async(self.core.agents_cloud_connect, done)

    def _disconnect(self):
        answer = message_box.question(
            self, _("Disconnect Cloud Sessions"),
            _("Delete the channel on the relay? The cloud sessions leave the agent keys, "
              "and the hooks in your cloud environment stop reaching this computer. "
              "Remove the environment variable there too."))
        if answer != QMessageBox.Yes:
            return
        self._busy = True
        self.disconnect_button.setEnabled(False)

        def done(ok, msg):
            self._busy = False
            if not ok:
                message_box.warning(self, _("Disconnect Cloud Sessions"), str(msg))
            self._refresh()
        self.call_async(self.core.agents_cloud_disconnect, done)
