"""The tray-side front end for :mod:`polyhost.services.shell_title`.

Lists each shell this computer has (bash, zsh, PowerShell 7, Windows
PowerShell 5.1) with its startup file and whether the title line is in it,
and installs or removes that line for the shells the user ticks. The rows ARE
the confirmation: each names the file that changes.

Local files only, no device and no daemon, so it works the same in client
mode, with no keyboard, and in the forwarder (which reports the window title
of the machine it runs on). The status runs on a thread because asking
PowerShell for ``$PROFILE`` starts a PowerShell process.
"""

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QGridLayout,
                             QLabel, QPushButton, QVBoxLayout)

from polyhost.i18n import _, _f, translate_message
from polyhost.services import shell_title


def shell_label(shell):
    """The shell's name as the dialog shows it (product names, not translated)."""
    return {
        shell_title.BASH: "bash",
        shell_title.ZSH: "zsh",
        shell_title.PWSH: "PowerShell 7 (pwsh)",
        shell_title.POWERSHELL: "Windows PowerShell 5.1",
        shell_title.FISH: "fish",
        shell_title.CMD: "cmd.exe",
        shell_title.MACOS_TERMINAL: "Terminal.app, iTerm2",
    }.get(shell, shell)


def state_text(st):
    """One shell's state, translated."""
    if st.state == shell_title.STATE_INSTALLED:
        return _("Set up")
    if st.state == shell_title.STATE_NOT_INSTALLED:
        return _("Not set up")
    if st.state == shell_title.STATE_STALE:
        return _f("Set up for another copy of the app: {path}", path=st.detail or "?")
    if st.state == shell_title.STATE_NOT_PRESENT:
        return _("Not found")
    if st.state == shell_title.STATE_UNKNOWN:
        return _f("The profile path is unknown: {error}", error=st.detail)
    if st.state == shell_title.STATE_BLOCKED:
        return _f("PowerShell's execution policy ({policy}) does not run profile scripts.",
                  policy=st.detail)
    return _("Shows the command without setup")


class _StatusThread(QThread):
    done = pyqtSignal(object)

    def __init__(self, status_fn, parent=None):
        super().__init__(parent)
        self._status_fn = status_fn

    def run(self):
        try:
            result = self._status_fn()
        except Exception as exc:  # noqa: BLE001 - shown in the dialog, never raised into Qt
            result = exc
        self.done.emit(result)


class ShellTitleDialog(QDialog):
    """``status_fn``, ``install_fn`` and ``remove_fn`` are the service's
    functions; tests pass fakes."""

    def __init__(self, parent=None, status_fn=None, install_fn=None, remove_fn=None):
        super().__init__(parent)
        self._status_fn = status_fn or shell_title.status
        self._install_fn = install_fn or shell_title.install
        self._remove_fn = remove_fn or shell_title.remove
        self._statuses = []
        self._boxes = {}
        self._thread = None
        self.setWindowTitle(_("Command in the terminal title"))

        layout = QVBoxLayout(self)
        intro = QLabel(_(
            "The keyboard shows the shortcuts of a program running in a terminal "
            "(nano, for example) only when the terminal's window title names the "
            "program. bash, zsh and PowerShell do not do this without setup.\n\n"
            "Install adds one line to the startup file of each selected shell, "
            "between two marker comments, and first saves a copy of the file next "
            "to it. Remove deletes those lines. The change applies to terminal "
            "windows opened afterwards."))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._grid = QGridLayout()
        self._grid.setColumnStretch(1, 1)
        layout.addLayout(self._grid)
        self._checking = QLabel(_("Checking the shells…"))
        layout.addWidget(self._checking)
        self._info = QLabel()
        self._info.setWordWrap(True)
        self._info.hide()
        layout.addWidget(self._info)
        self._results = QLabel()
        self._results.setWordWrap(True)
        self._results.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._results.hide()
        layout.addWidget(self._results)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.install_button = QPushButton(_("Install"))
        self.remove_button = QPushButton(_("Remove"))
        buttons.addButton(self.install_button, QDialogButtonBox.ActionRole)
        buttons.addButton(self.remove_button, QDialogButtonBox.ActionRole)
        # noinspection PyUnresolvedReferences
        buttons.rejected.connect(self.reject)
        # noinspection PyUnresolvedReferences
        self.install_button.clicked.connect(lambda: self._apply(True))
        # noinspection PyUnresolvedReferences
        self.remove_button.clicked.connect(lambda: self._apply(False))
        layout.addWidget(buttons)
        self.setMinimumWidth(620)
        self._update_buttons()
        self.refresh()

    # --- status ---------------------------------------------------------
    def refresh(self):
        """Read the state again on a thread; the rows are rebuilt when it ends."""
        if self._thread is not None and self._thread.isRunning():
            return
        self._checking.show()
        self.install_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self._thread = _StatusThread(self._status_fn, self)
        # noinspection PyUnresolvedReferences
        self._thread.done.connect(self._on_status)
        # `done` is emitted from run(), so it can be handled while the thread
        # still counts as running, and _update_buttons() then keeps both
        # buttons off. `finished` comes after run() has returned.
        # noinspection PyUnresolvedReferences
        self._thread.finished.connect(self._update_buttons)
        self._thread.start()

    def reopen(self):
        """Called when the tray opens the retained dialog again: the files may
        have changed since, so read them again and drop the old results."""
        self._results.hide()
        self.refresh()

    def _on_status(self, result):
        self._checking.hide()
        if isinstance(result, Exception):
            self._info.setText(_f("The shells could not be checked: {error}", error=str(result)))
            self._info.show()
            self._update_buttons()
            return
        self._statuses = list(result)
        self._rebuild_rows()

    def _rebuild_rows(self):
        old = {shell: box.isChecked() for shell, box in self._boxes.items()}
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._boxes = {}
        row = 0
        info = []
        for st in self._statuses:
            if st.state == shell_title.STATE_NO_SETUP:
                info.append(_f("{shell}: shows the command without setup.",
                               shell=shell_label(st.shell)))
                continue
            if st.state == shell_title.STATE_NOT_PRESENT:
                continue
            box = QCheckBox(shell_label(st.shell))
            if st.shell in old:
                box.setChecked(old[st.shell])
            else:
                box.setChecked(st.state == shell_title.STATE_STALE
                               or (st.state == shell_title.STATE_NOT_INSTALLED
                                   and shell_title.default_selection(st)))
            # noinspection PyUnresolvedReferences
            box.toggled.connect(self._update_buttons)
            self._boxes[st.shell] = box
            # The state under the file: a stale block's path is long, and three
            # columns squeezed it into a clipped sliver.
            path = QLabel(str(st.rc_path) if st.rc_path is not None else "")
            path.setTextInteractionFlags(Qt.TextSelectableByMouse)
            path.setToolTip(path.text())    # a long profile path is cut at the edge
            state = QLabel(state_text(st))
            state.setWordWrap(True)
            state.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._grid.addWidget(box, row, 0, Qt.AlignTop)
            self._grid.addWidget(path, row, 1)
            self._grid.addWidget(state, row + 1, 1)
            row += 2
        if not self._boxes:
            info.insert(0, _("No bash, zsh or PowerShell was found on this computer."))
        self._info.setText("\n".join(info))
        self._info.setVisible(bool(info))
        self._update_buttons()
        self._fit()

    def _update_buttons(self):
        any_checked = any(box.isChecked() for box in self._boxes.values())
        busy = self._thread is not None and self._thread.isRunning()
        self.install_button.setEnabled(any_checked and not busy)
        self.remove_button.setEnabled(any_checked and not busy)

    # --- install / remove -------------------------------------------------
    def selected(self):
        return [shell for shell, box in self._boxes.items() if box.isChecked()]

    def _apply(self, install):
        shells = self.selected()
        if not shells:
            return
        fn = self._install_fn if install else self._remove_fn
        try:
            results = fn(shells, statuses=self._statuses)
        except Exception as exc:  # noqa: BLE001 - a dialog must not take the tray down
            self._show_results([_f("The change failed: {error}", error=str(exc))])
            self.refresh()
            return
        lines = []
        for r in results:
            lines.append(f"{shell_label(r.shell)}: {translate_message(r.message)}")
            if r.backup is not None:
                lines.append(_f("Copy of the previous file: {path}", path=str(r.backup)))
        if install and any(r.changed for r in results):
            lines.append(_("Open a new terminal window for the change to take effect."))
        self._show_results(lines)
        self.refresh()

    def _show_results(self, lines):
        self._results.setText("\n".join(lines))
        self._results.show()
        self._fit()

    def _fit(self):
        """Grow the window to what the wrapped labels need at its width.
        adjustSize() sizes a word-wrapped QLabel from a guessed width and left
        the rows overlapping."""
        layout = self.layout()
        layout.activate()
        width = max(self.width(), self.minimumWidth())
        height = layout.totalHeightForWidth(width)
        if height > 0:
            self.resize(width, max(height, self.height()))
