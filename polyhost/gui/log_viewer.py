import os
import pathlib

from PyQt5.QtCore import QSize, QFileSystemWatcher
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QMainWindow, QWidget

from polyhost.gui.get_icon import get_icon


class LogViewerDialog(QMainWindow):
    def __init__(self):
        super().__init__()
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

        # OK/Close button
        self.button = QPushButton("Close")
        self.button.clicked.connect(self.close)
        button_layout.addWidget(self.button)

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
