import logging
import os
import re
import subprocess
import sys

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (QHBoxLayout, QMainWindow, QPlainTextEdit,
                              QPushButton, QTabWidget, QVBoxLayout, QWidget)

from polyhost.gui.get_icon import get_icon
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


class LogViewerDialog(QMainWindow):
    def __init__(self, log_files):
        super().__init__()
        self.log = logging.getLogger('PolyHost')
        self.setWindowTitle("Log Viewer")
        self.setWindowIcon(get_icon("pcolor.png"))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.layout = QVBoxLayout(central_widget)
        self.layout.setContentsMargins(0, 0, 0, 10)

        self.tab_widget = QTabWidget(self)
        self.layout.addWidget(self.tab_widget)

        self.log_text = {}
        self.log_files = log_files
        # Keep highlighters alive — QSyntaxHighlighter is GC'd if not referenced.
        self._highlighters = []

        for tab_name in log_files:
            log_text = QPlainTextEdit(self)
            log_text.setReadOnly(True)
            log_text.setLineWrapMode(QPlainTextEdit.NoWrap)
            log_text.setFont(QFont("Courier", 10))

            self._highlighters.append(_LogHighlighter(log_text.document()))

            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.addWidget(log_text)
            self.tab_widget.addTab(tab, tab_name)
            self.log_text[tab_name] = log_text

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

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
