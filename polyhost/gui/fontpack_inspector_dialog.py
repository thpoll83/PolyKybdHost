"""Qt window to visually inspect external-flash font-pack (.plyf) bundles.

A standalone Qt tool that is *also* launchable from the tray menu.  It renders
every glyph of each bundle exactly as the keycap OLED draws it, using the Qt-free
`fontpack_reader` (decode) + `fontpack_render` (rasterise) services — so the
window is a thin view over logic that's unit-tested without a display.

Sources are pluggable: by default it loads the bundles shipped in
``polyhost/res/fontpack/`` (so it runs with **no device connected**), but the
constructor accepts any list of ``(label, Pack)`` pairs, which is how the tray can
later feed it a pack read back from a live keyboard, or a freshly-built trial pack.

Run standalone:  ``python -m polyhost.gui.fontpack_inspector_dialog``
From the tray:   PolyHost.open_fontpack_inspector()
"""
from __future__ import annotations

import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, QLabel,
    QTabWidget, QDoubleSpinBox, QComboBox, QPushButton, QApplication,
)

from polyhost.services import fontpack_reader as fpr
from polyhost.services import fontpack_render as fprd


def _pil_l_to_pixmap(img) -> QPixmap:
    """PIL 'L' image -> QPixmap (Grayscale8). fromImage copies, so the temporary
    byte buffer doesn't need to outlive the call."""
    if img.mode != "L":
        img = img.convert("L")
    data = img.tobytes()
    qimg = QImage(data, img.width, img.height, img.width, QImage.Format_Grayscale8)
    return QPixmap.fromImage(qimg)


def _res_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "res", "fontpack")


def load_shipped_packs(res_dir: str | None = None):
    """Decode every bundle listed in res/fontpack/bundles.json -> [(label, Pack)].

    Falls back to globbing *.plyf if bundles.json is absent.  Bad bundles are
    skipped with a placeholder label rather than failing the whole window.
    """
    import glob
    import json
    res_dir = res_dir or _res_dir()
    out = []
    manifest = os.path.join(res_dir, "bundles.json")
    files = []
    if os.path.exists(manifest):
        with open(manifest) as f:
            for b in json.load(f).get("bundles", []):
                files.append((b["id"], os.path.join(res_dir, b["file"])))
    else:
        files = [(fpr._stem(p), p) for p in sorted(glob.glob(os.path.join(res_dir, "*.plyf")))]
    for label, path in files:
        try:
            out.append((label, fpr.decode_pack_file(path, name_hint=label)))
        except Exception as e:                       # noqa: BLE001 — one bad bundle != dead window
            out.append((f"{label} (error)", e))
    return out


class _BundleTab(QWidget):
    """One bundle: a metadata header + a scrollable, zoomable contact sheet.

    The contact sheet is rendered lazily and re-rendered on a view-mode switch
    ("glyph" inventory vs "keycap" 72×40 preview); the zoom control just rescales
    the cached pixmap."""

    def __init__(self, label: str, pack, parent=None):
        super().__init__(parent)
        self._label = label
        self._pack = pack
        self._rendered_mode = None
        self._base_pixmap = None
        v = QVBoxLayout(self)

        if not isinstance(pack, fpr.Pack):
            v.addWidget(QLabel(f"⚠ Could not decode '{label}': {pack}"))
            self._image = None
            return

        crc = "ok" if pack.crc_ok else "BAD"
        header = (f"{label}.plyf — abi v{pack.abi_version} · content v{pack.content_version} · "
                  f"{pack.font_count} fonts · {pack.codepoint_count()} glyphs · "
                  f"{pack.total_size:,} B · crc {crc}")
        hdr = QLabel(header)
        colour = "#e33" if not pack.crc_ok else "inherit"
        hdr.setStyleSheet(f"font-weight: bold; padding: 4px; color: {colour};")
        v.addWidget(hdr)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("Zoom"))
        self._zoom = QDoubleSpinBox()
        self._zoom.setRange(0.25, 6.0)
        self._zoom.setSingleStep(0.25)
        self._zoom.setValue(1.0)
        self._zoom.valueChanged.connect(self._apply_zoom)
        zoom_row.addWidget(self._zoom)
        zoom_row.addStretch(1)
        v.addLayout(zoom_row)

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll = QScrollArea()
        scroll.setWidget(self._image)
        scroll.setWidgetResizable(False)
        scroll.setStyleSheet("background: #000;")
        v.addWidget(scroll, 1)

    def set_mode(self, mode: str):
        """Render this tab's sheet in `mode` ('glyph'|'keycap'); a no-op if already
        rendered in that mode, so switching tabs back and forth is cheap."""
        if self._image is None or mode == self._rendered_mode:
            return
        sheet = fprd.contact_sheet(self._pack, cols=16, scale=2, mode=mode,
                                   title=f"{self._label} · {mode} · "
                                         f"{self._pack.codepoint_count()} glyphs")
        self._base_pixmap = _pil_l_to_pixmap(sheet)
        self._rendered_mode = mode
        self._apply_zoom(self._zoom.value())

    def _apply_zoom(self, factor: float):
        if self._image is None or self._base_pixmap is None:
            return
        pm = self._base_pixmap
        scaled = pm.scaled(int(pm.width() * factor), int(pm.height() * factor),
                           Qt.KeepAspectRatio, Qt.FastTransformation)
        self._image.setPixmap(scaled)
        self._image.resize(scaled.size())


class FontPackInspectorDialog(QDialog):
    def __init__(self, sources=None, parent=None, flash_cb=None):
        """`sources`: list of (label, Pack) pairs; defaults to the shipped bundles.
        `flash_cb(bundle_index, plyf_bytes)`: optional, enables the extend dialog's
        Flash button (the tray passes a device-flash callback)."""
        super().__init__(parent)
        self.setWindowTitle("PolyKybd — Font Pack Inspector")
        self.resize(1100, 800)
        v = QVBoxLayout(self)
        if sources is None:
            sources = load_shipped_packs()

        self._modes = [("Glyph grid (native size)", "glyph"),
                       ("Keycap preview (72×40)", "keycap")]
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("View"))
        self._mode_combo = QComboBox()
        for text, _ in self._modes:
            self._mode_combo.addItem(text)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo)
        mode_row.addStretch(1)
        self._extend_btn = QPushButton("Extend…")
        self._extend_btn.setToolTip("Build new glyphs from a font and splice them "
                                    "into a bundle")
        self._extend_btn.clicked.connect(self._open_extend)
        mode_row.addWidget(self._extend_btn)
        v.addLayout(mode_row)
        self._flash_cb = flash_cb

        self._tabs = QTabWidget()
        for label, pack in sources:
            self._tabs.addTab(_BundleTab(label, pack), label)
        self._tabs.currentChanged.connect(self._render_current)
        if self._tabs.count() == 0:
            v.addWidget(QLabel("No font-pack bundles found."))
            self._mode_combo.setEnabled(False)
        else:
            v.addWidget(self._tabs, 1)
            self._render_current()    # render the first visible tab now

    def _mode(self) -> str:
        return self._modes[self._mode_combo.currentIndex()][1]

    def _render_current(self, *_):
        tab = self._tabs.currentWidget()
        if isinstance(tab, _BundleTab):
            tab.set_mode(self._mode())

    def _on_mode_changed(self, *_):
        # Lazy: only the visible tab re-renders now; others re-render when shown.
        self._render_current()

    def _open_extend(self):
        from polyhost.gui.fontpack_extend_dialog import FontPackExtendDialog
        dlg = FontPackExtendDialog(flash_cb=self._flash_cb, parent=self)
        dlg.exec_()


def main(argv=None):
    app = QApplication(argv if argv is not None else sys.argv)
    dlg = FontPackInspectorDialog()
    dlg.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
