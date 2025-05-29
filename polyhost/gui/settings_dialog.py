from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QDialogButtonBox,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QWidget, QVBoxLayout, QHBoxLayout
)

from polyhost.gui.get_icon import get_icon


def create_editor(value):
    if isinstance(value, bool):
        checkbox = QCheckBox()
        checkbox.setChecked(value)
        return checkbox
    elif isinstance(value, int):
        spinbox = QSpinBox()
        spinbox.setMaximum(10_000)  # Adjust as needed
        spinbox.setValue(value)
        return spinbox
    elif isinstance(value, float):
        doublebox = QDoubleSpinBox()
        doublebox.setDecimals(3)
        doublebox.setMaximum(1_000.0)
        doublebox.setValue(value)
        return doublebox
    else:  # string fallback
        line_edit = QLineEdit()
        line_edit.setText(str(value))
        return line_edit


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PolyKybd Settings")
        self.edit_widgets = {}

    def sizeHint(self):
        return QSize(400, 200)

    def setup(self, settings_dict):
        self.setWindowIcon(get_icon("pcolor.png"))

        # Outer layout
        main_layout = QVBoxLayout(self)

        title_label = QLabel("Some settings might need a restart to take effect.")
        title_label.setAlignment(Qt.AlignCenter)
        # title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        main_layout.addWidget(title_label)

        # Wrapper widget to center form layout
        form_wrapper = QWidget()
        form_wrapper_layout = QFormLayout()
        form_wrapper.setLayout(form_wrapper_layout)

        for key, value in settings_dict.items():
            label = QLabel(key)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            widget = create_editor(value)
            form_wrapper_layout.addRow(label, widget)
            self.edit_widgets[key] = widget

        # Center the form layout in the dialog
        centered_layout = QHBoxLayout()
        centered_layout.addStretch()
        centered_layout.addWidget(form_wrapper)
        centered_layout.addStretch()
        main_layout.addLayout(centered_layout)

        # Add buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons, alignment=Qt.AlignCenter)

    def get_updated_settings(self):
        updated = {}
        for key, widget in self.edit_widgets.items():
            if isinstance(widget, QCheckBox):
                updated[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                updated[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                updated[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                updated[key] = widget.text()
        return updated
