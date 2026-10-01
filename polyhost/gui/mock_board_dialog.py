"""The mock keyboard's keycaps, drawn on the board (Developer menu).

Shows what the emulated keyboard (device/mock_firmware.py) holds on each
keycap after the host's last overlay send, under a chosen modifier -- the
pictures the real board would light up, decoded from the reports the host
actually wrote. A wrong-key or wrong-modifier image is visible at a glance
instead of after a hardware round.

Reads `core.mock_keycaps()`, so it works the same in-process and as a
`--connect` client over RPC. The geometry is the layout editor's (the KLE);
which keycode each key shows comes from the mock's layer 0, so an edit made in
the layout editor moves the picture too.
"""
from __future__ import annotations

import base64
import os

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QGraphicsScene,
                             QHBoxLayout, QLabel, QPushButton, QVBoxLayout)

from polyhost.device.keys import Modifier
from polyhost.gui.layout_dialog.qmk_keycode_helper import (HEADER_FILE, build_keycode_to_name,
                                                           describe_keycode, parse_qmk_keycodes)
from polyhost.gui.layout_dialog.renderable_key import RenderableKey, key_transform
from polyhost.gui.zoomable_graphics_view import ZoomableGraphicsView
from polyhost.services.board_layout import physical_keys

KEY_SCALE = 80.0
REFRESH_MS = 500
FRAME_W, FRAME_H = 72, 40


def bitmap_to_image(packed: bytes, lit: bool = True) -> QImage:
    """A 360-byte 1-bit keycap frame as a grey QImage (white ink on black, or
    dimmed while the keyboard has overlays switched off)."""
    import numpy as np
    bits = np.unpackbits(np.frombuffer(packed, dtype=np.uint8))[:FRAME_W * FRAME_H]
    pixels = (bits.reshape(FRAME_H, FRAME_W) * (255 if lit else 90)).astype(np.uint8)
    data = pixels.tobytes()
    return QImage(data, FRAME_W, FRAME_H, FRAME_W, QImage.Format_Grayscale8).copy()


class MockBoardDialog(QDialog):

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("Mock keyboard")
        self.resize(1400, 560)
        self._names = build_keycode_to_name(parse_qmk_keycodes(HEADER_FILE))
        self._last = None

        self.status = QLabel("")
        self.modifier = QComboBox()
        for m in Modifier:
            self.modifier.addItem(m.name.replace("_", "+").title(), m.value)
        # noinspection PyUnresolvedReferences
        self.modifier.currentIndexChanged.connect(self.refresh)
        self.live = QCheckBox("Live")
        self.live.setChecked(True)
        save = QPushButton("Save PNGs…")
        # noinspection PyUnresolvedReferences
        save.clicked.connect(self.save_pngs)

        top = QHBoxLayout()
        top.addWidget(QLabel("Modifier:"))
        top.addWidget(self.modifier)
        top.addWidget(self.live)
        top.addStretch(1)
        top.addWidget(save)

        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView(self.scene)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.status)

        self.keys = []
        self._build_board()
        self.timer = QTimer(self)
        # noinspection PyUnresolvedReferences
        self.timer.timeout.connect(lambda: self.live.isChecked() and self.refresh())
        self.timer.start(REFRESH_MS)
        self.refresh()

    def _build_board(self):
        keys = physical_keys()
        if not keys:
            return
        minx = min(k["x"] for k in keys)
        miny = min(k["y"] for k in keys)
        for k in keys:
            item = RenderableKey("", {"w": k["w"] or 1, "h": k["h"] or 1}, KEY_SCALE)
            item.setTransform(key_transform(k, minx, miny, KEY_SCALE))
            item.setFlag(item.ItemIsSelectable, False)
            self.scene.addItem(item)
            self.keys.append((k, item))
        self.view.setSceneRect(self.scene.itemsBoundingRect())

    def refresh(self):
        # Runs from a repeating QTimer: PyQt5 turns an exception in a slot into
        # qFatal(), so one bad tick (a daemon gone mid-refresh) would take the
        # whole tray down. Guard here, inside the slot.
        try:
            self._refresh()
        except Exception as e:   # noqa: BLE001 -- see above
            self.status.setText(f"Refresh failed: {e}")

    def _refresh(self):
        modifier = self.modifier.currentData() or 0
        ok, payload = self.core.mock_keycaps(modifier)
        if not ok:
            self.status.setText(str(payload))
            return
        self._last = payload
        lit = payload["overlays_enabled"]
        images = payload["images"]
        base = payload["base_layer"]
        shown = 0
        for k, item in self.keys:
            keycode = base.get(f"{k['row']},{k['col']}", k["keycode"] or 0)
            encoded = images.get(str(keycode))
            if encoded:
                item.set_keycap(QPixmap.fromImage(
                    bitmap_to_image(base64.b64decode(encoded), lit)))
                shown += 1
            else:
                item.set_keycap(None)
                main, badge, color = describe_keycode(keycode, self._names) if keycode else ("", "", None)
                item.set_display(main, badge, color, 9 if len(main) < 5 else 7)
        stats = payload["stats"]
        refused = payload["refused"]
        self.status.setText(
            f"{'Primary' if payload['primary'] else 'Secondary'} mock, protocol "
            f"v{payload['protocol']} · overlays {'on' if lit else 'OFF'} · {shown} keycap(s) "
            f"with an overlay · received: {stats['image_reports']} image, "
            f"{stats['fill_reports']} fill, {stats['mapping_reports']} mapping, "
            f"{stats['control_reports']} control report(s)"
            + (f" · ⚠ {len(refused)} refused: {refused[-1]}" if refused else ""))

    def save_pngs(self):
        """Every overlay the keyboard holds under the current modifier, one PNG
        per keycode -- the files the old "Dump Mock Bitmaps" wrote, but by what
        each keycap SHOWS rather than by raw pool slot."""
        if not self._last:
            return
        out = QFileDialog.getExistingDirectory(self, "Save the mock's keycaps to")
        if not out:
            return
        mod = self._last["modifier"]
        for kc, encoded in self._last["images"].items():
            image = bitmap_to_image(base64.b64decode(encoded))
            image.save(os.path.join(out, f"kc0x{int(kc):02x}_mod{mod}.png"))
        self.status.setText(f"Saved {len(self._last['images'])} PNG(s) to {out}")

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)


__all__ = ["MockBoardDialog", "bitmap_to_image"]
