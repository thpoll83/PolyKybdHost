from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QTabWidget,
    QVBoxLayout, QScrollArea, )

from polyhost.gui.flow_layout import FlowLayout
from polyhost.gui.layout_dialog.keycode_browser_button import KeycodeBrowserButton
from polyhost.gui.layout_dialog.keycode_composer import KeycodeComposer
from polyhost.gui.layout_dialog.macro_tab import MacroTab
from polyhost.gui.layout_dialog.qmk_keycode_helper import HEADER_FILE, parse_qmk_keycodes, categorize, create_nice_name, \
    category_order, standard_category, last_key_in_standard_category, build_keycode_to_name


class KeycodeBrowser(QWidget):
    keycodeSelected = pyqtSignal(str, str, int, int)  # uint16
    macrosChanged = pyqtSignal()          # relayed from the Macros tab

    def __init__(self, num_layers: int = 9, core=None):
        super().__init__()

        self.keycodes = parse_qmk_keycodes(HEADER_FILE)
        self.codes_to_name = build_keycode_to_name(self.keycodes)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)
        self.tabs = tabs
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

        # Composer tab for building layer-switch / one-shot / tap-hold keycodes.
        self.composer = KeycodeComposer(self.keycodes, num_layers=num_layers)
        self.composer.keycodeSelected.connect(self.keycodeSelected)
        tabs.addTab(self.composer, "Layers && Mods")

        # Macros tab. Like the composer this page BUILDS a keycode rather than listing
        # a fixed set, which is why it belongs here rather than in a window of its own:
        # you write the macro and place it without leaving the view.
        #
        # Only when a core is available AND the firmware is new enough. `core` is a
        # PolyCore in-process and a RemoteCore in client mode, and macro_list() goes
        # over RPC in the latter -- client mode is the default under daemon-by-default,
        # so a device-coupled page that only worked in-process would be unreachable.
        self.macro_tab = None
        if core is not None:
            self.macro_tab = MacroTab(core)
            self.macro_tab.keycodeSelected.connect(self.keycodeSelected)
            self.macro_tab.macrosChanged.connect(self.macrosChanged)
            tabs.addTab(self.macro_tab, "Macros")
            tabs.currentChanged.connect(self._on_tab_changed)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    def _on_tab_changed(self, index: int):
        # Load on first show rather than in __init__: the macro list is three device
        # round trips, and most sessions never open the tab at all.
        if self.macro_tab is not None and self.tabs.widget(index) is self.macro_tab:
            self.macro_tab.reload()

    def set_layer_count(self, num_layers: int):
        """Update the composer's layer range once the device layer count is known."""
        self.composer.set_layer_count(num_layers)

    def show_keycode(self, keycode: int):
        """Reflect a selected key's keycode in the composer.

        For composable keycodes (layer switch / one-shot / mod-tap / layer-tap /
        modified key) the composer is populated and brought to the front so the
        user sees the key's current setup. Plain keys leave the view unchanged.
        """
        if self.composer.load_from_keycode(keycode):
            self.tabs.setCurrentWidget(self.composer)

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
