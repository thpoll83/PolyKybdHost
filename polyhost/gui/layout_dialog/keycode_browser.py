from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QTabWidget,
    QVBoxLayout, QScrollArea, )

from polyhost.gui.flow_layout import FlowLayout
from polyhost.gui.layout_dialog.keycode_browser_button import KeycodeBrowserButton
from polyhost.gui.layout_dialog.qmk_keycode_helper import HEADER_FILE, parse_qmk_keycodes, categorize, create_nice_name, \
    category_order, standard_category, last_key_in_standard_category


class KeycodeBrowser(QWidget):
    keycodeSelected = pyqtSignal(str, str, int, int)  # uint16

    def __init__(self):
        super().__init__()

        self.keycodes = parse_qmk_keycodes(HEADER_FILE)
        self.codes_to_name = {self.keycodes[k]: k for k in self.keycodes}

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)
        self.setMaximumHeight(400)

        CAT_ORDER = category_order()

        categories = {}
        STANDARD = standard_category()
        cat = STANDARD
        LAST_KEY_IN_STD = last_key_in_standard_category()

        for name, keycode in self.keycodes.items():
            if cat != STANDARD:
                cat = categorize(name)
            categories.setdefault(cat, {})[name] = keycode
            if name == LAST_KEY_IN_STD:
                cat = ""

        for category in CAT_ORDER:
            if category not in categories:
                continue

            tabs.addTab(self._build_tab(categories[category]), category)

        for category in sorted(categories):
            if category not in CAT_ORDER:
                tabs.addTab(self._build_tab(categories[category]), category)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        
    def get_name_to_keycode_mapping(self):
        return self.keycodes
    
    def get_keycode_to_name_mapping(self):
        return self.codes_to_name

    def _build_tab(self, cat_keycodes):
        flow_layout = FlowLayout(margin=12, spacing=12)
        container = QWidget()
        container.setLayout(flow_layout)

        for name, keycode in cat_keycodes.items():
            caption = create_nice_name(name)
            btn = KeycodeBrowserButton(caption, name)
            btn.clicked.connect(lambda _, c=caption, k=name, v=keycode, s=btn.get_font_size(): self.on_keycode_clicked(c, k, v, s))
            flow_layout.addWidget(btn)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        container.setContentsMargins(12, 12, 12, 12)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        return scroll

    def on_keycode_clicked(self, nice_name, name, keycode, font_size_hint):
        self.keycodeSelected.emit(nice_name, name, keycode, font_size_hint)
