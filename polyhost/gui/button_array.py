from PyQt5.QtWidgets import (QWidget, QPushButton, QButtonGroup)

from polyhost.gui.flow_layout import FlowLayout


class ButtonArray(QWidget):
    def __init__(self, options):
        super().__init__()

        # 1. Setup Layout
        self.layout = FlowLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)

        # 2. Create the logical group
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)  # Ensures only one is active

        # 3. Dynamically create buttons
        for index, text in enumerate(options):
            btn = QPushButton(text)
            btn.setCheckable(True)  # Allows the "pushed" state

            # Optional: Styling for a clear "Active" look
            btn.setStyleSheet("""
                QPushBuself.grouptton:checked {
                    background-color: #2ecc71;
                    color: white;
                    font-weight: bold;
                    border: 1px solid #27ae60;
                }
            """)
            if index == 0:
                btn.setChecked(True)

            self.group.addButton(btn, index)
            self.layout.addWidget(btn)

        # 4. Connect signal
        self.group.buttonClicked.connect(self.handle_click)

    def handle_click(self, button):
        button.text = "clicked"
