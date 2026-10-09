import logging
import os
import re
import subprocess
import sys

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import (QColor, QFont, QKeySequence, QSyntaxHighlighter, QTextCharFormat,
                         QTextCursor)
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPlainTextEdit,
                              QPushButton, QShortcut, QTabWidget, QTextEdit, QVBoxLayout,
                              QWidget)

from polyhost.services import problem_scan
from polyhost.services.log_bundle import LOG_SOURCES
from polyhost.util.log_util import LEVEL_HEX_COLORS

# Matches "[timestamp] LEVELNAME" at the start of a formatted log line.
# Continuation lines (e.g. tracebacks) won't match and inherit the previous color.
_LEVEL_NAME_TO_NO = {logging.getLevelName(lvl): lvl for lvl in LEVEL_HEX_COLORS}
_LEVEL_RE = re.compile(
    r"^\[[^\]]+\]\s+(" + "|".join(re.escape(n) for n in _LEVEL_NAME_TO_NO) + r")\b"
)

# Encode each level as a block-state integer so continuation lines inherit color.
# State 0 means "no color"; states 1..N correspond to levels in LEVEL_HEX_COLORS.
_LEVEL_TO_STATE = {lvl: i + 1 for i, lvl in enumerate(LEVEL_HEX_COLORS)}

# Pre-built QTextCharFormat per state — reused across every highlightBlock() call.
_STATE_TO_FORMAT: dict[int, QTextCharFormat] = {}
for _state, _lvl in ((s, l) for l, s in _LEVEL_TO_STATE.items()):
    _fmt = QTextCharFormat()
    _fmt.setForeground(QColor(LEVEL_HEX_COLORS[_lvl]))
    _STATE_TO_FORMAT[_state] = _fmt


class _LogHighlighter(QSyntaxHighlighter):
    """Syntax highlighter that colours each line by its log level.

    Runs lazily — Qt only calls highlightBlock() for visible/dirty blocks,
    so opening large log files is near-instant.
    """

    def highlightBlock(self, text: str) -> None:
        m = _LEVEL_RE.match(text)
        if m:
            state = _LEVEL_TO_STATE[_LEVEL_NAME_TO_NO[m.group(1)]]
        else:
            # Inherit previous block's state (-1 on the very first block → 0 = no color)
            state = max(self.previousBlockState(), 0)

        fmt = _STATE_TO_FORMAT.get(state)
        if fmt:
            self.setFormat(0, len(text), fmt)
        self.setCurrentBlockState(state)


# The keyboard console's file name: its lines carry no level, so they need their own
# highlighter (below). Taken from LOG_SOURCES rather than spelled out again here.
_CONSOLE_FILENAME = next(s.filename for s in LOG_SOURCES if s.label == "keyboard-console")

_SEVERITY_TO_FORMAT: dict[str, QTextCharFormat] = {}
for _sev, _lvl in ((problem_scan.SEVERITY_ERROR, logging.ERROR),
                   (problem_scan.SEVERITY_WARNING, logging.WARNING)):
    _fmt = QTextCharFormat()
    _fmt.setForeground(QColor(LEVEL_HEX_COLORS[_lvl]))
    _SEVERITY_TO_FORMAT[_sev] = _fmt


class _ConsoleHighlighter(QSyntaxHighlighter):
    """Colours keyboard console lines that the problem scan would report.

    Console lines are `[timestamp] text` with no level, so _LogHighlighter
    leaves them all plain. Each line is classified on its own: there are no
    continuation lines to inherit a colour, and inheriting would paint every line
    after a warning. problem_scan.classify_console_line() decides, so the viewer
    and the problem dialog agree on what counts."""

    def highlightBlock(self, text: str) -> None:
        fmt = _SEVERITY_TO_FORMAT.get(problem_scan.classify_console_line(text))
        if fmt:
            self.setFormat(0, len(text), fmt)


# Search hits: every match tinted, the current one a stronger shade. Black text on a
# light fill reads in both themes, whatever colour the log line itself carries.
_MATCH_FORMAT = QTextCharFormat()
_MATCH_FORMAT.setBackground(QColor("#fff176"))
_MATCH_FORMAT.setForeground(QColor("#000000"))
_CURRENT_FORMAT = QTextCharFormat()
_CURRENT_FORMAT.setBackground(QColor("#ffb300"))
_CURRENT_FORMAT.setForeground(QColor("#000000"))
# A cap on how many matches are tinted. Counting is not capped, but thousands of
# extra selections make the editor sluggish on a long log and help nobody.
_MAX_TINTED = 2000


class LogViewerDialog(QMainWindow):
    def __init__(self, log_files, collect_cb=None):
        super().__init__()
        self.log = logging.getLogger('PolyHost')
        self._collect_cb = collect_cb
        self.setWindowTitle("Log Viewer")
        # Inherits QApplication's window icon — see settings_dialog: both tray
        # apps open this one, and they wear different marks.

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.layout = QVBoxLayout(central_widget)
        self.layout.setContentsMargins(0, 0, 0, 10)

        # Search: case-insensitive, over the visible tab. Enter / Shift+Enter step
        # through the matches, Ctrl+F focuses the field, Esc clears it.
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(6, 6, 6, 0)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search (Ctrl+F)")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(lambda _text: self._run_search())
        self.search_edit.returnPressed.connect(self.find_next)
        search_layout.addWidget(self.search_edit, 1)
        prev_button = QPushButton("Previous")
        prev_button.clicked.connect(self.find_previous)
        search_layout.addWidget(prev_button)
        next_button = QPushButton("Next")
        next_button.clicked.connect(self.find_next)
        search_layout.addWidget(next_button)
        self.search_count = QLabel("", self)
        self.search_count.setMinimumWidth(110)
        search_layout.addWidget(self.search_count)
        self.layout.addLayout(search_layout)
        QShortcut(QKeySequence.Find, self, activated=self._focus_search)
        QShortcut(QKeySequence(Qt.SHIFT + Qt.Key_Return), self.search_edit,
                  activated=self.find_previous)
        QShortcut(QKeySequence(Qt.SHIFT + Qt.Key_Enter), self.search_edit,
                  activated=self.find_previous)
        QShortcut(QKeySequence(Qt.Key_Escape), self.search_edit,
                  activated=self.search_edit.clear)

        self.tab_widget = QTabWidget(self)
        self.layout.addWidget(self.tab_widget)
        self.tab_widget.currentChanged.connect(lambda _idx: self._run_search())
        self._matches: list[QTextCursor] = []
        self._match_index = -1

        self.log_text = {}
        self.log_files = log_files
        # Keep highlighters alive — QSyntaxHighlighter is GC'd if not referenced.
        self._highlighters = []

        for tab_name, path in log_files.items():
            log_text = QPlainTextEdit(self)
            log_text.setReadOnly(True)
            log_text.setLineWrapMode(QPlainTextEdit.NoWrap)
            log_text.setFont(QFont("Courier", 10))

            is_console = os.path.basename(path) == _CONSOLE_FILENAME
            highlighter = _ConsoleHighlighter if is_console else _LogHighlighter
            self._highlighters.append(highlighter(log_text.document()))

            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.addWidget(log_text)
            self.tab_widget.addTab(tab, tab_name)
            self.log_text[tab_name] = log_text

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        # Reading a log here is one thing; handing it to someone else is the
        # other half, and this is where a user looks for it.
        if collect_cb is not None:
            button = QPushButton("Collect Logs...")
            button.setToolTip("Save all logs as a .zip, or copy them to the clipboard")
            button.clicked.connect(collect_cb)
            button_layout.addWidget(button)

        button = QPushButton("Open Folder")
        button.clicked.connect(self.open_file_directory)
        button_layout.addWidget(button)

        button = QPushButton("Reload")
        button.clicked.connect(self.load_log)
        button_layout.addWidget(button)

        button = QPushButton("Close")
        button.clicked.connect(self.close)
        button_layout.addWidget(button)

        button_layout.addStretch(1)
        self.layout.addLayout(button_layout)

        self.load_log()

    def sizeHint(self):
        return QSize(1600, 1000)

    def load_log(self):
        for tab_name, tab_log_file_name in self.log_files.items():
            text_edit = self.log_text[tab_name]
            try:
                with open(tab_log_file_name, encoding='utf-8') as f:
                    log_content = f.read()
            except Exception as e:
                text_edit.setPlainText(f"Failed to load log file '{tab_log_file_name}': {e}")
                continue
            text_edit.setPlainText(log_content)
            text_edit.moveCursor(QTextCursor.End)
        # Reload replaces every document, so the old match cursors point nowhere.
        if hasattr(self, "search_edit"):
            self._run_search()

    # ---- search ----------------------------------------------------------------
    def _current_editor(self) -> QPlainTextEdit | None:
        idx = self.tab_widget.currentIndex()
        if idx < 0:
            return None
        return self.log_text.get(self.tab_widget.tabText(idx))

    def _focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _run_search(self) -> None:
        """Find every match of the search text in the visible tab and tint them.

        The current match is the first one at or after the cursor, so a search
        typed while reading starts from there. With no match after the cursor it
        is the last one before it: a log opens scrolled to the end, so a fresh
        search lands on the NEWEST match, which is usually the one wanted."""
        for editor in self.log_text.values():
            editor.setExtraSelections([])
        self._matches = []
        self._match_index = -1
        editor = self._current_editor()
        needle = self.search_edit.text()
        if editor is None or not needle:
            self.search_count.setText("")
            return
        doc = editor.document()
        cursor = doc.find(needle, 0)   # no FindCaseSensitively flag: case-insensitive
        while not cursor.isNull():
            self._matches.append(cursor)
            cursor = doc.find(needle, cursor)
        if not self._matches:
            self.search_count.setText("No matches")
            return
        here = editor.textCursor().selectionStart()
        self._match_index = next((i for i, m in enumerate(self._matches)
                                  if m.selectionStart() >= here), len(self._matches) - 1)
        self._show_match()

    def _show_match(self) -> None:
        editor = self._current_editor()
        if editor is None or not self._matches:
            return
        selections = []
        for i, m in enumerate(self._matches[:_MAX_TINTED]):
            sel = QTextEdit.ExtraSelection()
            sel.cursor = m
            sel.format = _CURRENT_FORMAT if i == self._match_index else _MATCH_FORMAT
            selections.append(sel)
        current = self._matches[self._match_index]
        if self._match_index >= _MAX_TINTED:
            sel = QTextEdit.ExtraSelection()
            sel.cursor = current
            sel.format = _CURRENT_FORMAT
            selections.append(sel)
        editor.setExtraSelections(selections)
        editor.setTextCursor(current)
        editor.ensureCursorVisible()
        self.search_count.setText(f"{self._match_index + 1} of {len(self._matches)}")

    def find_next(self) -> None:
        if not self._matches:
            self._run_search()
            return
        self._match_index = (self._match_index + 1) % len(self._matches)
        self._show_match()

    def find_previous(self) -> None:
        if not self._matches:
            self._run_search()
            return
        self._match_index = (self._match_index - 1) % len(self._matches)
        self._show_match()

    def open_file_directory(self):
        file = list(self.log_files.values())[0]

        if sys.platform.startswith('darwin'):
            subprocess.run(['open', '-R', file])
        elif sys.platform.startswith('win'):
            subprocess.run(['explorer', '/select,', os.path.normpath(file)])
        elif sys.platform.startswith('linux'):
            self.reveal_in_linux_file_manager(file)
        else:
            logging.warning("Platform %s not supported", sys.platform)

    @staticmethod
    def reveal_in_linux_file_manager(file_path):
        file_path = os.path.abspath(file_path)
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

        preferred = []
        if "kde" in desktop:
            preferred = [
                ['dolphin', '--select', file_path],
                ['nautilus', '--select', file_path],
            ]
        elif "gnome" in desktop or "unity" in desktop:
            preferred = [
                ['nautilus', '--select', file_path],
                ['dolphin', '--select', file_path],
            ]
        elif "xfce" in desktop:
            preferred = [
                ['thunar', file_path],
                ['nautilus', '--select', file_path],
            ]
        elif "cinnamon" in desktop:
            preferred = [
                ['nemo', '--no-desktop', '--browser', '--select', file_path],
            ]
        elif "mate" in desktop:
            preferred = [
                ['caja', '--no-desktop', '--browser', '--select', file_path],
            ]

        fallback = [
            ['nautilus', '--select', file_path],
            ['dolphin', '--select', file_path],
            ['nemo', '--no-desktop', '--browser', '--select', file_path],
            ['caja', '--no-desktop', '--browser', '--select', file_path],
            ['thunar', file_path],
        ]

        for cmd in preferred + fallback:
            try:
                subprocess.Popen(cmd)
                return
            except FileNotFoundError:
                continue

        dir_path = os.path.dirname(file_path)
        subprocess.run(['xdg-open', dir_path])
