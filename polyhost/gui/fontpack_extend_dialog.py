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

import json
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

_RENDER_SETTINGS_CACHE = None


def _render_settings() -> dict:
    """Load the shipped global-index -> render-options map (built from the
    firmware's fonts.yaml by generate_fonts.py).  Cached; missing/broken file
    degrades to {} so editing still works (just without prefilled options)."""
    global _RENDER_SETTINGS_CACHE
    if _RENDER_SETTINGS_CACHE is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "res", "fontpack", "fontpack_render_settings.json")
        try:
            with open(path, encoding="utf-8") as f:
                _RENDER_SETTINGS_CACHE = json.load(f).get("by_global_index", {})
        except Exception:                       # noqa: BLE001
            _RENDER_SETTINGS_CACHE = {}
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
        dl.setToolTip("Fetch a Noto source font (same list as the firmware's "
                      "dl-fonts.sh) into the local cache and use it here")
        dl.clicked.connect(self._download_noto)
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
        applied = False
        if "global_index" in p:
            gi = p["global_index"]
            self._gidx.setValue(gi)
            self._edit_target = {"bundle_index": bi, "global_index": gi, "cp": cp}
            applied = self._apply_saved_settings(gi)
        hint = (" Original generation settings pre-filled." if applied else
                " (no saved settings for this font — set options manually.)")
        self._status.setText(f"Editing U+{cp:04X} in '{p.get('bundle')}' — pick a source "
                             f"font, Build to peek, then Save/Flash to take it.{hint}")

    def _apply_saved_settings(self, global_index: int) -> bool:
        """Prefill the render controls from the settings the font was generated
        with (shipped fontpack_render_settings.json, keyed by global index).  The
        glyph's *source font* isn't bundled, so the user still picks the .ttf;
        everything else (size, dither, flags, render size, yAdvance, …) is restored.
        Returns True if a settings record was found."""
        opts = _render_settings().get(str(global_index))
        if not opts:
            return False
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
        self._sync_mode()          # reflect the grayscale toggle (enables dither)
        return True

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

    def _download_noto(self):
        dlg = NotoDownloadDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.result_path:
            self._src.setText(dlg.result_path)

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


class NotoDownloadDialog(QDialog):
    """Pick a Noto source font from the shared catalog (noto-fonts.yaml) and
    download it to the local cache.  On accept, ``result_path`` holds the local
    file the caller should use; already-cached fonts are marked and picked
    instantly (no re-download)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Noto source font")
        self.resize(440, 460)
        self.result_path = None
        from polyhost.services import font_downloader as fdl
        self._fdl = fdl
        try:
            self._fonts = fdl.load_catalog()
        except Exception as e:  # noqa: BLE001
            self._fonts = []
            QMessageBox.warning(self, "Download", f"Could not read the font catalog:\n{e}")

        v = QVBoxLayout(self)
        v.addWidget(QLabel("Downloads into:\n" + fdl.default_cache_dir()))
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
        self._dl_btn = QPushButton("Download / Use selected")
        self._dl_btn.clicked.connect(self._download)
        self._dl_btn.setEnabled(bool(self._fonts))
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        btns.addStretch(1); btns.addWidget(cancel); btns.addWidget(self._dl_btn)
        v.addLayout(btns)

    def _label(self, font) -> str:
        mark = "  ✓ cached" if self._fdl.is_downloaded(font) else ""
        return f"{font.name}  ({font.filename}){mark}"

    def _download(self):
        item = self._list.currentItem()
        if item is None:
            return
        font = item.data(Qt.UserRole)
        # Already cached → use it straight away, no network.
        if self._fdl.is_downloaded(font):
            self.result_path = self._fdl.local_path(font)
            self.accept()
            return

        # Run the transfer off the GUI thread so the dialog stays responsive and
        # Cancel can actually abort it (the worker polls the cancel event).
        cancel = threading.Event()
        prog = QProgressDialog(f"Downloading {font.name}…", "Cancel", 0, 100, self)
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setAutoClose(False)
        prog.setAutoReset(False)
        prog.setValue(0)
        prog.canceled.connect(cancel.set)

        worker = _DownloadWorker(self._fdl, font, cancel, self)
        result = {}

        def on_progress(done, total):
            prog.setValue(min(100, int(done * 100 / total)) if total > 0 else 0)

        def on_ok(path):
            result["path"] = path

        def on_fail(msg):
            result["error"] = msg

        # progress drives a GUI widget → must run on the main thread (queued);
        # ok/fail only stash into a dict → direct so the result is captured
        # synchronously before the worker reports finished (no post-loop race).
        worker.progress.connect(on_progress)
        worker.finished_ok.connect(on_ok, Qt.DirectConnection)
        worker.failed.connect(on_fail, Qt.DirectConnection)
        worker.start()
        while not worker.isFinished():
            QApplication.processEvents()
            worker.wait(50)
        QApplication.processEvents()              # drain any last queued progress
        prog.close()

        if "error" in result:
            QMessageBox.critical(self, "Download failed",
                                 f"Could not download {font.name}:\n{result['error']}")
            return
        if "path" not in result:
            return                                # cancelled — leave dialog open
        item.setText(self._label(font))           # now shows ✓ cached
        self.result_path = result["path"]
        self.accept()


class _DownloadWorker(QThread):
    """Downloads one font off the GUI thread, reporting progress via signals.
    Cancellation is cooperative: ``cancel_event`` is polled inside download_font."""
    progress = pyqtSignal(int, int)     # done, total
    finished_ok = pyqtSignal(str)       # local path
    failed = pyqtSignal(str)            # error message

    def __init__(self, fdl, font, cancel_event, parent=None):
        super().__init__(parent)
        self._fdl, self._font, self._cancel = fdl, font, cancel_event

    def run(self):
        try:
            path = self._fdl.download_font(
                self._font, cancel_event=self._cancel,
                progress_cb=lambda d, t: self.progress.emit(d, t))
        except self._fdl.DownloadCancelled:
            return                                # cancelled → no signal, dialog stays
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
            return
        self.finished_ok.emit(path)


def main(argv=None):
    app = QApplication(argv if argv is not None else sys.argv)
    dlg = FontPackExtendDialog()        # keep a reference — without it PyQt GCs the
    dlg.show()                          # dialog and the window vanishes immediately
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
