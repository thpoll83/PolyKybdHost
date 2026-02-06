import json
import os
import traceback
import pathlib

from polyhost.gui.key_item import KeyItem
from polyhost.gui.keycode_browser import KeycodeBrowser
from polyhost.gui.zoomable_graphics_view import ZoomableGraphicsView
from polyhost.gui.get_icon import get_icon

from PyQt5.QtWidgets import (
    QMainWindow, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QMessageBox,
    QGraphicsScene, QDialog, QFormLayout
)
from PyQt5.QtGui import QTransform, QGuiApplication, QCursor

KEY_SCALE = 80.0

def parse_kle(json_data):
    """Parse KLE JSON"""
    keys = []
    y_cursor = 0.0
    current_rotation = 0.0
    current_rx = 0.0
    current_ry = 0.0
    
    for row in json_data:
        x_cursor = 0.0
        row_defaults = {}
        
        if 'name' in row:
            continue  # skip the metadata
            
        for item in row:
            if isinstance(item, dict):
                row_defaults.update(item)
                if 'r' in item.keys():
                    current_rotation = float(item['r'])
                if 'rx' in item.keys():
                    current_rx = float(item['rx'])
                    x_cursor = current_rx
                if 'ry' in item.keys():
                    current_ry = float(item['ry'])
                    y_cursor = current_ry
                if 'x' in item.keys():
                    x_cursor += float(item['x'])
                if 'y' in item.keys():
                    y_cursor += float(item['y'])
                continue

            label = str(item)
            w = float(row_defaults.get('w', 1))
            h = float(row_defaults.get('h', 1))
            
            keys.append({
                'x': x_cursor, 'y': y_cursor, 'w': w, 'h': h,
                'r': current_rotation, 'rx': current_rx, 'ry': current_ry,
                'label': label,
                'qmk': label.strip().split('\n')[0] if label else '',
            })
            
            x_cursor += w
            row_defaults.clear()
        
        if current_rotation == 0:
            y_cursor += 1.0
    
    return keys

def build_matrix(keys, tolerance=0.4):
    """Map keys to matrix positions"""
    ys = sorted(set([round(k['y'], 3) for k in keys]))
    xs = sorted(set([round(k['x'], 3) for k in keys]))
    
    rows = []
    for y in ys:
        if not any(abs(r - y) <= tolerance for r in rows):
            rows.append(y)
    rows.sort()
    
    cols = []
    for x in xs:
        if not any(abs(c - x) <= tolerance for c in cols):
            cols.append(x)
    cols.sort()
    
    mapping = {}
    for k in keys:
        row_idx = min(range(len(rows)), key=lambda i: abs(rows[i] - k['y']))
        col_idx = min(range(len(cols)), key=lambda i: abs(cols[i] - k['x']))
        mapping[(row_idx, col_idx)] = k
        k['row'] = row_idx
        k['col'] = col_idx
    
    return len(rows), len(cols), mapping


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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PolyKybd Split72 Layout")
        self.keys = []
        self.mapping = {}
        self.row_count = 0
        self.col_count = 0
        self.init_ui()
        self.load_from_file(os.path.join(pathlib.Path(__file__).parent.parent.resolve(), "res", "polykybd-split72.json"))
        
        self.scale_factor = 1.0
        self._zoom_step = 1.2   # multiplicative step for each + / - press
        self._zoom_min = 0.2
        self._zoom_max = 3.0

    def init_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout()
        
        # Left: keyboard view
        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView(zoom_callback=self.zoom)
        self.view.setScene(self.scene)

        self.keycodes = KeycodeBrowser()
        main_layout.addWidget(self.view, 3)
        main_layout.addWidget(self.keycodes)
        central.setLayout(main_layout)
        self.setCentralWidget(central)
        
        self.set_preferred_size(1800, 900)

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
            self.keys = parse_kle(data)
            self.row_count, self.col_count, self.mapping = build_matrix(self.keys)
            self.render_keys()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load:\n{e}\n{traceback.format_exc()}")
            
    def load_kle(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open KLE JSON", "", "JSON (*.json)")
        self.load_from_file(filename)

    def mouseDoubleClickEvent(self, item):
        dlg = KeyEditDialog(item.key)
        if dlg.exec_():
            item.text.setText(item.key.get('qmk') or item.key.get('label', ''))
            item.update_text_position()
            
    def render_keys(self):
        """Render keys with rotation applied"""
        self.scene.clear()
        
        if not self.keys:
            return
        
        minx = min(k['x'] for k in self.keys)
        miny = min(k['y'] for k in self.keys)
        
        for k in self.keys:
            # Get key properties
            x = k['x'] - minx
            y = k['y'] - miny
            r = k.get('r', 0)
            rx = k.get('rx', 0) - minx
            ry = k.get('ry', 0) - miny
            
            # Create key item
            item = KeyItem(k, KEY_SCALE)
            item.doubleClicked.connect(self.mouseDoubleClickEvent)
            
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
                # No rotation, just position
                transform.translate(x * KEY_SCALE, y * KEY_SCALE)
            
            item.setTransform(transform)
            self.scene.addItem(item)
        
        self.view.setSceneRect(self.scene.itemsBoundingRect())

    def send_to_device(self):
        if not self.mapping:
            QMessageBox.warning(self, "No Layout", "Load a layout first.")
            return

