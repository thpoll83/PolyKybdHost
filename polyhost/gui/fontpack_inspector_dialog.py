"""Qt window to visually inspect external-flash font-pack (.plyf) bundles.

A standalone Qt tool that is *also* launchable from the tray menu.  It renders
every glyph of each bundle exactly as the keycap OLED draws it, using the Qt-free
`fontpack_reader` (decode) + `fontpack_render` (rasterise) services — so the
window is a thin view over logic that's unit-tested without a display.

Glyphs are shown in a **flow layout** (reflows to the window width → only vertical
scrolling).  Bundles use contiguous codepoint ranges that the source fonts only
sparsely populate, so many entries are *empty* (no glyph); those are drawn as a
dashed placeholder and can be hidden with "Hide empty".  Double-click a glyph (or
select it and press "Edit…") to replace it via the extend dialog.

Sources are pluggable: by default it loads the bundles shipped in
``polyhost/res/fontpack/`` (so it runs with **no device connected**), but the
constructor accepts any list of ``(label, Pack)`` pairs.

Run standalone:  ``python -m polyhost.gui.fontpack_inspector_dialog``
From the tray:   PolyHost.open_fontpack_inspector()
"""
from __future__ import annotations

import os
import sys

from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QListView,
    QTabWidget, QDoubleSpinBox, QComboBox, QCheckBox, QPushButton, QApplication,
    QProgressDialog,
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


# Amber tint for "peek" previews — clearly distinct from real (white) pack glyphs.
PEEK_RGB = (255, 168, 0)


def _pil_l_to_tinted_pixmap(img, rgb) -> QPixmap:
    """PIL 'L' image -> RGB QPixmap tinted to `rgb` (lit pixels take the colour),
    so peek previews read as a different colour from the real pack glyphs."""
    from PIL import Image
    if img.mode != "L":
        img = img.convert("L")
    r, g, b = rgb
    chans = (img.point(lambda v: v * r // 255),
             img.point(lambda v: v * g // 255),
             img.point(lambda v: v * b // 255))
    rgbimg = Image.merge("RGB", chans)
    data = rgbimg.tobytes()
    qimg = QImage(data, rgbimg.width, rgbimg.height, rgbimg.width * 3, QImage.Format_RGB888)
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
    files = []
    manifest = os.path.join(res_dir, "bundles.json")
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


_FONT_ROLE = int(Qt.UserRole)
_CP_ROLE = int(Qt.UserRole) + 1

_VIEW_QSS = ("QListView { background:#000; color:#bbb; }"
             " QListView::item:selected { background:#1d4f3f; }")


class _BundleTab(QWidget):
    """One bundle: metadata header + a virtualized icon grid (QListView IconMode).

    QListView reflows to the window width (vertical scroll only) and renders only
    the visible items, so even the ~1200-glyph emoji bundle is responsive.  Items
    are (re)built lazily on view-mode / zoom / hide-empty changes; selection and
    double-click come from the view."""
    edit_requested = pyqtSignal(object, int)   # (font, codepoint)

    def __init__(self, label: str, pack, parent=None):
        super().__init__(parent)
        self._label = label
        self._pack = pack
        self._mode = "glyph"
        self._built_key = None         # (mode, scale, hide_empty, peek) last built
        self._settings_map = None      # lazy: global index -> render settings
        self._last_peek_count = 0      # previews rendered in the last peek rebuild
        v = QVBoxLayout(self)

        if not isinstance(pack, fpr.Pack):
            v.addWidget(QLabel(f"⚠ Could not decode '{label}': {pack}"))
            self._view = None
            return

        crc = "ok" if pack.crc_ok else "BAD"
        n_empty = sum(1 for f in pack.fonts for g in f.glyphs
                      if g["width"] == 0 or g["height"] == 0)
        hdr = QLabel(f"{label}.plyf — abi v{pack.abi_version} · content v{pack.content_version}"
                     f" · {pack.font_count} fonts · {pack.codepoint_count()} glyphs "
                     f"({n_empty} empty) · {pack.total_size:,} B · crc {crc}")
        hdr.setStyleSheet("font-weight: bold; padding: 4px; color: %s;"
                          % ("#e33" if not pack.crc_ok else "inherit"))
        v.addWidget(hdr)

        ctl = QHBoxLayout()
        ctl.addWidget(QLabel("Zoom"))
        self._zoom = QDoubleSpinBox()
        self._zoom.setRange(1.0, 8.0)
        self._zoom.setSingleStep(1.0)
        self._zoom.setValue(2.0)
        self._zoom.valueChanged.connect(self._rebuild)
        ctl.addWidget(self._zoom)
        self._hide_empty = QCheckBox("Hide empty")
        self._hide_empty.stateChanged.connect(self._rebuild)
        ctl.addWidget(self._hide_empty)
        self._peek = QCheckBox("Peek empty (from source)")
        self._peek.setToolTip("Render the empty slots from their source font (needs "
                              "the font downloaded) as amber previews — candidates to "
                              "build/take. Previews are not in the pack.")
        self._peek.stateChanged.connect(self._rebuild)
        ctl.addWidget(self._peek)
        ctl.addStretch(1)
        v.addLayout(ctl)

        self._model = QStandardItemModel(self)
        self._view = QListView()
        self._view.setModel(self._model)
        self._view.setViewMode(QListView.IconMode)
        self._view.setResizeMode(QListView.Adjust)     # reflow on resize → vertical scroll
        self._view.setWrapping(True)
        self._view.setMovement(QListView.Static)
        self._view.setUniformItemSizes(True)
        self._view.setSelectionMode(QListView.SingleSelection)
        self._view.setSpacing(6)
        self._view.setStyleSheet(_VIEW_QSS)
        self._view.doubleClicked.connect(self._on_double)
        v.addWidget(self._view, 1)

    # ---- public API used by the dialog ----
    def set_mode(self, mode: str):
        self._mode = mode
        self._rebuild()

    def selected(self):
        idx = self._view.currentIndex() if self._view else None
        if idx is not None and idx.isValid() and idx.data(_FONT_ROLE) is not None:
            return idx.data(_FONT_ROLE), idx.data(_CP_ROLE)
        return None

    # ---- internals ----
    def _on_double(self, index):
        font = index.data(_FONT_ROLE)
        if font is not None:
            self.edit_requested.emit(font, index.data(_CP_ROLE))

    def _cell_dims(self, scale: int):
        if self._mode == "keycap":
            return fprd.OLED_W * scale, fprd.OLED_H * scale
        w = h = 1
        for f in self._pack.fonts:
            for g in f.glyphs:
                w = max(w, g["width"])
                h = max(h, g["height"])
        return max(8, w * scale), max(8, h * scale)

    def _settings(self):
        if self._settings_map is None:
            from polyhost.services import fontpack_extend as ext
            self._settings_map = ext.load_render_settings()
        return self._settings_map

    def _peek_pixmap(self, font, cp, cw, ch, scale):
        """Render the empty slot `cp` from its source font (per the shipped render
        settings) as an amber preview pixmap, or None if no settings / the source
        isn't downloaded / the source has no glyph there / fontgen is unavailable."""
        opts = self._settings().get(str(font.global_index))
        if not opts or not opts.get("source_file"):
            return None
        from polyhost.services import font_downloader as fdl
        src = os.path.join(fdl.default_cache_dir(), opts["source_file"])
        if not os.path.exists(src):
            return None
        try:
            from polyhost.services import fontpack_extend as ext
            pf = ext.peek_source_glyph(src, cp, opts, global_index=font.global_index)
        except Exception:                       # noqa: BLE001 — one bad glyph != dead grid
            return None
        if pf is None:
            return None
        img = fprd.glyph_cell(pf, cp, cw, ch, scale=scale, mode=self._mode)
        return _pil_l_to_tinted_pixmap(img, PEEK_RGB)

    def _rebuild(self, *_):
        if self._view is None:
            return
        scale = int(self._zoom.value())
        hide_empty = self._hide_empty.isChecked()
        peek = self._peek.isChecked()
        key = (self._mode, scale, hide_empty, peek)
        if key == self._built_key:
            return
        self._built_key = key
        self._model.clear()
        cw, ch = self._cell_dims(scale)
        self._view.setIconSize(QSize(cw, ch + 11))

        # Peeking renders empties through FreeType — bound the cost / keep the UI
        # responsive with a cancellable progress dialog.
        prog = None
        if peek:
            n_empty = sum(1 for f in self._pack.fonts for g in f.glyphs
                          if g["width"] == 0 or g["height"] == 0)
            if n_empty:
                prog = QProgressDialog("Rendering previews…", "Cancel", 0, n_empty, self)
                prog.setWindowModality(Qt.WindowModal)
                prog.setMinimumDuration(0)
        peeked = done = 0
        for font in sorted(self._pack.fonts, key=lambda f: f.global_index):
            for cp in range(font.first, font.last + 1):
                g = font.glyphs[cp - font.first]
                empty = g["width"] == 0 or g["height"] == 0
                if empty and hide_empty:
                    continue
                pm, is_preview = None, False
                if empty and peek and (prog is None or not prog.wasCanceled()):
                    pm = self._peek_pixmap(font, cp, cw, ch, scale)
                    is_preview = pm is not None
                    if pm is not None:
                        peeked += 1
                    done += 1
                    if prog is not None:
                        prog.setValue(done)
                        QApplication.processEvents()
                if pm is None:
                    img = fprd.glyph_cell(font, cp, cw, ch, scale=scale, mode=self._mode)
                    pm = _pil_l_to_pixmap(img)
                it = QStandardItem()
                it.setIcon(QIcon(pm))
                it.setEditable(False)
                it.setData(font, _FONT_ROLE)
                it.setData(cp, _CP_ROLE)
                it.setToolTip(f"U+{cp:04X}" + ("  (preview from source — not in pack)"
                                               if is_preview else
                                               "  (empty — no glyph)" if empty else ""))
                self._model.appendRow(it)
        if prog is not None:
            prog.close()
        self._last_peek_count = peeked

    def cell_count(self) -> int:
        return self._model.rowCount() if self._view else 0


class FontPackInspectorDialog(QDialog):
    def __init__(self, sources=None, parent=None, flash_cb=None):
        """`sources`: list of (label, Pack) pairs; defaults to the shipped bundles.
        `flash_cb(bundle_index, plyf_bytes)`: optional, enables the extend dialog's
        Flash button (the tray passes a device-flash callback)."""
        super().__init__(parent)
        self.setWindowTitle("PolyKybd — Font Pack Inspector")
        self.resize(1100, 800)
        self._flash_cb = flash_cb
        v = QVBoxLayout(self)
        if sources is None:
            sources = load_shipped_packs()
        self._sources = sources         # keep the exact inspected bundles for Extend

        self._modes = [("Glyph grid (native size)", "glyph"),
                       ("Keycap preview (72×40)", "keycap")]
        row = QHBoxLayout()
        row.addWidget(QLabel("View"))
        self._mode_combo = QComboBox()
        for text, _ in self._modes:
            self._mode_combo.addItem(text)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        row.addWidget(self._mode_combo)
        row.addStretch(1)
        self._edit_btn = QPushButton("Edit…")
        self._edit_btn.setToolTip("Replace the selected glyph (double-clicking a glyph "
                                  "does the same)")
        self._edit_btn.clicked.connect(self._edit_selected)
        row.addWidget(self._edit_btn)
        self._extend_btn = QPushButton("Extend…")
        self._extend_btn.setToolTip("Build new glyphs from a font and splice them "
                                    "into a bundle")
        self._extend_btn.clicked.connect(lambda: self._open_extend())
        row.addWidget(self._extend_btn)
        v.addLayout(row)

        self._tabs = QTabWidget()
        for label, pack in sources:
            tab = _BundleTab(label, pack)
            tab.edit_requested.connect(self._on_edit)
            self._tabs.addTab(tab, label)
        self._tabs.currentChanged.connect(self._render_current)
        if self._tabs.count() == 0:
            v.addWidget(QLabel("No font-pack bundles found."))
            self._mode_combo.setEnabled(False)
            self._edit_btn.setEnabled(False)
        else:
            v.addWidget(self._tabs, 1)
            self._render_current()

    def _mode(self) -> str:
        return self._modes[self._mode_combo.currentIndex()][1]

    def _render_current(self, *_):
        tab = self._tabs.currentWidget()
        if isinstance(tab, _BundleTab):
            tab.set_mode(self._mode())

    def _on_mode_changed(self, *_):
        self._render_current()

    def _edit_selected(self):
        from PyQt5.QtWidgets import QMessageBox
        tab = self._tabs.currentWidget()
        sel = tab.selected() if isinstance(tab, _BundleTab) else None
        if sel is None:
            QMessageBox.information(self, "Edit", "Select a glyph first (click it), "
                                    "or double-click a glyph to edit it.")
            return
        self._on_edit(*sel)

    def _on_edit(self, font, cp: int):
        label = self._tabs.tabText(self._tabs.currentIndex())
        self._open_extend(prefill={"bundle": label, "first": cp, "last": cp,
                                   "global_index": font.global_index})

    def _open_extend(self, prefill=None):
        from polyhost.gui.fontpack_extend_dialog import FontPackExtendDialog
        dlg = FontPackExtendDialog(flash_cb=self._flash_cb, parent=self,
                                   prefill=prefill, sources=self._sources)
        dlg.exec_()


def main(argv=None):
    app = QApplication(argv if argv is not None else sys.argv)
    dlg = FontPackInspectorDialog()
    dlg.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
