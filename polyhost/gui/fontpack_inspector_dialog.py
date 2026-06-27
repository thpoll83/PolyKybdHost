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
    QTabWidget, QDoubleSpinBox, QApplication,
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
    """One bundle: a metadata header + a scrollable, zoomable contact sheet."""

    def __init__(self, label: str, pack, parent=None):
        super().__init__(parent)
        self._pack = pack
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
        hdr.setStyleSheet("font-weight: bold; padding: 4px;")
        if not pack.crc_ok:
            hdr.setStyleSheet("font-weight: bold; padding: 4px; color: #e33;")
        v.addWidget(hdr)

        # Render the contact sheet once at scale 2; the zoom control rescales the
        # pixmap (FastTransformation keeps the 1-bit pixels crisp).
        self._sheet = fprd.contact_sheet(pack, cols=16, scale=2,
                                         title=f"{label} · {pack.codepoint_count()} glyphs")
        self._base_pixmap = _pil_l_to_pixmap(self._sheet)

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
        self._apply_zoom(1.0)

    def _apply_zoom(self, factor: float):
        if self._image is None:
            return
        pm = self._base_pixmap
        scaled = pm.scaled(int(pm.width() * factor), int(pm.height() * factor),
                           Qt.KeepAspectRatio, Qt.FastTransformation)
        self._image.setPixmap(scaled)
        self._image.resize(scaled.size())


class FontPackInspectorDialog(QDialog):
    def __init__(self, sources=None, parent=None):
        """`sources`: list of (label, Pack) pairs; defaults to the shipped bundles."""
        super().__init__(parent)
        self.setWindowTitle("PolyKybd — Font Pack Inspector")
        self.resize(1100, 800)
        v = QVBoxLayout(self)
        if sources is None:
            sources = load_shipped_packs()
        self._tabs = QTabWidget()
        for label, pack in sources:
            self._tabs.addTab(_BundleTab(label, pack), label)
        if self._tabs.count() == 0:
            v.addWidget(QLabel("No font-pack bundles found."))
        else:
            v.addWidget(self._tabs, 1)


def main(argv=None):
    app = QApplication(argv if argv is not None else sys.argv)
    dlg = FontPackInspectorDialog()
    dlg.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
