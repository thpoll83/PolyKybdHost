import json
import logging
import pathlib
import traceback

from PyQt5.QtGui import QTransform, QGuiApplication, QCursor
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QMessageBox,
    QGraphicsScene, QDialog, QFormLayout
)

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.poly_kybd import PolyKybd
from polyhost.gui.button_array import ButtonArray
from polyhost.gui.get_icon import get_icon
from polyhost.gui.layout_dialog.qmk_keycode_helper import create_nice_name
from polyhost.gui.layout_dialog.renderable_key import RenderableKey
from polyhost.gui.layout_dialog.keycode_browser import KeycodeBrowser
from polyhost.gui.zoomable_graphics_view import ZoomableGraphicsView
from polyhost.kle.kle_praser import parse_kle

KEY_SCALE = 80.0
KLE_DEFINITION = pathlib.Path(__file__).parent.parent.parent.resolve() / "res" / "polykybd-split72.json"

class KeyEditDialog(QDialog):
    """Key editing dialog"""
    def __init__(self, key_dict):
        super().__init__()
        self.setWindowTitle("Edit Key")
        self.key = key_dict
        layout = QFormLayout()
        
        self.qmk_edit = QLineEdit(self.key.get('qmk', ''))
        layout.addRow("QMK Keycode:", self.qmk_edit)
        
        self.label_edit = QTextEdit(self.key.get('label', ''))
        layout.addRow("Visual Label:", self.label_edit)
        
        if self.key.get('r', 0) != 0:
            info = f"Rotation: {self.key['r']}° around ({self.key['rx']}, {self.key['ry']})"
            layout.addRow("Info:", QLabel(info))
        
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self.accept_changes)
        btn_cancel.clicked.connect(self.reject)
        h = QHBoxLayout()
        h.addWidget(btn_ok)
        h.addWidget(btn_cancel)
        layout.addRow(h)
        self.setLayout(layout)
        
        self.setWindowIcon(get_icon("pcolor.png"))
    
    def accept_changes(self):
        self.key['qmk'] = self.qmk_edit.text().strip()
        self.key['label'] = self.label_edit.toPlainText()
        self.accept()


class KbLayoutDialog(QMainWindow):
    def __init__(self, keeb: PolyKybd, settings: DeviceSettings, parent=None):
        super().__init__(parent)
        self.log = logging.getLogger('PolyHost')
        self.settings = settings
        self.setWindowTitle("PolyKybd Split72 Layout")
        self.key_matrix = {}
        self.mapping = {}
        self.row_count = 0
        self.col_count = 0

        self.keeb = keeb
        
        self.scale_factor = 1.0
        self._zoom_step = 1.2   # multiplicative step for each + / - press
        self._zoom_min = 0.2
        self._zoom_max = 3.0
        self.selected_key = None
        self.keys = {}

        self.init_ui()

    def get_selected_key(self):
        return self.selected_key

    def init_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout()
        
        # Left: keyboard view
        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView(zoom_callback=self.zoom)
        self.view.setScene(self.scene)

        self.keycode_browser = KeycodeBrowser()
        self.keycode_browser.keycodeSelected.connect(self.keycodeSelected)

        success, self.num_layers = self.keeb.get_dynamic_layer_count()

        if not success:
            my_options = ["Could not read layers from device"]
        else:
            my_options = []
            for idx in range(self.keeb.num_layers):
                my_options.append(f"{idx}")

        header_layout = QHBoxLayout()
        self.layers = ButtonArray(my_options)
        self.layers.setMaximumHeight(40)
        self.layers.setMaximumHeight(40)
        label = QLabel("Layers:")
        label.setMaximumWidth(50)
        header_layout.addWidget(label)
        header_layout.addWidget(self.layers)
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.view)
        main_layout.addWidget(self.keycode_browser)
        central.setLayout(main_layout)
        self.setCentralWidget(central)
        
        self.set_preferred_size(1800, 1000)
        
        self.load_from_file(str(KLE_DEFINITION))
        
        success, self.key_buffer = self.keeb.get_dynamic_buffer()
        if success:
            self.log.info("Received dynamic key buffer: %d", len(self.key_buffer))
            mapping = self.keycode_browser.get_keycode_to_name_mapping()
            num_keys = len(self.keys)
            max_idx = self.settings.MATRIX_COLUMNS*self.settings.MATRIX_ROWS
            for idx in range(num_keys):
                keycode = self.key_buffer[idx]
                name = mapping[keycode] if keycode in mapping else str(keycode)
                while idx not in self.keys and idx < max_idx:
                    idx += 1
                self.keys[idx].setKeycode(create_nice_name(name), name, keycode)

        else:
            self.log.warning("Failed to receive dynamic key buffer")
        

    # call this from your MainWindow (e.g., at end of init_ui)
    def set_preferred_size(self, pref_w, pref_h):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geom = screen.availableGeometry()

        # if preferred fits, use it; otherwise clamp to available size
        if geom.width() >= pref_w and geom.height() >= pref_h:
            w, h = pref_w, pref_h
        else:
            w = min(pref_w, geom.width())
            h = min(pref_h, geom.height())

        self.resize(w, h)

        # center on that screen's available area
        x = geom.x() + (geom.width() - w) // 2
        y = geom.y() + (geom.height() - h) // 2
        self.move(x, y)
    
    def zoom(self, step):
        """
        step: positive int to zoom in, negative to zoom out.
        Uses multiplicative scaling so zoom is smooth.
        """
        if step == 0:
            return
        if step > 0:
            factor = self._zoom_step ** step
        else:
            factor = (1.0 / self._zoom_step) ** (-step)

        new_scale = self.scale_factor * factor
        new_scale = max(self._zoom_min, min(self._zoom_max, new_scale))
        # compute relative factor to apply to view (delta)
        delta = new_scale / self.scale_factor
        # apply transform
        self.view.scale(delta, delta)
        self.scale_factor = new_scale

        
    def load_from_file(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.row_count, self.col_count, self.key_matrix = parse_kle(data)
            # self.row_count, self.col_count, self.mapping = build_matrix(self.matrix_pos)
            self.render_keys()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load:\n{e}\n{traceback.format_exc()}")
            
    # def load_kle(self):
    #     filename, _ = QFileDialog.getOpenFileName(self, "Open KLE JSON", "", "JSON (*.json)")
    #     self.load_from_file(filename)

    def mouseClickEvent(self, item):
        self.selected_key = item

    def keycodeSelected(self, nice_name, name, keycode, font_size_hint):
        if self.selected_key:
            self.selected_key.setKeycode(nice_name, name, keycode, font_size_hint)

            
    def render_keys(self):
        """Render keys with rotation applied"""
        self.scene.clear()
        
        if not self.key_matrix:
            return
        
        minx = min(p['x'] for p in self.key_matrix.values())
        miny = min(p['y'] for p in self.key_matrix.values())
        
        for name, info in self.key_matrix.items():
            # Get key properties
            x = info['x'] - minx
            y = info['y'] - miny
            r = info.get('r', 0)
            rx = info.get('rx', 0) - minx
            ry = info.get('ry', 0) - miny
            
            # Create key item
            item = RenderableKey(name, info, KEY_SCALE)
            item.pressed.connect(self.mouseClickEvent)
            index = info["row"]*self.settings.MATRIX_COLUMNS+info["col"]
            self.keys[index] = item
            
            # Apply transformations for rotation
            # 1. Translate to position
            # 2. Translate to rotation origin
            # 3. Rotate
            # 4. Translate back
            
            transform = QTransform()
            
            if r != 0:
                # Position relative to rotation origin
                rel_x = (x - rx) * KEY_SCALE
                rel_y = (y - ry) * KEY_SCALE
                
                # Move to rotation origin, rotate, then offset
                transform.translate(rx * KEY_SCALE, ry * KEY_SCALE)
                transform.rotate(r)
                transform.translate(rel_x, rel_y)
            else:
                # Without rotation
                transform.translate(x * KEY_SCALE, y * KEY_SCALE)
            
            item.setTransform(transform)
            self.scene.addItem(item)
        
        self.view.setSceneRect(self.scene.itemsBoundingRect())

    def send_to_device(self):
        if not self.mapping:
            QMessageBox.warning(self, "No Layout", "Load a layout first.")
            return

