import logging
import os
import subprocess
import sys

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QVBoxLayout, QPlainTextEdit, QHBoxLayout, QPushButton, QMainWindow, QWidget, QTabWidget

from polyhost.gui.get_icon import get_icon


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
            # a read-only QPlainTextEdit
            log_text = QPlainTextEdit(self)
            log_text.setReadOnly(True)
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
            try:
                with open(tab_log_file_name, encoding='utf-8') as f:
                    log_content = f.read()
                text_edit = self.log_text[tab_name]
                text_edit.setPlainText(log_content)
                text_edit.moveCursor(text_edit.textCursor().End)
            except Exception as e:
                self.log_text[tab_name].setPlainText(f"Failed to load log file '{tab_log_file_name}': {e}")


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

