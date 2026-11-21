"""Integrations: the PolyKybd parts this app installs into other programs.

One dialog, laid out like Settings: a list of categories on the left, the
category's page on the right. Each page installs and removes its own parts:

- AI agents: the hooks in each agent's config file (services/agents/hook_install.py)
- Terminals: the title line in each shell's startup file (services/shell_title.py)
- Editors: the Vim, Neovim, Emacs and GDB plugins and the FreeCAD add-on (services/editor_plugins.py)
- Browser: the browser extension folder (services/browser_extension.py)

All of it is a local file change on the computer the app runs on. It needs no
keyboard and no daemon, so it works the same in client mode and in the
forwarder, which installs for the computer it reports from.
"""
from __future__ import annotations

import difflib

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCursor, QGuiApplication, QPalette
from PyQt5.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QListWidget, QMessageBox,
                             QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
                             QVBoxLayout, QWidget)

from polyhost.gui import section_colors, section_style
from polyhost.gui.settings_dialog import (_STYLE as SETTINGS_STYLE, MIN_DIALOG_SIZE,
                                          SIDEBAR_WIDTH, initial_dialog_size,
                                          minimum_dialog_size)
from polyhost.gui.ui_kit import (CARD_STYLE, WrapLabel, card, muted, px, set_button_icon,
                                 style_button_box)
from polyhost.i18n import _, _f

AGENTS = "agents"
TERMINALS = "terminals"
EDITORS = "editors"
BROWSER = "browser"
# Sidebar order.
CATEGORIES = (AGENTS, TERMINALS, EDITORS, BROWSER)


class _StatusThread(QThread):
    done = pyqtSignal(object)

    def __init__(self, status_fn, parent=None):
        super().__init__(parent)
        self._status_fn = status_fn

    def run(self):
        try:
            result = self._status_fn()
        except Exception as exc:  # noqa: BLE001 - shown on the page, never raised into Qt
            result = exc
        self.done.emit(result)


class RowsPage(QWidget):
    """A page of rows: one per program, each with a checkbox, the file or
    folder that changes, and its state below. Install and Remove act on the
    ticked rows; the rows ARE the confirmation, because each names its file.

    A subclass implements read_status() (runs on a thread), show_status()
    (fills the rows with add_row()) and apply(install, keys) (returns the
    result lines)."""

    # The first column of the grid, so the paths of every page start at the same x.
    NAME_COLUMN_W = 170
    # Run apply() on the worker thread. Only for a page whose apply() shows no
    # dialog: it may start a program (GDB, PowerShell) that takes seconds.
    APPLY_ON_THREAD = False

    def __init__(self, title, intro, parent=None):
        super().__init__(parent)
        self._boxes = {}
        self._removable = set()
        self._thread = None
        self.apply_keys = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        head = QLabel(title)
        head.setObjectName("settingsSectionTitle")
        lay.addWidget(head)
        self.intro = muted(WrapLabel(intro))
        self.intro.setWordWrap(True)
        lay.addWidget(self.intro)

        self.grid = QGridLayout()
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnMinimumWidth(0, px(self.NAME_COLUMN_W))
        self.grid.setVerticalSpacing(2)
        lay.addLayout(self.grid)
        # Subclasses add their own widgets (an option, a note) here.
        self.extra = QVBoxLayout()
        self.extra.setSpacing(8)
        lay.addLayout(self.extra)

        self._checking = muted(QLabel(_("Checking…")))
        lay.addWidget(self._checking)
        self.info = WrapLabel()
        self.info.setWordWrap(True)
        self.info.hide()
        lay.addWidget(self.info)
        self.results = WrapLabel()
        self.results.setWordWrap(True)
        self.results.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.results.hide()
        lay.addWidget(self.results)

        row = QHBoxLayout()
        row.addStretch(1)
        self.install_button = section_style.mark_accent_button(
            set_button_icon(QPushButton(_("Install")), "install"))
        # The section colour (gui/section_style.py), set by the dialog; rows
        # added later (the status arrives on a thread) take it in add_row.
        self.accent_color = None
        self.remove_button = set_button_icon(QPushButton(_("Remove")), "delete")
        # noinspection PyUnresolvedReferences
        self.install_button.clicked.connect(lambda: self._apply(True))
        # noinspection PyUnresolvedReferences
        self.remove_button.clicked.connect(lambda: self._apply(False))
        row.addWidget(self.install_button)
        row.addWidget(self.remove_button)
        lay.addLayout(row)
        lay.addStretch(1)

    # --- for subclasses -----------------------------------------------------
    def read_status(self):
        raise NotImplementedError

    def show_status(self, result):
        raise NotImplementedError

    def apply(self, install, keys):
        raise NotImplementedError

    def status_error_text(self, exc):
        return _f("The check failed: {error}", error=str(exc))

    def before_apply(self, install):
        """Runs on the GUI thread before apply(). A page whose apply() runs on
        the worker thread reads its widgets here: Qt widgets must not be
        touched from another thread."""

    def clear_rows(self):
        self._boxes = {}
        self._removable = set()
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def add_row(self, key, label, path, state, checked, enabled=True, removable=True):
        """One program: its checkbox, the file that changes, the state below."""
        row = self.grid.rowCount() if self._boxes else 0
        box = QCheckBox(label)
        section_style.accent_checkbox(box, self.accent_color)
        box.setProperty("sectionAccentDone", True)
        box.setChecked(checked)
        box.setEnabled(enabled)
        # noinspection PyUnresolvedReferences
        box.toggled.connect(self.update_buttons)
        self._boxes[key] = box
        if removable:
            self._removable.add(key)
        path_label = QLabel(path)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # A long path is cut at the edge, not widened into a sideways scroll
        # bar; the tooltip has all of it.
        path_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        path_label.setToolTip(path)
        # The state goes under the path: three columns squeezed a long path
        # into a clipped sliver.
        state_label = muted(WrapLabel(state))
        state_label.setWordWrap(True)
        state_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.grid.addWidget(box, row, 0, Qt.AlignTop)
        self.grid.addWidget(path_label, row, 1)
        self.grid.addWidget(state_label, row + 1, 1)
        return box

    def add_message(self, text):
        """A line across the grid (nothing found, or the check failed)."""
        label = WrapLabel(text)
        label.setWordWrap(True)
        self.grid.addWidget(label, self.grid.rowCount(), 0, 1, 2)

    def set_info(self, text):
        self.info.setText(text)
        self.info.setVisible(bool(text))

    def boxes(self):
        return dict(self._boxes)

    def selected(self):
        """The ticked rows that can be changed."""
        return [k for k, b in self._boxes.items() if b.isChecked() and b.isEnabled()]

    # --- status ---------------------------------------------------------------
    def busy(self):
        return self._thread is not None and self._thread.isRunning()

    def refresh(self):
        """Read the state again on a thread; the rows are rebuilt when it ends."""
        if self.busy():
            return
        self._checking.show()
        self.install_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self._thread = _StatusThread(self.read_status, self)
        # noinspection PyUnresolvedReferences
        self._thread.done.connect(self._on_status)
        # `done` is emitted from run(), while the thread still counts as
        # running; `finished` comes after run() has returned.
        # noinspection PyUnresolvedReferences
        self._thread.finished.connect(self.update_buttons)
        self._thread.start()

    def reopen(self):
        """The dialog opens again: the files may have changed since."""
        self.results.hide()
        self.refresh()

    def _on_status(self, result):
        self._checking.hide()
        if isinstance(result, Exception):
            self.set_info(self.status_error_text(result))
            self.update_buttons()
            return
        self.show_status(result)
        self.update_buttons()

    def update_buttons(self):
        chosen = self.selected()
        busy = self.busy()
        self.install_button.setEnabled(bool(chosen) and not busy)
        self.remove_button.setEnabled(
            any(k in self._removable for k in chosen) and not busy)

    def _apply(self, install, keys=None):
        """Install or remove the ticked rows, or only ``keys`` (a row's own
        button)."""
        keys = self.selected() if keys is None else list(keys)
        if not install:
            keys = [k for k in keys if k in self._removable]
        if not keys or self.busy():
            return
        # The rows this Install or Remove acts on, for before_apply().
        self.apply_keys = keys
        self.before_apply(install)
        if self.APPLY_ON_THREAD:
            self._checking.show()
            self.install_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            self._thread = _StatusThread(lambda: self.apply(install, keys), self)
            # noinspection PyUnresolvedReferences
            self._thread.done.connect(self._on_applied)
            self._thread.start()
            return
        try:
            lines = self.apply(install, keys)
        except Exception as exc:  # noqa: BLE001 - a dialog must not take the tray down
            lines = exc
        self._on_applied(lines)

    def _on_applied(self, lines):
        self._checking.hide()
        if isinstance(lines, Exception):
            lines = [_f("The change failed: {error}", error=str(lines))]
        if lines is not None:   # None: cancelled
            self.show_results(lines)
        # After `done` the thread may still count as running for a moment;
        # refresh() waits for it so the two threads never overlap.
        if self._thread is not None and self._thread.isRunning():
            self._thread.wait()
        if lines is not None:
            self.refresh()
        else:
            self.update_buttons()

    def show_results(self, lines):
        self.results.setText("\n".join(lines))
        self.results.setVisible(bool(lines))


# --- AI agents ------------------------------------------------------------------

AGENT_LABELS = (("claude-code", "Claude Code"), ("codex", "Codex"), ("copilot", "Copilot CLI"),
                ("gemini", "Gemini CLI"), ("qwen", "Qwen Code"), ("opencode", "OpenCode"))


def agent_label(vendor):
    """The agent's name (product names, not translated)."""
    return dict(AGENT_LABELS).get(vendor, vendor)


def agent_state_text(st):
    from polyhost.services.agents import hook_install as hi
    if st.state == hi.STATE_INSTALLED:
        return _("Set up")
    if st.state == hi.STATE_OUTDATED:
        return _("Set up for another copy of the app, or an older version. "
                 "Install updates it.")
    if st.state == hi.STATE_CONFLICT:
        return st.detail
    if st.state == hi.STATE_ERROR:
        return _f("The file cannot be read: {error}", error=st.detail)
    return _("Not set up")


def _diff(changes):
    return "\n\n".join(
        "\n".join(difflib.unified_diff(c.before.splitlines(), c.after.splitlines(),
                                       c.path, c.path, lineterm=""))
        for c in changes)


class AgentsPage(RowsPage):
    """The hooks that report an agent's state to its key. ``note()``, when
    given, returns a text shown after hooks were written (the forwarder says
    what the keyboard computer needs). ``status_fn``, ``plan_fn``,
    ``apply_fn`` and ``confirm`` are the service's functions and a Yes/No box;
    tests pass fakes."""

    def __init__(self, log, note=None, status_fn=None, plan_fn=None, apply_fn=None,
                 confirm=None, parent=None):
        super().__init__(_("AI agents"), _(
            "An agent's key shows whether the agent works, waits for you or is "
            "finished only when the agent runs the PolyKybd hook.\n\n"
            "Install adds the hooks to the agent's settings file. Your own hooks and "
            "settings are kept, and a copy of each file is saved as "
            "<file>.polykybd.bak. Remove takes out only the PolyKybd hooks. Restart "
            "the agent for the change to take effect."), parent)
        from polyhost.services.agents import hook_install as hi
        self._hi = hi
        self.log = log
        self._note = note
        self._status_fn = status_fn or (lambda: [hi.status(v) for v in hi.VENDORS])
        self._plan_fn = plan_fn or (lambda vendor, install: hi.plan(vendor, install=install))
        self._apply_fn = apply_fn or hi.apply
        self._confirm = confirm or self._ask
        self._statuses = {}
        self.refresh()

    def read_status(self):
        return list(self._status_fn())

    def show_status(self, statuses):
        hi = self._hi
        old = {k: b.isChecked() for k, b in self.boxes().items()}
        self.clear_rows()
        self._statuses = {st.vendor: st for st in statuses}
        for st in statuses:
            self.add_row(st.vendor, agent_label(st.vendor), st.path, agent_state_text(st),
                         checked=old.get(st.vendor, st.state == hi.STATE_OUTDATED),
                         enabled=st.state not in (hi.STATE_CONFLICT, hi.STATE_ERROR),
                         removable=st.has_ours)

    @staticmethod
    def _ask(text, details):
        box = QMessageBox(QMessageBox.Question, _("AI agents"), text)
        box.setDetailedText(details)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        return box.exec_() == QMessageBox.Yes

    def apply(self, install, keys):
        changes = []
        lines = []
        for vendor in keys:
            try:
                changes.extend(self._plan_fn(vendor, install))
            except (ValueError, OSError) as e:
                lines.append(f"{agent_label(vendor)}: {e}")
        if not changes:
            return lines or [_("Nothing to change.")]
        files = ", ".join(c.path for c in changes)
        text = (_f("Write the PolyKybd hooks into {files}? Your own hooks are kept, and "
                   "a copy of each file is saved as <file>.polykybd.bak.", files=files)
                if install else
                _f("Remove the PolyKybd hooks from {files}? Your own hooks are kept, and "
                   "a copy of each file is saved as <file>.polykybd.bak.", files=files))
        if not self._confirm(text, _diff(changes)):
            return None
        try:
            done = self._apply_fn(changes)
        except OSError as e:
            return lines + [_f("The change failed: {error}", error=str(e))]
        self.log.info("Agent hooks %s: %s", "written" if install else "removed",
                      ", ".join(done))
        lines += [_f("Changed: {path}", path=path) for path in done]
        note = self._note() if (install and self._note) else ""
        if note:
            lines.append(note)
        elif done:
            lines.append(_("Restart the agent for the change to take effect."))
        return lines


# --- the dialog -------------------------------------------------------------------

def category_title(category):
    return {AGENTS: _("AI agents"), TERMINALS: _("Terminals"), EDITORS: _("Editors"),
            BROWSER: _("Browser")}[category]


class IntegrationsDialog(QDialog):
    """``categories`` lists the pages to show. ``page_factories`` maps a
    category to a function that builds its page; tests pass fakes."""

    def __init__(self, log, parent=None, categories=CATEGORIES, agent_note=None,
                 page_factories=None):
        super().__init__(parent)
        self.log = log
        self.setWindowTitle(_("Integrations"))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(SETTINGS_STYLE + CARD_STYLE)
        factories = {
            AGENTS: lambda: AgentsPage(log, note=agent_note),
            TERMINALS: _terminals_page,
            EDITORS: _editors_page,
            BROWSER: lambda: _browser_page(log),
        }
        factories.update(page_factories or {})
        self.categories = [c for c in categories if c in factories]
        self.pages = {}

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        main.addLayout(body, 1)

        side = QWidget()
        side.setFixedWidth(px(SIDEBAR_WIDTH))
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(12, 14, 8, 12)
        self.nav = QListWidget()
        self.nav.setObjectName("settingsNav")
        self.nav.setFrameShape(QFrame.NoFrame)
        self.nav.setWordWrap(True)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        section_style.style_nav(self.nav)
        side_lay.addWidget(self.nav, 1)
        body.addWidget(side)

        self.stack = QStackedWidget()
        dark = section_style.dialog_is_dark(self)
        for index, category in enumerate(self.categories):
            page = factories[category]()
            self.pages[category] = page
            # The page sits in a coloured section like a Settings section
            # (gui/section_style.py). The section's band shows the page's own
            # title, so the page's heading is hidden.
            color = section_colors.slot_color(index, dark)
            heading = page.findChild(QLabel, "settingsSectionTitle")
            title = heading.text() if heading is not None else category_title(category)
            if heading is not None:
                heading.hide()
            section = section_style.ColorSection(title, color)
            # The page's content sits in a card on the base colour (white or
            # black), like a Settings group and a tutorial entry. A page with
            # cards of its own (Browser) is not wrapped again. The stretch
            # below keeps the card as tall as its content.
            if page.findChildren(QFrame, "uiCard"):
                section.body_layout.addWidget(page)
            else:
                content, content_lay = card()
                content_lay.setContentsMargins(px(14), px(12), px(14), px(12))
                content_lay.addWidget(page)
                section.body_layout.addWidget(content)
                section.body_layout.addStretch(1)
            page.accent_color = color
            section_style.adopt(page, color)
            # Each page scrolls on its own: a long result list or a small
            # screen must not push the Install button out of reach.
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            holder = QWidget()
            holder_lay = QVBoxLayout(holder)
            holder_lay.setContentsMargins(16, 14, 16, 16)
            holder_lay.addWidget(section)
            scroll.setWidget(holder)
            self.stack.addWidget(scroll)
            section_style.add_nav_item(self.nav, category_title(category), color)
        # noinspection PyUnresolvedReferences
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        body.addWidget(self.stack, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(16, 8, 16, 12)
        note = QLabel(_("Changes apply to the program after it restarts."))
        note.setWordWrap(True)
        pal = note.palette()
        pal.setColor(QPalette.WindowText, pal.color(QPalette.Disabled, QPalette.WindowText))
        note.setPalette(pal)
        footer.addWidget(note, 1)
        buttons = style_button_box(QDialogButtonBox(QDialogButtonBox.Close))
        # noinspection PyUnresolvedReferences
        buttons.rejected.connect(self.close)
        footer.addWidget(buttons)
        main.addLayout(footer)

        if self.categories:
            self.nav.setCurrentRow(0)
        self._fit_to_screen()

    def sizeHint(self):
        return MIN_DIALOG_SIZE

    def _fit_to_screen(self):
        """The Settings window's size: half the screen the cursor is on."""
        screen = (QGuiApplication.screenAt(QCursor.pos())
                  or QGuiApplication.primaryScreen())
        if screen is None:
            self.setMinimumSize(px(MIN_DIALOG_SIZE.width()), px(MIN_DIALOG_SIZE.height()))
            return
        available = screen.availableGeometry().size()
        minimum = minimum_dialog_size(available)
        self.setMinimumSize(minimum)
        self.resize(initial_dialog_size(available, minimum))

    def current_category(self):
        row = self.nav.currentRow()
        return self.categories[row] if 0 <= row < len(self.categories) else None

    def show_category(self, category):
        if category in self.categories:
            self.nav.setCurrentRow(self.categories.index(category))

    def reopen(self):
        """The tray opens the kept dialog again: read every page's files again."""
        for page in self.pages.values():
            if hasattr(page, "reopen"):
                page.reopen()


def _terminals_page():
    from polyhost.gui.shell_editor_pages import TerminalsPage
    return TerminalsPage()


def _editors_page():
    from polyhost.gui.shell_editor_pages import EditorsPage
    return EditorsPage()


def _browser_page(log):
    from polyhost.gui.browser_extension_page import BrowserPage
    return BrowserPage(log)


def open_integrations(owner, attr="integrations_dialog", category=None, **kwargs):
    """Open the dialog kept on `owner` (the tray app or the forwarder), at
    `category` when given. One window at a time; it is not modal."""
    from polyhost.gui.dialog_util import bring_to_front
    dialog = getattr(owner, attr, None)
    if dialog is None:
        dialog = IntegrationsDialog(owner.log, **kwargs)
        setattr(owner, attr, dialog)
    elif not dialog.isVisible():
        dialog.reopen()
    if category is not None:
        dialog.show_category(category)
    dialog.show()
    bring_to_front(dialog)
    return dialog
