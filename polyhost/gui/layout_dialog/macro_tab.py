"""The Macros tab of the keycode browser.

Authoring and placement live in the same view on purpose: you write the macro, then
click the key, and the browser is already open on it. It is a tab rather than a separate
window because the browser is already a QTabWidget whose "Layers && Mods" page BUILDS
keycodes rather than just listing them -- a macro page is the same shape.

Two widgets here do real work rather than decorate:

* the meter under the label is in PIXELS, not characters, and the preview beside it
  renders the label through the firmware's own font. The keycap truncates by measured
  width, so a character count would promise letters that will not be drawn -- and the
  preview is also the only place the ASCII-only limit explains itself, since an umlaut
  simply does not appear.
* the storage bar. The bodies share one buffer, so a long macro takes room from the
  others; without it the failure mode is a confusing refusal when you save the ninth
  macro because the third is enormous.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPixmap
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from polyhost.services import macro_label as ml

# QK_MACRO_0. The firmware owns this range outright -- via.c is the only core dispatcher
# for it and VIA_ENABLE is unset -- so a macro key is an ordinary keycode assignment.
QK_MACRO = 0x7700

PREVIEW_SCALE = 2


class MacroTab(QWidget):
    """Lists the keyboard's macros, edits one, and hands the keycode to the grid."""

    keycodeSelected = pyqtSignal(str, str, int, int)

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self._info: dict = {}
        self._macros: list[dict] = []
        self._current = 0
        self._font = None
        self._loaded = False

        # A missing font only costs the preview, so the tab still edits macros on a
        # machine without the firmware checkout beside it.
        try:
            self._font = ml.load_nano_font(ml.default_font_dir())
        except Exception:
            self._font = None

        outer = QHBoxLayout(self)

        self.list = QListWidget()
        self.list.setMaximumWidth(190)
        self.list.currentRowChanged.connect(self._on_select)
        outer.addWidget(self.list)

        right = QVBoxLayout()
        outer.addLayout(right, 1)

        right.addWidget(self._caption("LABEL"))
        label_row = QHBoxLayout()
        self.label_edit = QLineEdit()
        self.label_edit.setMaxLength(ml.LABEL_MAX_CHARS)
        self.label_edit.textChanged.connect(self._on_label_changed)
        label_row.addWidget(self.label_edit, 1)

        self.preview = QLabel()
        self.preview.setFixedSize(ml.PANEL_W * PREVIEW_SCALE, ml.PANEL_H * PREVIEW_SCALE)
        self.preview.setToolTip("How the keycap will look")
        label_row.addWidget(self.preview)
        right.addLayout(label_row)

        self.width_meter = QProgressBar()
        self.width_meter.setRange(0, ml.PANEL_W)
        self.width_meter.setTextVisible(True)
        right.addWidget(self.width_meter)

        right.addWidget(self._caption("WHAT IT TYPES"))
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("tom@example.com")
        right.addWidget(self.text_edit)

        self.body_note = QLabel()
        self.body_note.setWordWrap(True)
        right.addWidget(self.body_note)

        # Not a scary modal, just the truth: people will store passwords here anyway.
        warn = QLabel("Stored unencrypted on the keyboard, and readable by anything "
                      "that can talk to it over USB.")
        warn.setWordWrap(True)
        warn.setStyleSheet("color: palette(mid);")
        right.addWidget(warn)

        right.addStretch(1)

        right.addWidget(self._caption("SHARED STORAGE"))
        self.storage = QProgressBar()
        self.storage.setTextVisible(True)
        right.addWidget(self.storage)

        buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save macro")
        self.save_btn.clicked.connect(self._on_save)
        buttons.addWidget(self.save_btn)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._on_clear)
        buttons.addWidget(self.clear_btn)
        self.assign_btn = QPushButton("Use on selected key")
        self.assign_btn.clicked.connect(self._on_assign)
        buttons.addWidget(self.assign_btn)
        buttons.addStretch(1)
        right.addLayout(buttons)

        # Debounced so a fast typist does not repaint per keystroke.
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(80)
        self._preview_timer.timeout.connect(self._repaint_preview)

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _caption(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: palette(mid); font-size: 10px; letter-spacing: 1px;")
        return lbl

    def _error(self, title: str, msg: str):
        QMessageBox.warning(self, title, str(msg))

    # -- loading ------------------------------------------------------------

    def reload(self):
        """Pull every macro from the keyboard. Cheap enough to call on tab show."""
        ok, info = self.core.macro_list()
        if not ok:
            self.setEnabled(False)
            self.body_note.setText(str(info))
            return
        self.setEnabled(True)
        self._loaded = True
        self._info = info
        self._macros = info["macros"]
        self.label_edit.setMaxLength(info.get("label_len", ml.LABEL_MAX_CHARS))

        row = self.list.currentRow()
        self.list.blockSignals(True)
        self.list.clear()
        for m in self._macros:
            # By LABEL, not by index: picking `push` is the point of having labels.
            title = m["label"] or f"M{m['id']} (empty)"
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, m["id"])
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.list.setCurrentRow(row if 0 <= row < len(self._macros) else 0)
        self._update_storage()

    def _update_storage(self):
        cap = self._info.get("capacity", 0)
        used = self._info.get("used", 0)
        self.storage.setRange(0, max(cap, 1))
        self.storage.setValue(used)
        self.storage.setFormat(f"{used} of {cap} bytes  ·  %p%")

    # -- selection ----------------------------------------------------------

    def _on_select(self, row: int):
        if not (0 <= row < len(self._macros)):
            return
        self._current = row
        m = self._macros[row]
        self.label_edit.setText(m["label"])
        if m["text"] is None:
            # Not expressible as text. Showing it as text and saving would silently
            # drop the chords and delays, so the field is locked instead.
            self.text_edit.setText("")
            self.text_edit.setEnabled(False)
            self.body_note.setText(
                f"{len(m['steps'])} steps including keys or delays — not plain text, "
                f"so it can only be edited with <tt>polyctl macro</tt> for now.")
        else:
            self.text_edit.setEnabled(True)
            self.text_edit.setText(m["text"])
            self.body_note.setText(f"{m['bytes']} bytes")

    # -- label preview ------------------------------------------------------

    def _on_label_changed(self, _text: str):
        self._preview_timer.start()

    def _repaint_preview(self):
        text = self.label_edit.text()
        if self._font is None:
            self.width_meter.setFormat("no font — preview unavailable")
            self.width_meter.setValue(0)
            return
        r = ml.fit(text, self._font)
        self.width_meter.setValue(min(r.full_width, ml.PANEL_W))
        self.width_meter.setFormat(f"{r.full_width} / {ml.PANEL_W} px")
        # Amber past the panel: the label is still accepted, it is just cut.
        self.width_meter.setStyleSheet(
            "QProgressBar::chunk { background: #B4690E; }" if r.truncated else "")
        self.preview.setPixmap(self._render(r.text))

    def _render(self, label: str) -> QPixmap:
        """Draw the keycap the way render_macro_key() composes it."""
        img = QImage(ml.PANEL_W, ml.PANEL_H, QImage.Format_RGB32)
        img.fill(QColor(8, 10, 14))
        lit = QColor(207, 231, 245).rgb()
        if label and self._font is not None:
            self._blit(img, label, lit)
        return QPixmap.fromImage(
            img.scaled(ml.PANEL_W * PREVIEW_SCALE, ml.PANEL_H * PREVIEW_SCALE,
                       Qt.IgnoreAspectRatio, Qt.FastTransformation))

    def _blit(self, img: QImage, label: str, lit: int):
        f = self._font
        # Mirror the firmware's placement: pin the caption's lowest lit pixel to the
        # last row, centre it horizontally on its own ink box.
        x = 0
        xmn = xmx = ymx = None
        for ch in label:
            g = self._glyph(ord(ch))
            if g is None:
                continue
            if g["width"] and g["height"]:
                l, r = x + g["xOffset"], x + g["xOffset"] + g["width"] - 1
                b = g["yOffset"] + g["height"] - 1
                xmn = l if xmn is None else min(xmn, l)
                xmx = r if xmx is None else max(xmx, r)
                ymx = b if ymx is None else max(ymx, b)
            x += g["xAdvance"]
        if xmn is None:
            return
        x0 = (ml.PANEL_W - (xmx - xmn + 1)) // 2 - xmn
        baseline = ml.PANEL_H - 1 - ymx

        x = x0
        for ch in label:
            g = self._glyph(ord(ch))
            if g is None:
                continue
            bo, cb = g["bitmapOffset"], (g["height"] + 7) >> 3   # column-native
            for xx in range(g["width"]):
                col = bo + xx * cb
                for yy in range(g["height"]):
                    if f.bitmap[col + (yy >> 3)] & (1 << (yy & 7)):
                        vx, vy = x + g["xOffset"] + xx, baseline + g["yOffset"] + yy
                        if 0 <= vx < ml.PANEL_W and 0 <= vy < ml.PANEL_H:
                            img.setPixel(vx, vy, lit)
            x += g["xAdvance"]

    def _glyph(self, cp: int):
        f = self._font
        if f is None or not (f.first <= cp <= f.last):
            return None
        g = f.glyphs[cp - f.first]
        if g["width"] == 0 and g["height"] == 0 and g["xAdvance"] == 0:
            return None
        return g

    # -- actions ------------------------------------------------------------

    def _on_save(self):
        if not self._macros:
            return
        m = self._macros[self._current]
        params = {"label": self.label_edit.text()}
        if self.text_edit.isEnabled():
            params["text"] = self.text_edit.text()
        ok, msg = self.core.macro_set(m["id"], **params)
        if not ok:
            self._error("Could not save the macro", msg)
            return
        self.reload()

    def _on_clear(self):
        if not self._macros:
            return
        m = self._macros[self._current]
        ok, msg = self.core.macro_clear(m["id"])
        if not ok:
            self._error("Could not clear the macro", msg)
            return
        self.reload()

    def _on_assign(self):
        """Hand the macro's keycode to the grid, exactly as a keycode button does."""
        if not self._macros:
            return
        m = self._macros[self._current]
        name = f"QK_MACRO_{m['id']}"
        caption = m["label"] or f"M{m['id']}"
        self.keycodeSelected.emit(caption, name, QK_MACRO + m["id"], 0)
