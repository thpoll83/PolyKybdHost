"""Qt dialog for the font-pack *extend* round-trip: build glyphs from a TTF/OTF,
preview them as keycaps, and splice them into a bundle to save or flash.

Ties fontgen (render) + fontpack_extend (splice/encode) to a form.  fontgen and
its deps are imported lazily on Build, so the dialog opens without the optional
[fontgen] extra (it just tells you to install it).  Flashing is an injected
callback ``flash_cb(bundle_index:int, plyf_bytes:bytes)`` — None hides the Flash
button, so the dialog is fully usable (and testable) with no device.

Reached from the inspector's "Extend…" button; standalone:
``python -m polyhost.gui.fontpack_extend_dialog``.
"""
from __future__ import annotations

import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QSpinBox,
    QComboBox, QCheckBox, QPushButton, QScrollArea, QFileDialog, QMessageBox,
    QApplication, QWidget,
)

from polyhost.services import fontpack_reader as fpr
from polyhost.gui.fontpack_inspector_dialog import _pil_l_to_pixmap, load_shipped_packs

_DITHER = ["fs", "stucki", "bayer", "threshold", "random"]


class FontPackExtendDialog(QDialog):
    def __init__(self, res_dir: str | None = None, flash_cb=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PolyKybd — Build / Extend Font Pack")
        self.resize(900, 640)
        self._flash_cb = flash_cb
        self._built = None          # (bundle_index, new PackFont)
        # Only valid bundles are splice targets — load_shipped_packs may yield
        # (label, Exception) placeholders for ones that failed to decode.
        self._packs = [(label, p) for label, p in load_shipped_packs(res_dir)
                       if isinstance(p, fpr.Pack)]

        root = QHBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form, 0)

        self._src = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        srow = QHBoxLayout(); srow.addWidget(self._src, 1); srow.addWidget(browse)
        sw = QWidget(); sw.setLayout(srow)
        form.addRow("Source font (.ttf/.otf)", sw)

        self._mode = QComboBox(); self._mode.addItems(["Codepoint range", "HarfBuzz sequence"])
        self._mode.currentIndexChanged.connect(self._sync_mode)
        form.addRow("Mode", self._mode)
        self._first = QLineEdit("0x2600"); self._last = QLineEdit("0x2610")
        form.addRow("Range first (hex)", self._first)
        form.addRow("Range last (hex)", self._last)
        self._seq = QLineEdit("1F1E9 1F1EA"); self._seq.setEnabled(False)
        form.addRow("Sequence (hex cps; , = glyph)", self._seq)
        self._seq_first = QLineEdit("0xE000"); self._seq_first.setEnabled(False)
        form.addRow("Sequence base -F (hex)", self._seq_first)

        self._size = self._spin(8, 200, 20); form.addRow("Size -s", self._size)
        self._gray = QCheckBox("Grayscale / colour (-g)")
        self._gray.stateChanged.connect(self._sync_mode)
        form.addRow("", self._gray)
        self._dither = QComboBox(); self._dither.addItems(_DITHER); self._dither.setEnabled(False)
        form.addRow("Dither -D", self._dither)
        self._norm = QCheckBox("Normalize -N"); self._inv = QCheckBox("Invert -I")
        self._edge = QCheckBox("Edge-preserve -E")
        for c in (self._norm, self._inv, self._edge):
            form.addRow("", c)
        self._outline = self._spin(0, 8, 0); form.addRow("Outline -O", self._outline)
        self._rsize = self._spin(0, 200, 0); form.addRow("Render size -r (0=off)", self._rsize)
        self._yadv = self._spin(0, 200, 0); form.addRow("yAdvance -Y (0=off)", self._yadv)
        self._maxw = self._spin(0, 200, 0); form.addRow("Max width -W (0=off)", self._maxw)

        self._bundle = QComboBox()
        for label, pack in self._packs:
            self._bundle.addItem(label, pack)
        self._bundle.currentIndexChanged.connect(self._default_index)
        form.addRow("Target bundle", self._bundle)
        self._gidx = self._spin(0, 65535, 0)
        form.addRow("Global font index", self._gidx)

        btns = QHBoxLayout()
        self._build_btn = QPushButton("Build / Preview"); self._build_btn.clicked.connect(self._build)
        self._save_btn = QPushButton("Save .plyf…"); self._save_btn.clicked.connect(self._save)
        self._save_btn.setEnabled(False)
        btns.addWidget(self._build_btn); btns.addWidget(self._save_btn)
        if flash_cb is not None:
            self._flash_btn = QPushButton("Flash to device"); self._flash_btn.clicked.connect(self._flash)
            self._flash_btn.setEnabled(False)
            btns.addWidget(self._flash_btn)
        btns.addStretch(1)
        form.addRow(btns)

        right = QVBoxLayout()
        self._status = QLabel("Pick a font, set options, then Build / Preview.")
        self._status.setWordWrap(True)
        right.addWidget(self._status)
        self._preview = QLabel(); self._preview.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll = QScrollArea(); scroll.setWidget(self._preview); scroll.setWidgetResizable(False)
        scroll.setStyleSheet("background:#000;")
        right.addWidget(scroll, 1)
        root.addLayout(right, 1)

        self._default_index()
        if not self._packs:
            self._build_btn.setEnabled(False)
            self._status.setText("No valid shipped bundles available to extend.")

    # ---- helpers ----
    @staticmethod
    def _spin(lo, hi, val):
        s = QSpinBox(); s.setRange(lo, hi); s.setValue(val); return s

    def _sync_mode(self, *_):
        seq = self._mode.currentIndex() == 1
        for w in (self._seq, self._seq_first):
            w.setEnabled(seq)
        for w in (self._first, self._last):
            w.setEnabled(not seq)
        gray = self._gray.isChecked()
        self._dither.setEnabled(gray)

    def _default_index(self, *_):
        pack = self._bundle.currentData()
        if isinstance(pack, fpr.Pack) and pack.fonts:
            self._gidx.setValue(max(f.global_index for f in pack.fonts) + 1)
        # A previous build targeted the old bundle — invalidate it so Save/Flash
        # can't splice the built font into a bundle the user has since switched to.
        self._built = None
        self._save_btn.setEnabled(False)
        if self._flash_cb is not None:
            self._flash_btn.setEnabled(False)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select font", "",
                                              "Fonts (*.ttf *.otf);;All files (*)")
        if path:
            self._src.setText(path)

    def _options(self):
        from polyhost.services.fontgen import RenderOptions
        from polyhost.services import fontgen_dither as fd
        return RenderOptions(
            size=self._size.value(), render_mode=1 if self._gray.isChecked() else 0,
            dither_mode=fd.dither_mode_from_name(self._dither.currentText()),
            normalize=self._norm.isChecked(), invert=self._inv.isChecked(),
            edge_preserve=self._edge.isChecked(), outline=self._outline.value(),
            height=self._rsize.value(), yadvance=self._yadv.value(),
            max_width=self._maxw.value(),
            seq_first=int(self._seq_first.text(), 16) if self._seq.isEnabled() else 0,
            bits=32)

    # ---- actions ----
    def _build(self):
        src = self._src.text().strip()
        if not src or not os.path.exists(src):
            QMessageBox.warning(self, "Build", "Pick an existing font file first.")
            return
        try:
            from polyhost.services import fontpack_extend as ext
            from polyhost.services import fontpack_render as rd
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Build", f"Font building needs the optional deps:\n"
                                "  pip install -e .[fontgen]\n\n" f"({e})")
            return
        gidx = self._gidx.value()
        try:
            if self._seq.isEnabled():
                new = ext.render_packfont(src, sequence=self._seq.text().strip(),
                                          opts=self._options(), global_index=gidx)
            else:
                new = ext.render_packfont(
                    src, codepoint_range=(int(self._first.text(), 16),
                                          int(self._last.text(), 16)),
                    opts=self._options(), global_index=gidx)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Build failed", str(e))
            return
        self._built = (self._bundle.currentIndex(), new)
        sheet = rd.contact_sheet(fpr.Pack(1, 0, 1, 0, 0, True, [new]), cols=12, scale=2,
                                 mode="keycap", title=f"built · {new.glyph_count} glyphs")
        self._preview.setPixmap(_pil_l_to_pixmap(sheet))
        self._preview.resize(self._preview.pixmap().size())
        self._status.setText(f"Built {new.glyph_count} glyph(s), U+{new.first:04X}–"
                             f"{new.last:04X}, global index {gidx}. Save or flash to the "
                             f"'{self._bundle.currentText()}' bundle.")
        self._save_btn.setEnabled(True)
        if self._flash_cb is not None:
            self._flash_btn.setEnabled(True)

    def _spliced_bytes(self) -> bytes:
        bundle_index, new = self._built     # the bundle chosen at Build time
        pack = self._packs[bundle_index][1]
        fonts = fpr.splice_font(pack, new)
        return fpr.encode_pack(fonts, pack.content_version + 1)

    def _save(self):
        if not self._built:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save font pack", "trial.plyf",
                                              "Font pack (*.plyf)")
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(self._spliced_bytes())
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self._status.setText(f"Saved {path}")

    def _flash(self):
        if not self._built or self._flash_cb is None:
            return
        bundle_index, _ = self._built          # the bundle chosen at Build time
        label = self._packs[bundle_index][0]
        if QMessageBox.question(self, "Flash",
                                f"Flash the modified '{label}' bundle to the keyboard?") \
                != QMessageBox.Yes:
            return
        try:
            self._flash_cb(bundle_index, self._spliced_bytes())
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Flash failed", str(e))
            return
        self._status.setText("Flash started — watch the tray/log for progress.")


def main(argv=None):
    app = QApplication(argv if argv is not None else sys.argv)
    FontPackExtendDialog().show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
