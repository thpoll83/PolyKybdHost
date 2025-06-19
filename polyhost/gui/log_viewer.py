import logging
import os
import pathlib
import subprocess
import sys

from PyQt5.QtCore import QSize, QFileSystemWatcher
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QMainWindow, QWidget

from polyhost.gui.get_icon import get_icon


class LogViewerDialog(QMainWindow):
    def __init__(self):
        super().__init__()
        self.log = logging.getLogger('PolyHost')
        self.setWindowTitle("Log Viewer")
        self.setWindowIcon(get_icon("pcolor.png"))

        # Main vertical layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.layout = QVBoxLayout(central_widget)
        self.layout.setContentsMargins(0, 0, 0, 10)

        # Text area for log display
        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Courier", 10))
        self.layout.addWidget(self.text_edit)

        # Horizontal layout for buttons
        button_layout = QHBoxLayout()

        # Spacer to center buttons
        button_layout.addStretch(1)

        # Open button
        button = QPushButton("Open Folder")
        button.clicked.connect(self.open_file_directory)
        button_layout.addWidget(button)

        # OK/Close button
        button = QPushButton("Close")
        button.clicked.connect(self.close)
        button_layout.addWidget(button)

        # Spacer to center buttons
        button_layout.addStretch(1)

        # Add button layout to main layout
        self.layout.addLayout(button_layout)

        # File watcher
        self.file_watcher = QFileSystemWatcher(self)
        self.path = os.path.join(pathlib.Path(__file__).parent.parent.parent.resolve(), "host_log.txt")
        self.load_log()
        self.file_watcher.addPath(self.path)
        self.file_watcher.fileChanged.connect(self.load_log)

    def sizeHint(self):
        return QSize(1024, 600)

    def load_log(self):

        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                log_content = f.read()
            self.text_edit.setPlainText(log_content)
            self.text_edit.moveCursor(self.text_edit.textCursor().End)
        except Exception as e:
            self.text_edit.setPlainText(f"Failed to load log file: {e}")

    def open_file_directory(self):
        if sys.platform.startswith('darwin'):  # macOS
            subprocess.run(['open', '-R', self.path])
        elif sys.platform.startswith('win'):  # Windows
            subprocess.run(['explorer', '/select,', os.path.normpath(self.path)])
        elif sys.platform.startswith('linux'):  # Linux
            self.reveal_in_linux_file_manager(self.path)
        else:
            logging.warning("Platform %s not supported", sys.platform)

    def reveal_in_linux_file_manager(self, file_path):
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

