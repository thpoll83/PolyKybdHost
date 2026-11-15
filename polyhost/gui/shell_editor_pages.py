"""The Terminals and Editors pages of Integrations (gui/integrations_dialog.py),
the front end for :mod:`polyhost.services.shell_title` and
:mod:`polyhost.services.editor_plugins`.

Terminals lists each shell this computer has (bash, zsh, PowerShell 7, Windows
PowerShell 5.1) with its startup file and whether the title line is in it.
Editors lists each editor (Vim, Neovim, Emacs, GDB, FreeCAD) with the folder or init
file its plugin goes to. The status runs on a thread because asking PowerShell
for ``$PROFILE`` starts a PowerShell process.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox

from polyhost.gui.integrations_dialog import RowsPage
from polyhost.gui.ui_kit import WrapLabel
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


class TerminalsPage(RowsPage):
    """``status_fn``, ``install_fn`` and ``remove_fn`` are the service's
    functions; tests pass fakes."""

    APPLY_ON_THREAD = True

    def __init__(self, parent=None, status_fn=None, install_fn=None, remove_fn=None):
        super().__init__(_("Terminals"), _(
            "The keyboard shows the shortcuts of a program running in a terminal "
            "(nano, for example) only when the terminal's window title names the "
            "program. bash, zsh and PowerShell do not do this without setup.\n\n"
            "Install adds one line to the startup file of each selected shell, "
            "between two marker comments, and first saves a copy of the file next "
            "to it. Remove deletes those lines. The change applies to terminal "
            "windows opened afterwards. To change the Codex option, select the "
            "shells and press Install again."), parent)
        self._status_fn = status_fn or shell_title.status
        self._install_fn = install_fn or shell_title.install
        self._remove_fn = remove_fn or shell_title.remove
        self._statuses = []
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
        self.extra.addWidget(self.codex_box)
        self.refresh()

    def status_error_text(self, exc):
        return _f("The shells could not be checked: {error}", error=str(exc))

    def read_status(self):
        return list(self._status_fn())

    def _on_codex_clicked(self):
        self._codex_touched = True

    def show_status(self, statuses):
        self._statuses = list(statuses)
        if not self._codex_touched:
            self.codex_box.setChecked(any(getattr(st, "codex", False) for st in self._statuses))
        old = {k: b.isChecked() for k, b in self.boxes().items()}
        self.clear_rows()
        info = []
        for st in self._statuses:
            if st.state == shell_title.STATE_NO_SETUP:
                info.append(_f("{shell}: shows the command without setup.",
                               shell=shell_label(st.shell)))
                continue
            if st.state == shell_title.STATE_NOT_PRESENT:
                continue
            default = (st.state == shell_title.STATE_STALE
                       or (st.state == shell_title.STATE_NOT_INSTALLED
                           and shell_title.default_selection(st)))
            self.add_row(st.shell, shell_label(st.shell),
                         str(st.rc_path) if st.rc_path is not None else "",
                         state_text(st), checked=old.get(st.shell, default))
        if not self.boxes():
            info.insert(0, _("No bash, zsh or PowerShell was found on this computer."))
        self.set_info("\n".join(info))

    def before_apply(self, install):
        self._codex_for_apply = self.codex_box.isChecked()

    def apply(self, install, keys):
        # Runs on the worker thread: the checkbox was read in before_apply().
        lines = []
        if install:
            results = self._install_fn(keys, statuses=self._statuses,
                                       codex=self._codex_for_apply)
        else:
            results = self._remove_fn(keys, statuses=self._statuses)
        for r in results:
            lines.append(f"{shell_label(r.shell)}: {translate_message(r.message)}")
            if r.backup is not None:
                lines.append(_f("Copy of the previous file: {path}", path=str(r.backup)))
        if install and any(r.changed for r in results):
            lines.append(_("Open a new terminal window for the change to take effect."))
        return lines


class EditorsPage(RowsPage):
    """``status_fn``, ``install_fn`` and ``remove_fn`` are the service's
    functions; tests pass fakes. ``report_settings`` is the (port, token) of
    the report listener, read from the settings file when None."""

    APPLY_ON_THREAD = True

    def __init__(self, parent=None, status_fn=None, install_fn=None, remove_fn=None,
                 report_settings=None):
        super().__init__(_("Editors"), _(
            "Vim, Neovim and Emacs tell the keyboard their mode (Normal or Insert "
            "mode, the Org or Dired keys) only with the PolyKybd plugin. GDB shows "
            "whether the program runs or waits at the prompt only with it.\n\n"
            "Install copies the plugin from this installation to where the program "
            "loads it. For Emacs and GDB it also adds lines that load the plugin to the "
            "init file, between two marker comments, and first saves a copy of the file. "
            "When this app is updated, it copies the new plugin files at its next "
            "start. Restart the program for the change to take effect."), parent)
        self._status_fn = status_fn or editor_plugins.status
        self._install_fn = install_fn or editor_plugins.install
        self._remove_fn = remove_fn or editor_plugins.remove
        self._report_settings = report_settings
        self._statuses = []
        freecad_intro = WrapLabel(_(
            "FreeCAD shows the keys of the active workbench only with the PolyKybd "
            "add-on. Install copies it to FreeCAD's Mod folder."))
        freecad_intro.setWordWrap(True)
        self.extra.addWidget(freecad_intro)
        self.settings_note = WrapLabel()
        self.settings_note.setWordWrap(True)
        self.settings_note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.settings_note.hide()
        self.extra.addWidget(self.settings_note)
        self.refresh()

    def status_error_text(self, exc):
        return _f("The editors could not be checked: {error}", error=str(exc))

    def read_status(self):
        return list(self._status_fn())

    def show_status(self, statuses):
        self._statuses = list(statuses)
        old = {k: b.isChecked() for k, b in self.boxes().items()}
        self.clear_rows()
        for st in self._statuses:
            if st.state == editor_plugins.STATE_NOT_PRESENT:
                continue
            self.add_row(st.editor, editor_label(st.editor),
                         str(st.target) if st.target is not None else "",
                         editor_state_text(st),
                         checked=old.get(st.editor, editor_plugins.default_selection(st)),
                         enabled=st.state != editor_plugins.STATE_NO_SOURCE)
        if not self.boxes():
            self.add_message(_("No Vim, Neovim or Emacs was found on this computer."))
        note = ""
        if self.boxes():
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
        self.settings_note.setText(note)
        self.settings_note.setVisible(bool(note))

    def apply(self, install, keys):
        lines = []
        fn = self._install_fn if install else self._remove_fn
        # No cached statuses: the service reads the files again, so a plugin
        # file changed by hand since the page was shown is found (and kept)
        # instead of being deleted on a stale "Set up".
        results = fn(keys, statuses=None)
        for r in results:
            lines.append(f"{editor_label(r.editor)}: {translate_message(r.message)}")
            if r.backup is not None:
                lines.append(_f("Copy of the previous file: {path}", path=str(r.backup)))
        if install and any(r.changed for r in results):
            lines.append(_("Restart the editor for the change to take effect."))
        return lines
