import logging
import os
import pathlib
import subprocess
import sys

from PyQt5.QtCore import QSize, QFileSystemWatcher
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QVBoxLayout, QPlainTextEdit, QHBoxLayout, QPushButton, QMainWindow, QWidget, QTabWidget

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

         # Tab widget to hold multiple tabs
        self.tab_widget = QTabWidget(self)
        self.layout.addWidget(self.tab_widget)

        # First tab with a read-only QPlainTextEdit
        self.text_host_log = QPlainTextEdit(self)
        self.text_host_log.setReadOnly(True)
        self.text_host_log.setFont(QFont("Courier", 10))

        tab1 = QWidget()
        tab1_layout = QVBoxLayout(tab1)
        tab1_layout.addWidget(self.text_host_log)
        self.tab_widget.addTab(tab1, "PolyHost Log")

        # Second tab with another read-only QPlainTextEdit
        self.text_polykybd_console = QPlainTextEdit(self)
        self.text_polykybd_console.setReadOnly(True)
        self.text_polykybd_console.setFont(QFont("Courier", 10))

        tab2 = QWidget()
        tab2_layout = QVBoxLayout(tab2)
        tab2_layout.addWidget(self.text_polykybd_console)
        self.tab_widget.addTab(tab2, "PolyKybd Console Log")

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

        # File watcher
        self.path = os.path.join(pathlib.Path(__file__).parent.parent.parent.resolve(), "host_log.txt")
        self.console_path = os.path.join(pathlib.Path(__file__).parent.parent.parent.resolve(), "polykybd_console.txt")
        self.load_log()

    def sizeHint(self):
        return QSize(1600, 1000)

    def load_log(self):
        try:
            with open(self.path, encoding='utf-8') as f:
                log_content = f.read()
            self.text_host_log.setPlainText(log_content)
            self.text_host_log.moveCursor(self.text_host_log.textCursor().End)
        except Exception as e:
            self.text_host_log.setPlainText(f"Failed to host load log file: {e}")

        try:
            with open(self.console_path, encoding='utf-8') as f:
                log_content = f.read()
            self.text_polykybd_console.setPlainText(log_content)
            self.text_polykybd_console.moveCursor(self.text_polykybd_console.textCursor().End)
        except Exception as e:
            self.text_polykybd_console.setPlainText(f"Failed to polykybd load log file: {e}")

    def open_file_directory(self):
        if sys.platform.startswith('darwin'):  # macOS
            subprocess.run(['open', '-R', self.path])
        elif sys.platform.startswith('win'):  # Windows
            subprocess.run(['explorer', '/select,', os.path.normpath(self.path)])
        elif sys.platform.startswith('linux'):  # Linux
            self.reveal_in_linux_file_manager(self.path)
        else:
            logging.warning("Platform %s not supported", sys.platform)

    @staticmethod
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

