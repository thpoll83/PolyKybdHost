"""The tray-side front end for :mod:`polyhost.services.shell_title` and
:mod:`polyhost.services.editor_plugins`.

Lists each shell this computer has (bash, zsh, PowerShell 7, Windows
PowerShell 5.1) with its startup file and whether the title line is in it,
then each editor (Vim, Neovim, Emacs, GDB) with the folder or init file its plugin
goes to. Install and Remove act on the ticked rows of both lists. The rows ARE
the confirmation: each names the file or folder that changes.

Local files only, no device and no daemon, so it works the same in client
mode, with no keyboard, and in the forwarder (which reports the window title
of the machine it runs on). The status runs on a thread because asking
PowerShell for ``$PROFILE`` starts a PowerShell process.
"""

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QGridLayout,
                             QLabel, QPushButton, QVBoxLayout)

from polyhost.gui.ui_kit import (CARD_STYLE, WrapLabel, card, muted, px, set_button_icon,
                                 style_button_box)
from polyhost.i18n import _, _f, translate_message
from polyhost.services import editor_plugins, shell_title


def shell_label(shell):
    """The shell's name as the dialog shows it (product names, not translated)."""
    return {
        shell_title.BASH: "bash",
        shell_title.ZSH: "zsh",
        shell_title.PWSH: "PowerShell 7 (pwsh)",
        shell_title.POWERSHELL: "Windows PowerShell 5.1",
        shell_title.FISH: "fish",
        shell_title.NUSHELL: "Nushell",
        shell_title.XONSH: "xonsh",
        shell_title.CMD: "cmd.exe",
        shell_title.MACOS_TERMINAL: "Terminal.app, iTerm2",
    }.get(shell, shell)


def state_text(st):
    """One shell's state, translated."""
    if st.state == shell_title.STATE_INSTALLED:
        return _("Set up")
    if st.state == shell_title.STATE_NOT_INSTALLED and st.shell == shell_title.FISH:
        return _("Shows the command without setup. Install adds only the Codex option.")
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


def _read_report_settings():
    """This computer's (port, token) of the report listener the plugins send to."""
    from polyhost.settings import read_setting
    return read_setting("browser_report_port", 50164), read_setting("browser_report_token", "")


def editor_label(editor):
    """The editor's name as the dialog shows it (product names, not translated)."""
    return {editor_plugins.VIM: "Vim", editor_plugins.NEOVIM: "Neovim",
            editor_plugins.EMACS: "Emacs", editor_plugins.GDB: "GDB",
            editor_plugins.FREECAD: "FreeCAD"}.get(editor, editor)


def editor_state_text(st):
    """One editor's state, translated."""
    if st.state == editor_plugins.STATE_INSTALLED:
        return _("Set up")
    if st.state == editor_plugins.STATE_NOT_INSTALLED:
        return _("Not set up")
    if st.state == editor_plugins.STATE_OUTDATED:
        return _("Set up with older plugin files. Install copies the current ones.")
    if st.state == editor_plugins.STATE_MODIFIED:
        return _("Set up, and changed by hand since. This app leaves it alone.")
    if st.state == editor_plugins.STATE_STALE:
        return _f("Set up for another copy of the app: {path}", path=st.detail or "?")
    if st.state == editor_plugins.STATE_MANUAL:
        return _f("The plugin is already loaded from {path}.", path=st.detail or "?")
    if st.state == editor_plugins.STATE_NO_SOURCE:
        return _f("This installation has no plugin files ({path}).", path=st.detail)
    return _("Not found")


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

    def __init__(self, parent=None, status_fn=None, install_fn=None, remove_fn=None,
                 editor_status_fn=None, editor_install_fn=None, editor_remove_fn=None,
                 report_settings=None):
        super().__init__(parent)
        self._shell_status_fn = status_fn or shell_title.status
        self._editor_status_fn = editor_status_fn or editor_plugins.status
        self._status_fn = self._status_both
        self._install_fn = install_fn or shell_title.install
        self._remove_fn = remove_fn or shell_title.remove
        self._editor_install_fn = editor_install_fn or editor_plugins.install
        self._editor_remove_fn = editor_remove_fn or editor_plugins.remove
        # (port, token) of the report listener, read from the settings file when
        # None; the plugins assume 50164 and no token.
        self._report_settings = report_settings
        self._statuses = []
        self._editor_statuses = []
        self._boxes = {}
        self._editor_boxes = {}
        self._editor_error = None
        self._thread = None
        self.setWindowTitle(_("Terminal and editor setup"))

        self.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(12)
        # One card per kind of program, as in the settings dialog: a heading,
        # the explanation in grey, then the rows.
        shell_card, shell_lay = card(self)
        shell_lay.addWidget(self._heading(_("Terminals")))
        intro = WrapLabel(_(
            "The keyboard shows the shortcuts of a program running in a terminal "
            "(nano, for example) only when the terminal's window title names the "
            "program. bash, zsh and PowerShell do not do this without setup.\n\n"
            "Install adds one line to the startup file of each selected shell, "
            "between two marker comments, and first saves a copy of the file next "
            "to it. Remove deletes those lines. The change applies to terminal "
            "windows opened afterwards. To change the Codex option, select the "
            "shells and press Install again."))
        intro.setWordWrap(True)
        shell_lay.addWidget(muted(intro))

        self._grid = self._row_grid()
        shell_lay.addLayout(self._grid)
        # Codex replaces the title with its own, which does not name it; the
        # option makes the installed line wrap the codex command.
        self.codex_box = QCheckBox(_("Also show Codex in the title (wraps the codex command)"))
        self.codex_box.setToolTip(_(
            "Codex replaces the terminal title with the thread and project name, so "
            "the keyboard cannot tell that it is running. With this option the codex "
            "command starts Codex with a title that begins with \"codex\". A codex "
            "alias or function of your own, and a title set in Codex's config.toml, "
            "are kept."))
        self._codex_touched = False
        # noinspection PyUnresolvedReferences
        self.codex_box.clicked.connect(self._on_codex_clicked)
        shell_lay.addWidget(self.codex_box)
        layout.addWidget(shell_card)

        editor_intro = WrapLabel(_(
            "Vim, Neovim and Emacs tell the keyboard their mode (Normal or Insert "
            "mode, the Org or Dired keys) only with the PolyKybd plugin. GDB shows "
            "whether the program runs or waits at the prompt only with it.\n\n"
            "Install copies the plugin from this installation to where the program "
            "loads it. For Emacs and GDB it also adds lines that load the plugin to the "
            "init file, between two marker comments, and first saves a copy of the file. "
            "When this app is updated, it copies the new plugin files at its next "
            "start. Restart the program for the change to take effect."))
        editor_intro.setWordWrap(True)
        editor_card, editor_lay = card(self)
        editor_lay.addWidget(self._heading(_("Editors")))
        editor_lay.addWidget(muted(editor_intro))
        freecad_intro = WrapLabel(_(
            "FreeCAD shows the keys of the active workbench only with the PolyKybd "
            "add-on. Install copies it to FreeCAD's Mod folder."))
        freecad_intro.setWordWrap(True)
        editor_lay.addWidget(muted(freecad_intro))
        self._editor_grid = self._row_grid()
        editor_lay.addLayout(self._editor_grid)
        self._settings_note = WrapLabel()
        self._settings_note.setWordWrap(True)
        self._settings_note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._settings_note.hide()
        editor_lay.addWidget(self._settings_note)
        layout.addWidget(editor_card)

        self._checking = muted(QLabel(_("Checking the shells…")))
        layout.addWidget(self._checking)
        self._info = WrapLabel()
        self._info.setWordWrap(True)
        self._info.hide()
        layout.addWidget(self._info)
        self._results = WrapLabel()
        self._results.setWordWrap(True)
        self._results.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._results.hide()
        layout.addWidget(self._results)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.install_button = set_button_icon(QPushButton(_("Install")), "install")
        self.remove_button = set_button_icon(QPushButton(_("Remove")), "delete")
        buttons.addButton(self.install_button, QDialogButtonBox.ActionRole)
        buttons.addButton(self.remove_button, QDialogButtonBox.ActionRole)
        style_button_box(buttons)
        # noinspection PyUnresolvedReferences
        buttons.rejected.connect(self.reject)
        # noinspection PyUnresolvedReferences
        self.install_button.clicked.connect(lambda: self._apply(True))
        # noinspection PyUnresolvedReferences
        self.remove_button.clicked.connect(lambda: self._apply(False))
        layout.addWidget(buttons)
        self.setMinimumWidth(px(620))
        self._update_buttons()
        self.refresh()

    # The first column of both grids, so the paths of shells and editors
    # start at the same x.
    _NAME_COLUMN_W = 170

    @staticmethod
    def _heading(text):
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    def _row_grid(self):
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(0, px(self._NAME_COLUMN_W))
        grid.setVerticalSpacing(2)
        return grid

    # --- status ---------------------------------------------------------
    def _status_both(self):
        """Both lists, read on the status thread. An editor check that fails
        leaves the shell rows working."""
        shells = self._shell_status_fn()
        try:
            editors = list(self._editor_status_fn())
        except Exception as exc:  # noqa: BLE001 - shown in the dialog
            editors = exc
        return shells, editors

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
        shells, editors = result
        self._statuses = list(shells)
        self._editor_error = editors if isinstance(editors, Exception) else None
        self._editor_statuses = [] if self._editor_error else list(editors)
        if not self._codex_touched:
            self.codex_box.setChecked(any(getattr(st, "codex", False) for st in self._statuses))
        self._rebuild_rows()
        self._rebuild_editor_rows()
        # The rows just replaced are deleted on the next event loop pass, and
        # until then the layout reports a height too small for the new ones
        # (the window showed 173 of 202 px). Fit again once they are gone.
        QTimer.singleShot(0, self._fit)

    def _on_codex_clicked(self):
        self._codex_touched = True

    def _rebuild_rows(self):
        old = {shell: box.isChecked() for shell, box in self._boxes.items()}
        self._clear(self._grid)
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
            state = muted(WrapLabel(state_text(st)))
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

    @staticmethod
    def _clear(grid):
        while grid.count():
            item = grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _rebuild_editor_rows(self):
        old = {editor: box.isChecked() for editor, box in self._editor_boxes.items()}
        self._clear(self._editor_grid)
        self._editor_boxes = {}
        row = 0
        if self._editor_error is not None:
            self._editor_grid.addWidget(QLabel(_f("The editors could not be checked: {error}",
                                                  error=str(self._editor_error))), 0, 0, 1, 2)
        for st in self._editor_statuses:
            if st.state == editor_plugins.STATE_NOT_PRESENT:
                continue
            box = QCheckBox(editor_label(st.editor))
            box.setChecked(old.get(st.editor, editor_plugins.default_selection(st)))
            box.setEnabled(st.state != editor_plugins.STATE_NO_SOURCE)
            # noinspection PyUnresolvedReferences
            box.toggled.connect(self._update_buttons)
            self._editor_boxes[st.editor] = box
            path = QLabel(str(st.target) if st.target is not None else "")
            path.setTextInteractionFlags(Qt.TextSelectableByMouse)
            path.setToolTip(path.text())
            state = muted(WrapLabel(editor_state_text(st)))
            state.setWordWrap(True)
            state.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._editor_grid.addWidget(box, row, 0, Qt.AlignTop)
            self._editor_grid.addWidget(path, row, 1)
            self._editor_grid.addWidget(state, row + 1, 1)
            row += 2
        if not self._editor_boxes and self._editor_error is None:
            self._editor_grid.addWidget(
                QLabel(_("No Vim, Neovim or Emacs was found on this computer.")), 0, 0, 1, 2)
        note = ""
        if self._editor_boxes:
            port, token = self._report_settings or _read_report_settings()
            if editor_plugins.needs_settings(port, token):
                if token:
                    note = _f("This app listens on port {port} and requires a token. The "
                              "plugins use port 50164 and no token: set g:polykybd_port and "
                              "g:polykybd_token in Vim, or polykybd-port and polykybd-token "
                              "in Emacs, to the same values.", port=port)
                else:
                    note = _f("This app listens on port {port}. The plugins use port 50164: "
                              "set g:polykybd_port in Vim, or polykybd-port in Emacs, to the "
                              "same value.", port=port)
        self._settings_note.setText(note)
        self._settings_note.setVisible(bool(note))
        self._update_buttons()
        self._fit()

    def _update_buttons(self):
        any_checked = any(box.isChecked() for box in self._boxes.values()) or any(
            box.isChecked() and box.isEnabled() for box in self._editor_boxes.values())
        busy = self._thread is not None and self._thread.isRunning()
        self.install_button.setEnabled(any_checked and not busy)
        self.remove_button.setEnabled(any_checked and not busy)

    # --- install / remove -------------------------------------------------
    def selected(self):
        return [shell for shell, box in self._boxes.items() if box.isChecked()]

    def selected_editors(self):
        return [editor for editor, box in self._editor_boxes.items()
                if box.isChecked() and box.isEnabled()]

    def _apply(self, install):
        shells = self.selected()
        editors = self.selected_editors()
        if not shells and not editors:
            return
        lines = []
        if shells:
            try:
                if install:
                    results = self._install_fn(shells, statuses=self._statuses,
                                               codex=self.codex_box.isChecked())
                else:
                    results = self._remove_fn(shells, statuses=self._statuses)
            except Exception as exc:  # noqa: BLE001 - a dialog must not take the tray down
                results = []
                lines.append(_f("The change failed: {error}", error=str(exc)))
            for r in results:
                lines.append(f"{shell_label(r.shell)}: {translate_message(r.message)}")
                if r.backup is not None:
                    lines.append(_f("Copy of the previous file: {path}", path=str(r.backup)))
            if install and any(r.changed for r in results):
                lines.append(_("Open a new terminal window for the change to take effect."))
        if editors:
            fn = self._editor_install_fn if install else self._editor_remove_fn
            try:
                results = fn(editors, statuses=self._editor_statuses)
            except Exception as exc:  # noqa: BLE001
                results = []
                lines.append(_f("The change failed: {error}", error=str(exc)))
            for r in results:
                lines.append(f"{editor_label(r.editor)}: {translate_message(r.message)}")
                if r.backup is not None:
                    lines.append(_f("Copy of the previous file: {path}", path=str(r.backup)))
            if install and any(r.changed for r in results):
                lines.append(_("Restart the editor for the change to take effect."))
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
