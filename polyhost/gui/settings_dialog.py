import string
from collections import defaultdict

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QDialogButtonBox,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QSizePolicy,
    QScrollArea
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
        return QSize(640, 480)

    def setup(self, settings_dict):
        self.setWindowIcon(get_icon("pcolor.png"))

        # Outer layout
        main_layout = QVBoxLayout(self)

        title_label = QLabel("Some settings might need a restart to take effect.")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_contents = QWidget()
        scroll_layout = QVBoxLayout(scroll_contents)

        grouped_settings = defaultdict(dict)
        for full_key, value in settings_dict.items():
            if "_" in full_key:
                group, _ = full_key.split("_", 1)
                grouped_settings[group][full_key] = value
            else:
                grouped_settings["General"][full_key] = value

        # For each group, create a QGroupBox with a form layout
        for group_name, group_items in grouped_settings.items():
            group_box = QGroupBox(string.capwords(group_name))
            group_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            group_layout = QFormLayout()
            group_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            group_box.setLayout(group_layout)

            for full_key, value in group_items.items():
                cap = string.capwords(full_key, sep="_").replace("_", " ")
                parts = cap.split(" ",1)
                label = QLabel(parts[1])
                label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                widget = create_editor(value)

                field_container = QWidget()
                field_layout = QHBoxLayout()
                field_layout.setContentsMargins(0, 0, 0, 0)
                field_layout.setAlignment(Qt.AlignRight)  # Right-align the widget inside the field cell
                field_layout.addWidget(widget)
                field_container.setLayout(field_layout)

                group_layout.addRow(label, field_container)
                self.edit_widgets[full_key] = widget

            # form_wrapper_layout.addWidget(group_box)
            scroll_layout.addWidget(group_box)

        scroll_layout.addStretch()  # force groups to fill width
        scroll.setWidget(scroll_contents)
        main_layout.addWidget(scroll)

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
