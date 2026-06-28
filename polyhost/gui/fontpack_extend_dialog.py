"""Qt dialog for the font-pack *extend* round-trip: build glyphs from a TTF/OTF,
preview them as keycaps, and splice them into a bundle to save or flash.

Ties fontgen (render) + fontpack_extend (splice/encode) to a form.  fontgen and
its deps (freetype-py/uharfbuzz/fonttools — core deps, but imported lazily on
Build so the dialog still opens and reports clearly if an env is missing them).
Flashing is an injected callback ``flash_cb(bundle_index:int, plyf_bytes:bytes)``
— None hides the Flash button, so the dialog is usable (and testable) with no device.

Reached from the inspector's "Extend…" button; standalone:
``python -m polyhost.gui.fontpack_extend_dialog``.
"""
from __future__ import annotations

import os
import sys

import threading

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QSpinBox,
    QComboBox, QCheckBox, QPushButton, QScrollArea, QFileDialog, QMessageBox,
    QApplication, QWidget, QListWidget, QListWidgetItem, QProgressDialog,
)

from polyhost.services import fontpack_reader as fpr
from polyhost.gui.fontpack_inspector_dialog import _pil_l_to_pixmap, load_shipped_packs

_DITHER = ["fs", "stucki", "bayer", "threshold", "random"]

def _missing_fontgen_deps() -> list:
    """The font-generation modules not importable here (pip names), so Build can
    show an actionable hint instead of a raw 'No module named freetype' if an env
    somehow lacks them (they're core deps, normally always present)."""
    missing = []
    for mod, pip in (("freetype", "freetype-py"), ("uharfbuzz", "uharfbuzz"),
                     ("fontTools", "fonttools"), ("numpy", "numpy"), ("PIL", "pillow")):
        try:
            __import__(mod)
        except Exception:                       # noqa: BLE001
            missing.append(pip)
    return missing


_RENDER_SETTINGS_CACHE = None


def _render_settings() -> dict:
    """Load the shipped global-index -> render-options map (built from the
    firmware's fonts.yaml by generate_fonts.py).  Cached; missing/broken file
    degrades to {} so editing still works (just without prefilled options)."""
    global _RENDER_SETTINGS_CACHE
    if _RENDER_SETTINGS_CACHE is None:
        from polyhost.services import fontpack_extend as ext
        _RENDER_SETTINGS_CACHE = ext.load_render_settings()
    return _RENDER_SETTINGS_CACHE


class FontPackExtendDialog(QDialog):
    def __init__(self, res_dir: str | None = None, flash_cb=None, parent=None,
                 prefill=None, sources=None):
        """`prefill` (optional): {"bundle": label, "first": cp, "last": cp,
        "global_index": gidx} to pre-target a glyph for *editing* (replace).
        `sources` (optional): the exact (label, Pack) list the caller is inspecting
        — pass it so edit/save stay bound to *that* bundle.  Defaults to the
        shipped bundles when omitted."""
        super().__init__(parent)
        self.setWindowTitle("PolyKybd — Build / Extend Font Pack")
        self.resize(900, 640)
        self._flash_cb = flash_cb
        self._built = None          # (bundle_index, new PackFont)
        self._edit_target = None    # {bundle_index, global_index, cp} in edit mode
        # Only valid bundles are splice targets — sources/load_shipped_packs may
        # yield (label, Exception) placeholders for ones that failed to decode.
        raw = sources if sources is not None else load_shipped_packs(res_dir)
        self._packs = [(label, p) for label, p in raw if isinstance(p, fpr.Pack)]

        root = QHBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form, 0)

        self._src = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        dl = QPushButton("Download Noto…")
        dl.setCheckable(True)
        dl.setToolTip("Show/hide the Noto download panel (same list as the firmware's "
                      "dl-fonts.sh); picking one fills the source field")
        dl.toggled.connect(self._toggle_download_panel)
        self._dl_toggle = dl
        srow = QHBoxLayout()
        srow.addWidget(self._src, 1); srow.addWidget(browse); srow.addWidget(dl)
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
        self._weight = self._spin(0, 1000, 0)
        self._weight.setToolTip("Variable-font wght axis (e.g. 400 Regular, 500 Medium, "
                                "700 Bold). 0 = the font's default instance.")
        form.addRow("Weight -w (0=default)", self._weight)
        self._xshift = self._spin(-128, 128, 0)
        self._xshift.setToolTip("Horizontal pixel shift of the rendered glyph (rarely "
                                "needed; e.g. couple emoji use -12).")
        form.addRow("X shift -X", self._xshift)

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

        # Download UI as an attached side panel (hidden until toggled) rather than a
        # stacked modal dialog — keeps everything in one window.
        self._dl_panel = NotoDownloadPanel(self)
        self._dl_panel.font_chosen.connect(self._on_downloaded_font)
        self._dl_panel.setVisible(False)
        root.addWidget(self._dl_panel, 0)

        self._default_index()
        if not self._packs:
            self._build_btn.setEnabled(False)
            self._status.setText("No valid shipped bundles available to extend.")
        elif prefill:
            self._apply_prefill(prefill)

    def _apply_prefill(self, p: dict):
        """Pre-target a single glyph for editing/peek: select its bundle, range =
        [cp, cp].  Records `_edit_target` so Save/Flash inserts the built glyph into
        the existing font (preserving its siblings) instead of a whole-font splice."""
        bi = next((i for i, (label, _pack) in enumerate(self._packs)
                   if label == p.get("bundle")), None)
        if bi is None:
            # Don't silently retarget another bundle — that would edit the wrong pack.
            raise ValueError(f"Unknown target bundle: {p.get('bundle')!r}")
        self._bundle.setCurrentIndex(bi)
        self._mode.setCurrentIndex(0)          # codepoint range
        self._sync_mode()
        cp = p.get("first", 0)
        self._first.setText(f"0x{cp:04X}")
        self._last.setText(f"0x{p.get('last', cp):04X}")
        opts = None
        if "global_index" in p:
            gi = p["global_index"]
            self._gidx.setValue(gi)
            self._edit_target = {"bundle_index": bi, "global_index": gi, "cp": cp}
            opts = self._apply_saved_settings(gi)
        if opts is None:
            hint = " (no saved settings for this font — set options manually.)"
        elif self._src.text().strip():
            hint = (f" Pre-filled from '{opts.get('source_file', 'source')}' + its "
                    "original settings.")
        else:
            sf = opts.get("source_file")
            hint = (f" Original settings pre-filled; source font '{sf}' isn't cached — "
                    "Download Noto… or Browse." if sf else
                    " Original settings pre-filled; pick the source font.")
        self._status.setText(f"Editing U+{cp:04X} in '{p.get('bundle')}' — Build to peek, "
                             f"then Save/Flash to take it.{hint}")

    def _apply_saved_settings(self, global_index: int):
        """Prefill the render controls from the settings the font was generated
        with (shipped fontpack_render_settings.json, keyed by global index): size,
        dither, flags, render size, yAdvance, …  Also auto-fills the source font
        from the download cache when its file (``source_file``) is already present,
        so an edit needs no manual font pick.  Returns the opts dict, or None when
        there's no record for this index."""
        opts = _render_settings().get(str(global_index))
        if not opts:
            return None
        if "size" in opts:
            self._size.setValue(int(opts["size"]))
        self._gray.setChecked(bool(opts.get("grayscale")))
        if opts.get("dither") in _DITHER:
            self._dither.setCurrentIndex(_DITHER.index(opts["dither"]))
        self._norm.setChecked(bool(opts.get("normalize")))
        self._inv.setChecked(bool(opts.get("invert")))
        self._edge.setChecked(bool(opts.get("edge")))
        self._outline.setValue(int(opts.get("outline") or 0))
        self._rsize.setValue(int(opts.get("render_height") or 0))
        self._yadv.setValue(int(opts.get("yadvance") or 0))
        self._maxw.setValue(int(opts.get("max_width") or 0))
        self._weight.setValue(int(opts.get("weight") or 0))
        self._xshift.setValue(int(opts.get("xshift") or 0))
        self._sync_mode()          # reflect the grayscale toggle (enables dither)
        sf = opts.get("source_file")
        if sf and not self._src.text().strip():
            from polyhost.services import font_downloader as fdl
            cached = os.path.join(fdl.default_cache_dir(), sf)
            if os.path.exists(cached):
                self._src.setText(cached)
        return opts

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
        # Switching bundles also leaves edit mode (becomes a normal whole-font add).
        self._built = None
        self._edit_target = None
        self._save_btn.setEnabled(False)
        if self._flash_cb is not None:
            self._flash_btn.setEnabled(False)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select font", "",
                                              "Fonts (*.ttf *.otf);;All files (*)")
        if path:
            self._src.setText(path)

    def _toggle_download_panel(self, on: bool):
        self._dl_panel.setVisible(on)

    def _on_downloaded_font(self, path: str):
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
            weight=self._weight.value() or -1,    # 0 in the UI = unset (-1)
            xshift=self._xshift.value(),
            seq_first=int(self._seq_first.text(), 16) if self._seq.isEnabled() else 0,
            bits=32)

    # ---- actions ----
    def _build(self):
        src = self._src.text().strip()
        if not src or not os.path.exists(src):
            QMessageBox.warning(self, "Build", "Pick an existing font file first.")
            return
        missing = _missing_fontgen_deps()
        if missing:
            QMessageBox.warning(self, "Build",
                                "Building glyphs needs these font-generation "
                                "dependencies, which aren't installed in this "
                                "environment:\n\n    pip install " + " ".join(missing) +
                                "\n\n(They're normally pulled in by installing "
                                "PolyKybdHost: pip install -e .)")
            return
        try:
            from polyhost.services import fontpack_extend as ext
            from polyhost.services import fontpack_render as rd
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Build", "Font building dependencies are missing "
                                "or broken:\n  pip install -e .\n\n" f"({e})")
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
        et = self._edit_target
        if et is not None:
            # Edit/peek mode: insert the single built glyph into the existing font
            # (keeping its siblings), rather than replacing the whole font.  If the
            # edit target no longer resolves in the chosen bundle, fail loudly —
            # silently degrading to a whole-font splice would corrupt the bundle.
            existing = next((f for f in pack.fonts
                             if f.global_index == et["global_index"]), None)
            if existing is None or not existing.covers(et["cp"]) or not new.glyphs:
                raise ValueError("Edit target no longer matches the selected bundle")
            merged = fpr.replace_glyph(existing, et["cp"], new.glyphs[0], new.bitmap)
            return fpr.encode_pack(fpr.splice_font(pack, merged),
                                   pack.content_version + 1)
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


class NotoDownloadPanel(QWidget):
    """Embeddable Noto source-font picker/downloader (no modal).  Lists the shared
    catalog (noto-fonts.yaml), marks cached fonts, downloads selected / all in the
    background, and emits ``font_chosen(path)`` when a font is ready to use — so it
    can sit as a side panel in the extend dialog instead of stacking a dialog."""
    font_chosen = pyqtSignal(str)       # local path of the picked/downloaded font

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumWidth(360)
        from polyhost.services import font_downloader as fdl
        self._fdl = fdl
        try:
            self._fonts = fdl.load_catalog()
        except Exception as e:  # noqa: BLE001
            self._fonts = []
            QMessageBox.warning(self, "Download", f"Could not read the font catalog:\n{e}")

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(QLabel("Download Noto source fonts\n→ " + fdl.default_cache_dir()))
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _it: self._download())
        for f in self._fonts:
            item = QListWidgetItem(self._label(f))
            item.setData(Qt.UserRole, f)
            self._list.addItem(item)
        if self._fonts:
            self._list.setCurrentRow(0)
        v.addWidget(self._list, 1)

        btns = QHBoxLayout()
        self._all_btn = QPushButton("Download all")
        self._all_btn.setToolTip("Fetch every Noto font in the list into the cache")
        self._all_btn.clicked.connect(self._download_all)
        self._all_btn.setEnabled(bool(self._fonts))
        self._dl_btn = QPushButton("Use selected")
        self._dl_btn.setToolTip("Download if needed, then use it as the source font")
        self._dl_btn.clicked.connect(self._download)
        self._dl_btn.setEnabled(bool(self._fonts))
        btns.addWidget(self._all_btn)
        btns.addStretch(1)
        btns.addWidget(self._dl_btn)
        v.addLayout(btns)

    def _label(self, font) -> str:
        mark = "  ✓ cached" if self._fdl.is_downloaded(font) else ""
        return f"{font.name}  ({font.filename}){mark}"

    def _refresh_marks(self):
        for i in range(self._list.count()):
            it = self._list.item(i)
            it.setText(self._label(it.data(Qt.UserRole)))

    def _download(self):
        item = self._list.currentItem()
        if item is None:
            return
        font = item.data(Qt.UserRole)
        # Already cached → use it straight away, no network.
        if self._fdl.is_downloaded(font):
            self.font_chosen.emit(self._fdl.local_path(font))
            return
        paths, err = self._run_downloads([font])
        if err:
            QMessageBox.critical(self, "Download failed",
                                 f"Could not download {font.name}:\n{err}")
            return
        if font.filename in paths:                # not cancelled
            self.font_chosen.emit(paths[font.filename])

    def _download_all(self):
        todo = [f for f in self._fonts if not self._fdl.is_downloaded(f)]
        if not todo:
            QMessageBox.information(self, "Download all", "All fonts are already cached.")
            return
        _, err = self._run_downloads(todo)
        if err:
            QMessageBox.critical(self, "Download all", f"Stopped on an error:\n{err}")
            return
        # marks now show ✓ cached; the user can then pick one to use

    def _run_downloads(self, fonts):
        """Download `fonts` off the GUI thread behind a cancellable progress dialog.
        Returns (paths_by_filename, error_or_None).  A cancel yields whatever
        completed before it (and no error)."""
        cancel = threading.Event()
        prog = QProgressDialog("Downloading…", "Cancel", 0, 100, self)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setAutoClose(False)
        prog.setAutoReset(False)
        prog.setValue(0)
        prog.canceled.connect(cancel.set)

        worker = _DownloadWorker(self._fdl, fonts, cancel, self)
        state = {"paths": {}}

        def on_progress(done, total, name, idx, n):
            prog.setLabelText(f"Downloading {name}  ({idx}/{n})…")
            prog.setValue(min(100, int(done * 100 / total)) if total > 0 else 0)

        def on_one(filename, path):     # direct connection → captured synchronously
            state["paths"][filename] = path

        def on_fail(msg):
            state["error"] = msg

        worker.progress.connect(on_progress)
        worker.one_done.connect(on_one, Qt.DirectConnection)
        worker.failed.connect(on_fail, Qt.DirectConnection)
        worker.start()
        while not worker.isFinished():
            QApplication.processEvents()
            worker.wait(50)
        QApplication.processEvents()
        prog.close()
        self._refresh_marks()
        return state["paths"], state.get("error")


class NotoDownloadDialog(QDialog):
    """Standalone modal wrapper around NotoDownloadPanel (kept for direct use /
    back-compat).  ``result_path`` holds the chosen font on accept."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Noto source font")
        self.resize(440, 460)
        self.result_path = None
        v = QVBoxLayout(self)
        self._panel = NotoDownloadPanel(self)
        self._panel.setMaximumWidth(16777215)       # full width in its own window
        self._panel.font_chosen.connect(self._on_chosen)
        v.addWidget(self._panel, 1)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        v.addWidget(close)
        # delegate the bits the tests/standalone callers reach for
        self._list = self._panel._list
        self._download = self._panel._download

    def _on_chosen(self, path):
        self.result_path = path
        self.accept()


class _DownloadWorker(QThread):
    """Downloads a list of fonts off the GUI thread, reporting progress via
    signals.  Cancellation is cooperative: ``cancel_event`` is polled inside
    download_font, so Cancel aborts after the current chunk."""
    progress = pyqtSignal(int, int, str, int, int)  # done, total, name, idx, count
    one_done = pyqtSignal(str, str)                  # filename, local path
    failed = pyqtSignal(str)                         # error message

    def __init__(self, fdl, fonts, cancel_event, parent=None):
        super().__init__(parent)
        self._fdl, self._fonts, self._cancel = fdl, list(fonts), cancel_event

    def run(self):
        n = len(self._fonts)
        for i, font in enumerate(self._fonts, 1):
            try:
                path = self._fdl.download_font(
                    font, cancel_event=self._cancel,
                    progress_cb=lambda d, t, nm=font.name, ix=i: self.progress.emit(
                        d, t, nm, ix, n))
            except self._fdl.DownloadCancelled:
                return                            # stop here; keep what completed
            except Exception as e:  # noqa: BLE001
                self.failed.emit(str(e))
                return
            self.one_done.emit(font.filename, path)


def main(argv=None):
    app = QApplication(argv if argv is not None else sys.argv)
    dlg = FontPackExtendDialog()        # keep a reference — without it PyQt GCs the
    dlg.show()                          # dialog and the window vanishes immediately
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
