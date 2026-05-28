import html
import logging
import os
import re
import subprocess
import sys

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QMainWindow, QWidget, QTabWidget

from polyhost.gui.get_icon import get_icon
from polyhost.util.log_util import LEVEL_HEX_COLORS

# Matches "[timestamp] LEVELNAME" at the start of a formatted log line.
# Continuation lines (e.g. tracebacks) won't match and inherit the previous color.
_LEVEL_NAME_TO_NO = {logging.getLevelName(lvl): lvl for lvl in LEVEL_HEX_COLORS}
_LEVEL_RE = re.compile(
    r"^\[[^\]]+\]\s+(" + "|".join(re.escape(n) for n in _LEVEL_NAME_TO_NO) + r")\b"
)


class LogViewerDialog(QMainWindow):
    def __init__(self, log_files):
        super().__init__()
        self.log = logging.getLogger('PolyHost')
        self.setWindowTitle("Log Viewer")
        self.setWindowIcon(get_icon("pcolor.png"))

        # Main vertical layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.layout = QVBoxLayout(central_widget)
        self.layout.setContentsMargins(0, 0, 0, 10)

         # Tab widget to hold multiple tabs
        self.tab_widget = QTabWidget(self)
        self.layout.addWidget(self.tab_widget)

        self.log_text = {}
        self.log_files = log_files

        for tab_name in log_files:
            # a read-only QTextEdit (HTML for per-line colouring)
            log_text = QTextEdit(self)
            log_text.setReadOnly(True)
            log_text.setLineWrapMode(QTextEdit.NoWrap)
            log_text.setFont(QFont("Courier", 10))
        
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.addWidget(log_text)
            self.tab_widget.addTab(tab, tab_name)
            self.log_text[tab_name] = log_text

        # Horizontal layout for buttons
        button_layout = QHBoxLayout()

        # Spacer to center buttons
        button_layout.addStretch(1)

        # Open button
        button = QPushButton("Open Folder")
        button.clicked.connect(self.open_file_directory)
        button_layout.addWidget(button)

        # OK/Close button
        button = QPushButton("Reload")
        button.clicked.connect(self.load_log)
        button_layout.addWidget(button)


        # OK/Close button
        button = QPushButton("Close")
        button.clicked.connect(self.close)
        button_layout.addWidget(button)

        # Spacer to center buttons
        button_layout.addStretch(1)

        # Add button layout to main layout
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
            text_edit.setHtml(self._colorize(log_content))
            text_edit.moveCursor(text_edit.textCursor().End)

    @staticmethod
    def _colorize(log_content: str) -> str:
        """Wrap each log line in a coloured <span> based on its level.

        Continuation lines (no "[time] LEVEL" prefix) inherit the previous
        line's colour so multi-line records stay visually grouped.
        """
        out = ['<pre style="margin:0; font-family:Courier; white-space:pre-wrap;">']
        current_color = None
        for line in log_content.splitlines():
            m = _LEVEL_RE.match(line)
            if m:
                current_color = LEVEL_HEX_COLORS.get(_LEVEL_NAME_TO_NO[m.group(1)])
            escaped = html.escape(line)
            if current_color:
                out.append(f'<span style="color:{current_color};">{escaped}</span>')
            else:
                out.append(escaped)
            out.append("<br>")
        out.append("</pre>")
        return "".join(out)


    def open_file_directory(self):
        file = list(self.log_files.values())[0] # maybe also the focus tab is possible
        
        if sys.platform.startswith('darwin'):  # macOS
            subprocess.run(['open', '-R', file])
        elif sys.platform.startswith('win'):  # Windows
            subprocess.run(['explorer', '/select,', os.path.normpath(file)])
        elif sys.platform.startswith('linux'):  # Linux
            self.reveal_in_linux_file_manager(file)
        else:
            logging.warning("Platform %s not supported", sys.platform)

    @staticmethod
    def reveal_in_linux_file_manager(file_path):
        file_path = os.path.abspath(file_path)
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

        # Priority mapping
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

        # Add universal fallback options
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

        # Last fallback: open directory only
        dir_path = os.path.dirname(file_path)
        subprocess.run(['xdg-open', dir_path])

