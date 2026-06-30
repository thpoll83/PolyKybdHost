"""Qt dialog for the font-pack *extend* round-trip: build one glyph (or font) from a
TTF/OTF and preview it as a keycap.  A focused glyph **editor** — OK keeps the built
glyph (the inspector merges it into its in-memory working copy), Cancel discards.

Ties fontgen (render) to a form.  fontgen and its deps (freetype-py/uharfbuzz/
fonttools — core deps, but imported lazily on Build so the dialog still opens and
reports clearly if an env is missing them).  The accumulate/version/save/flash side
lives in the inspector's "Save as…" dialog (`FontPackSaveDialog`), not here.

After ``exec_()`` returns ``Accepted``, the caller reads ``result_font`` (the built
PackFont), ``result_label`` (the chosen target bundle) and ``result_edit`` (the
``{global_index, cp}`` edit target, or None for a whole-font add).

Reached from the inspector's "Extend…"/"Edit…"; standalone:
``python -m polyhost.gui.fontpack_extend_dialog``.
"""
from __future__ import annotations

import json
import os
import sys

import threading

from PyQt5.QtCore import Qt, QEvent, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QLabel, QLineEdit,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QPushButton, QScrollArea, QSlider,
    QFileDialog, QMessageBox, QApplication, QWidget, QListWidget, QListWidgetItem,
    QProgressDialog,
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
_LANG_FLAGS_CACHE = None


def _render_settings() -> dict:
    """Load the shipped global-index -> render-options map (built from the
    firmware's fonts.yaml by generate_fonts.py).  Cached; missing/broken file
    degrades to {} so editing still works (just without prefilled options)."""
    global _RENDER_SETTINGS_CACHE
    if _RENDER_SETTINGS_CACHE is None:
        from polyhost.services import fontpack_extend as ext
        _RENDER_SETTINGS_CACHE = ext.load_render_settings()
    return _RENDER_SETTINGS_CACHE


def _lang_flags() -> dict:
    """The shipped flag-font render record (res/fontpack/lang_flags.json, mirror of
    the firmware's gen-lang-fonts.sh output).  The flag font isn't in fonts.yaml, so
    it has no entry in fontpack_render_settings.json; this carries its source +
    options + seq_first + the per-flag regional-indicator `sequence` so the editor
    can rebuild a single flag.  {} if absent."""
    global _LANG_FLAGS_CACHE
    if _LANG_FLAGS_CACHE is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "res", "fontpack", "lang_flags.json")
        try:
            with open(path, encoding="utf-8") as f:
                _LANG_FLAGS_CACHE = json.load(f)
        except Exception:                       # noqa: BLE001
            _LANG_FLAGS_CACHE = {}
    return _LANG_FLAGS_CACHE


class FontPackExtendDialog(QDialog):
    def __init__(self, res_dir: str | None = None, parent=None,
                 prefill=None, sources=None):
        """`prefill` (optional): {"bundle": label, "first": cp, "last": cp,
        "global_index": gidx} to pre-target a glyph for *editing* (replace).
        `sources` (optional): the exact (label, Pack) list the caller is inspecting
        — pass it so the target-bundle list matches.  Defaults to the shipped
        bundles when omitted.

        On accept (OK), the built glyph is exposed via the result_* attributes for
        the caller to merge; this dialog itself neither accumulates nor saves."""
        super().__init__(parent)
        self.setWindowTitle("PolyKybd — Build / Edit Glyph")
        self.resize(900, 640)
        self._built = None          # (bundle_index, new PackFont) — last previewed candidate
        self._edit_target = None    # {bundle_index, global_index, cp} in edit mode
        self._scale = 3.0           # preview zoom (scroll wheel over the preview, 0.5 steps)
        # Result of an OK accept, read by the caller (inspector) to merge the glyph:
        self.result_font = None     # the built PackFont
        self.result_label = None    # target bundle label
        self.result_edit = None     # {global_index, cp} edit target, or None for add
        # Only valid bundles are targets — sources/load_shipped_packs may yield
        # (label, Exception) placeholders for ones that failed to decode.
        raw = sources if sources is not None else load_shipped_packs(res_dir)
        self._packs = [(label, p) for label, p in raw if isinstance(p, fpr.Pack)]

        root = QHBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form, 0)

        self._src = QLineEdit()
        self._src.setReadOnly(True)
        self._src.setPlaceholderText("pick one from Source fonts below, or Browse…")
        browse = QPushButton("Browse…")
        browse.setToolTip("Use a custom font not in the Noto list")
        browse.clicked.connect(self._browse)
        srow = QHBoxLayout()
        srow.addWidget(self._src, 1)
        srow.addWidget(browse)
        sw = QWidget()
        sw.setLayout(srow)
        form.addRow("Source font", sw)

        self._mode = QComboBox(); self._mode.addItems(["Codepoint range", "HarfBuzz sequence"])
        self._mode.currentIndexChanged.connect(self._sync_mode)
        form.addRow("Mode", self._mode)
        self._first = QLineEdit("0x2600"); self._last = QLineEdit("0x2610")
        rrow = QHBoxLayout()
        rrow.addWidget(self._first, 1)
        rrow.addWidget(QLabel("–"))
        rrow.addWidget(self._last, 1)
        rw = QWidget(); rw.setLayout(rrow)
        form.addRow("Range first–last (hex)", rw)
        self._seq = QLineEdit("1F1E9 1F1EA"); self._seq.setEnabled(False)
        form.addRow("Sequence (hex cps; , = glyph)", self._seq)
        self._seq_first = QLineEdit("0xE000"); self._seq_first.setEnabled(False)
        form.addRow("Sequence base -F (hex)", self._seq_first)
        self._composite = QCheckBox("Composite -C (combine group into one glyph)")
        self._composite.setEnabled(False)
        self._composite.setToolTip("Composite all codepoints of each sequence group "
                                   "into a single glyph (mono) — used by the combining-"
                                   "mark / matra fonts (base U+25CC + mark).")
        form.addRow("", self._composite)

        self._size = self._spin(8, 200, 20); form.addRow("Size -s", self._size)
        # The four flag checkboxes in a 2x2 grid (was 4 separate rows).
        self._gray = QCheckBox("Grayscale / colour (-g)")
        self._gray.stateChanged.connect(self._sync_mode)
        self._norm = QCheckBox("Normalize -N"); self._inv = QCheckBox("Invert -I")
        self._edge = QCheckBox("Edge-preserve -E")
        flags = QGridLayout()
        flags.addWidget(self._gray, 0, 0); flags.addWidget(self._norm, 0, 1)
        flags.addWidget(self._inv, 1, 0); flags.addWidget(self._edge, 1, 1)
        fw = QWidget(); fw.setLayout(flags)
        form.addRow("Flags", fw)
        self._dither = QComboBox(); self._dither.addItems(_DITHER); self._dither.setEnabled(False)
        form.addRow("Dither -D", self._dither)
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
        # Grayscale/colour tone tuning (pre-dither), same knobs as fontconvert — each
        # number field gets a slider beside it over the same range.
        self._gamma = self._dspin(0.1, 5.0, 1.0, 0.1)
        form.addRow("Gamma -G (1 = off)", self._with_slider(self._gamma))
        self._contrast = self._dspin(0.1, 5.0, 1.0, 0.1)
        form.addRow("Contrast -c (1 = off)", self._with_slider(self._contrast))
        self._exposure = self._dspin(-5.0, 5.0, 0.0, 0.1)
        form.addRow("Exposure -e (0 = off)", self._with_slider(self._exposure))
        self._sharp = self._dspin(0.0, 10.0, 0.0, 0.1)
        form.addRow("Sharpen -U (0 = off)", self._with_slider(self._sharp))
        self._sat = self._dspin(0.0, 5.0, 0.0, 0.1)
        form.addRow("Saturation -B (0 = off)", self._with_slider(self._sat))

        self._bundle = QComboBox()
        for label, pack in self._packs:
            self._bundle.addItem(label, pack)
        self._bundle.currentIndexChanged.connect(self._default_index)
        form.addRow("Target bundle", self._bundle)
        self._gidx = self._spin(0, 65535, 0)
        form.addRow("Global font index", self._gidx)

        # Build a candidate from the source font and preview it.  Auto update
        # re-renders on any change so a manual Build press is rarely needed.
        brow = QHBoxLayout()
        self._build_btn = QPushButton("Build / Preview"); self._build_btn.clicked.connect(self._build)
        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setToolTip("Restore the render options to the settings this "
                                   "dialog opened with (the glyph's defaults)")
        self._reset_btn.clicked.connect(self._reset)
        self._auto = QCheckBox("Auto update")
        self._auto.setChecked(True)
        self._auto.setToolTip("Re-render the preview automatically when an option changes")
        brow.addWidget(self._build_btn); brow.addWidget(self._reset_btn)
        brow.addWidget(self._auto); brow.addStretch(1)
        form.addRow(brow)

        # OK keeps the built glyph (the inspector merges it into its working copy);
        # Cancel discards.  OK is enabled only once something has built.
        okrow = QHBoxLayout()
        okrow.addStretch(1)
        self._ok_btn = QPushButton("OK")
        self._ok_btn.setToolTip("Keep the built glyph (added to the bundle in memory; "
                                "save it from the inspector's “Save as…”)")
        self._ok_btn.clicked.connect(self._ok)
        self._ok_btn.setEnabled(False)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        okrow.addWidget(self._ok_btn); okrow.addWidget(cancel_btn)
        form.addRow(okrow)

        # Debounced auto-rebuild: coalesce rapid changes into one render.
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self._auto_build)
        self._wire_auto_update()

        right = QVBoxLayout()
        self._status = QLabel("Pick a font, set options, then Build / Preview.")
        self._status.setWordWrap(True)
        right.addWidget(self._status)
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._preview.setToolTip("Scroll here to zoom the preview")
        scroll = QScrollArea()
        scroll.setWidget(self._preview)
        scroll.setWidgetResizable(False)
        scroll.setStyleSheet("background:#000;")
        scroll.setMaximumHeight(260)        # compact preview; list gets the rest
        # Scroll wheel over the preview = zoom (instead of panning the small view).
        self._scroll = scroll
        scroll.viewport().installEventFilter(self)
        self._preview.installEventFilter(self)
        right.addWidget(scroll, 1)

        # Font browser sits permanently under the preview (no modal, no toggle):
        # clicking a font assigns it as the source.
        self._dl_panel = NotoDownloadPanel(self)
        self._dl_panel.font_chosen.connect(self._on_downloaded_font)
        right.addWidget(self._dl_panel, 3)
        root.addLayout(right, 1)

        self._default_index()
        if not self._packs:
            self._build_btn.setEnabled(False)
            self._status.setText("No valid shipped bundles available to extend.")
        elif prefill:
            self._apply_prefill(prefill)
        # Snapshot the option controls as opened (blank defaults, or an edit's
        # prefilled settings) so Reset can return to them.
        self._defaults = self._snapshot()

    def _apply_prefill(self, p: dict):
        """Pre-target a single glyph for editing: select its bundle, range = [cp, cp].
        Records `_edit_target` so OK returns it as an edit (the inspector inserts the
        built glyph into the existing font, preserving its siblings) rather than a
        whole-font add."""
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
                # No fonts.yaml record — e.g. the language-flag font, generated by
                # gen-lang-fonts.sh (sequence mode, not in fonts.yaml).  Fall back to
                # the shipped flag render settings when cp is a flag codepoint.
                opts = self._flags_record_for(cp)
                if opts:
                    self._set_controls_from_opts(opts)
            if opts and opts.get("sequence"):
                # Sequence-mode glyph (flag): switch modes and pre-fill the single
                # regional-indicator group for this codepoint so Build re-renders it.
                seq_base = p.get("font_first")
                if seq_base is None:
                    seq_base = int(opts.get("seq_first") or cp)
                self._setup_sequence_edit(cp, seq_base, opts)
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
        self._status.setText(f"Editing U+{cp:04X} in '{p.get('bundle')}' — Build to "
                             f"preview, then OK to keep it (Cancel to discard).{hint}")

    def _flags_record_for(self, cp: int):
        """The flag-font render record (lang_flags.json) if `cp` is a flag codepoint
        (within [seq_first, seq_first+count)), else None."""
        rec = _lang_flags()
        if not rec:
            return None
        base = int(rec.get("seq_first") or 0)
        n = int(rec.get("count") or 0)
        return rec if base <= cp < base + n else None

    def _setup_sequence_edit(self, cp: int, seq_base: int, opts: dict):
        """Editing a sequence-mode glyph: switch to HarfBuzz sequence mode and
        pre-fill the single group (e.g. the two regional-indicator codepoints of a
        flag) for `cp`, with seq base = cp so Build emits exactly that one glyph."""
        self._mode.setCurrentIndex(1)
        self._sync_mode()
        groups = [g.strip() for g in str(opts.get("sequence", "")).split(",") if g.strip()]
        idx = cp - seq_base
        if 0 <= idx < len(groups):
            self._seq.setText(groups[idx])
        self._seq_first.setText(f"0x{cp:04X}")
        # Composite (-C) when the record says so, else inferred: combining-mark/matra
        # sequences composite a mark onto the dotted circle U+25CC (every group starts
        # with it); regional-indicator flag groups don't, so they stay non-composite.
        comp = opts.get("composite")
        if comp is None:
            comp = bool(groups) and all(g.split() and g.split()[0].upper() == "25CC"
                                        for g in groups)
        self._composite.setChecked(bool(comp))

    def _apply_saved_settings(self, global_index: int):
        """Prefill the render controls from the settings the font was generated with
        (shipped fontpack_render_settings.json, keyed by global index).  Returns the
        opts dict, or None when there's no record for this index."""
        opts = _render_settings().get(str(global_index))
        if not opts:
            return None
        self._set_controls_from_opts(opts)
        return opts

    def _set_controls_from_opts(self, opts: dict):
        """Apply a render-options record (size, dither, flags, render size, yAdvance,
        tone knobs, …) to the controls, and auto-fill the source font from the
        download cache when its ``source_file`` is already present."""
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
        self._gamma.setValue(float(opts.get("gamma") or 1.0))
        self._contrast.setValue(float(opts.get("contrast") or 1.0))
        self._exposure.setValue(float(opts.get("exposure") or 0.0))
        self._sharp.setValue(float(opts.get("sharpness") or 0.0))
        self._sat.setValue(float(opts.get("saturation") or 0.0))
        self._sync_mode()          # reflect the grayscale toggle (enables dither)
        sf = opts.get("source_file")
        if sf:
            self._dl_panel.select_filename(sf)       # default-select it in the browser
            if not self._src.text().strip():
                from polyhost.services import font_downloader as fdl
                cached = os.path.join(fdl.default_cache_dir(), sf)
                if os.path.exists(cached):
                    self._src.setText(cached)

    # ---- helpers ----
    @staticmethod
    def _spin(lo, hi, val):
        s = QSpinBox(); s.setRange(lo, hi); s.setValue(val); return s

    @staticmethod
    def _dspin(lo, hi, val, step):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(step)
        s.setDecimals(2)
        s.setValue(val)
        s.setFixedWidth(72)            # all float inputs share one width
        return s

    @staticmethod
    def _with_slider(spin):
        """Wrap a QDoubleSpinBox with a horizontal slider beside it, kept in sync over
        the spin's range (slider int = value / singleStep).  Returns the container."""
        step = spin.singleStep() or 0.1
        scale = round(1.0 / step)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(round(spin.minimum() * scale), round(spin.maximum() * scale))
        sl.setSingleStep(1)            # one slider notch == one spin step (0.1)
        sl.setPageStep(1)
        sl.setValue(round(spin.value() * scale))
        guard = {"on": False}

        def from_slider(v):
            if guard["on"]:
                return
            guard["on"] = True
            spin.setValue(v / scale)
            guard["on"] = False

        def from_spin(v):
            if guard["on"]:
                return
            guard["on"] = True
            sl.setValue(round(v * scale))
            guard["on"] = False

        sl.valueChanged.connect(from_slider)
        spin.valueChanged.connect(from_spin)
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(spin)
        h.addWidget(sl, 1)
        return w

    # ---- reset to the settings the dialog opened with ----
    def _snapshot(self) -> dict:
        return dict(size=self._size.value(), gray=self._gray.isChecked(),
                    dither=self._dither.currentIndex(), norm=self._norm.isChecked(),
                    inv=self._inv.isChecked(), edge=self._edge.isChecked(),
                    outline=self._outline.value(), rsize=self._rsize.value(),
                    yadv=self._yadv.value(), maxw=self._maxw.value(),
                    weight=self._weight.value(), xshift=self._xshift.value(),
                    gamma=self._gamma.value(), contrast=self._contrast.value(),
                    exposure=self._exposure.value(), sharp=self._sharp.value(),
                    sat=self._sat.value(), composite=self._composite.isChecked())

    def _restore(self, s: dict):
        self._size.setValue(s["size"]); self._gray.setChecked(s["gray"])
        self._dither.setCurrentIndex(s["dither"]); self._norm.setChecked(s["norm"])
        self._inv.setChecked(s["inv"]); self._edge.setChecked(s["edge"])
        self._outline.setValue(s["outline"]); self._rsize.setValue(s["rsize"])
        self._yadv.setValue(s["yadv"]); self._maxw.setValue(s["maxw"])
        self._weight.setValue(s["weight"]); self._xshift.setValue(s["xshift"])
        self._gamma.setValue(s["gamma"]); self._contrast.setValue(s["contrast"])
        self._exposure.setValue(s["exposure"]); self._sharp.setValue(s["sharp"])
        self._sat.setValue(s["sat"]); self._composite.setChecked(s["composite"])
        self._sync_mode()

    def _reset(self):
        self._restore(self._defaults)
        self._status.setText("Reset to the default render settings.")

    def _sync_mode(self, *_):
        seq = self._mode.currentIndex() == 1
        for w in (self._seq, self._seq_first, self._composite):
            w.setEnabled(seq)
        for w in (self._first, self._last):
            w.setEnabled(not seq)
        gray = self._gray.isChecked()
        self._dither.setEnabled(gray)

    def _default_index(self, *_):
        pack = self._bundle.currentData()
        if isinstance(pack, fpr.Pack) and pack.fonts:
            self._gidx.setValue(max(f.global_index for f in pack.fonts) + 1)
        # Switching the target bundle invalidates the current candidate (and leaves
        # edit mode → a whole-font add) so OK can't keep a glyph for the wrong bundle.
        self._built = None
        self._edit_target = None
        self._ok_btn.setEnabled(False)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select font", "",
                                              "Fonts (*.ttf *.otf);;All files (*)")
        if path:
            self._src.setText(path)

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
            gamma_val=self._gamma.value(), contrast=self._contrast.value(),
            exposure=self._exposure.value(), sharpness=self._sharp.value(),
            saturation_boost=self._sat.value(),
            seq_first=int(self._seq_first.text(), 16) if self._seq.isEnabled() else 0,
            composite=self._composite.isChecked() and self._seq.isEnabled(),
            bits=32)

    # ---- auto-update ----
    def _wire_auto_update(self):
        """Schedule a debounced rebuild whenever any render option changes."""
        for w in (self._src, self._first, self._last, self._seq, self._seq_first):
            w.textChanged.connect(self._schedule_auto)
        for w in (self._mode, self._dither, self._bundle):
            w.currentIndexChanged.connect(self._schedule_auto)
        for w in (self._size, self._outline, self._rsize, self._yadv, self._maxw,
                  self._weight, self._xshift, self._gamma, self._contrast,
                  self._exposure, self._sharp, self._sat, self._gidx):
            w.valueChanged.connect(self._schedule_auto)
        for w in (self._gray, self._norm, self._inv, self._edge, self._composite):
            w.stateChanged.connect(self._schedule_auto)
        self._auto.stateChanged.connect(self._schedule_auto)

    def _schedule_auto(self, *_):
        if self._auto.isChecked():
            self._auto_timer.start(250)        # coalesce bursts of changes

    def _auto_build(self):
        src = self._src.text().strip()
        if self._auto.isChecked() and src and os.path.exists(src):
            self._build(auto=True)             # silent on errors (status only)

    # ---- actions ----
    def _build(self, *_a, auto=False):
        def fail(title, msg):
            if auto:
                self._status.setText(msg)
            else:
                QMessageBox.warning(self, title, msg)

        src = self._src.text().strip()
        if not src or not os.path.exists(src):
            fail("Build", "Pick an existing font file first.")
            return
        missing = _missing_fontgen_deps()
        if missing:
            fail("Build", "Building glyphs needs these font-generation dependencies, "
                 "which aren't installed in this environment:\n\n    pip install "
                 + " ".join(missing) + "\n\n(They're normally pulled in by installing "
                 "PolyKybdHost: pip install -e .)")
            return
        try:
            from polyhost.services import fontpack_extend as ext
            from polyhost.services import fontpack_render as rd  # noqa: F401  (deps check)
        except Exception as e:  # noqa: BLE001
            fail("Build", "Font building dependencies are missing or broken:\n"
                 f"  pip install -e .\n\n({e})")
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
            if auto:
                self._status.setText(f"(auto preview) {e}")
            else:
                QMessageBox.critical(self, "Build failed", str(e))
            return
        self._built = (self._bundle.currentIndex(), new)
        self._render_preview()
        self._status.setText(f"Built {new.glyph_count} glyph(s), U+{new.first:04X}–"
                             f"{new.last:04X}, global index {gidx}. OK to keep it in the "
                             f"'{self._bundle.currentText()}' bundle, Cancel to discard.")
        self._ok_btn.setEnabled(True)

    def _render_preview(self):
        """(Re)draw the preview from the already-built pack at the current zoom —
        keycap render + the source-font glyph beside it.  Cheap to call on zoom
        (no re-render of the keycap glyph; the source reference re-rasterises)."""
        if not self._built:
            return
        from polyhost.services import fontpack_render as rd
        _bi, new = self._built
        src = self._src.text().strip()
        try:
            opts = self._options()
        except Exception:                           # noqa: BLE001
            opts = None
        seq = self._seq.text().strip() if self._seq.isEnabled() else None
        sheet = rd.preview_sheet(fpr.Pack(1, 0, 1, 0, 0, True, [new]),
                                 source_path=src or None, opts=opts,
                                 cols=12, scale=self._scale, sequence=seq,
                                 title=f"built · {new.glyph_count} glyphs")
        self._preview.setPixmap(_pil_l_to_pixmap(sheet))
        self._preview.resize(self._preview.pixmap().size())

    def _zoom(self, step: float) -> bool:
        """Change the preview zoom by `step` (clamped 0.5..7.0) and re-render.  Returns
        True if it changed something (so the wheel event is consumed)."""
        ns = round(max(0.5, min(7.0, self._scale + step)), 1)
        if ns == self._scale or self._built is None:
            return False
        self._scale = ns
        self._render_preview()
        self._status.setText(f"Zoom {self._scale:g}×  (scroll over the preview to change)")
        return True

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Wheel and self._built is not None:
            self._zoom(0.5 if ev.angleDelta().y() > 0 else -0.5)
            return True                             # consume: wheel zooms, not pans
        return super().eventFilter(obj, ev)

    # ---- accept ----
    def _ok(self):
        """Keep the built glyph: expose it via result_* and accept.  The caller (the
        inspector) merges it into the bundle's in-memory working copy."""
        if not self._built:
            return
        bi, new = self._built
        self.result_font = new
        self.result_label = self._packs[bi][0]
        self.result_edit = (None if self._edit_target is None else
                            {"global_index": self._edit_target["global_index"],
                             "cp": self._edit_target["cp"]})
        self.accept()


class NotoDownloadPanel(QWidget):
    """Embeddable Noto source-font picker/downloader (no modal).  Lists the shared
    catalog (noto-fonts.yaml), marks cached fonts, and emits ``font_chosen(path)``
    when a font is clicked (downloading it first if needed) — it lives permanently
    under the extend dialog's preview so picking a source is a single click."""
    font_chosen = pyqtSignal(str)       # local path of the picked/downloaded font

    def __init__(self, parent=None):
        super().__init__(parent)
        from polyhost.services import font_downloader as fdl
        self._fdl = fdl
        try:
            self._fonts = fdl.load_catalog()
        except Exception as e:  # noqa: BLE001
            self._fonts = []
            QMessageBox.warning(self, "Download", f"Could not read the font catalog:\n{e}")

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        # Header row: label + "Download all" ON TOP of the list, so it's clearly
        # separate from the dialog's OK/Cancel buttons below.
        top = QHBoxLayout()
        top.addWidget(QLabel("Source fonts — click to use (✓ = downloaded; uncached "
                             "downloads first)"), 1)
        self._all_btn = QPushButton("Download all")
        self._all_btn.setToolTip("Fetch every Noto font in the list into the cache")
        self._all_btn.clicked.connect(self._download_all)
        self._all_btn.setEnabled(bool(self._fonts))
        top.addWidget(self._all_btn)
        v.addLayout(top)
        self._list = QListWidget()
        # Click = use it (download first if needed) — no separate "Use" button.
        self._list.itemClicked.connect(self._use_clicked)
        self._list.itemDoubleClicked.connect(self._use_clicked)
        for f in self._fonts:
            item = QListWidgetItem(self._label(f))
            item.setData(Qt.UserRole, f)
            self._list.addItem(item)
        v.addWidget(self._list, 1)

    def _label(self, font) -> str:
        mark = "  ✓ cached" if self._fdl.is_downloaded(font) else ""
        return f"{font.name}  ({font.filename}){mark}"

    def current_filename(self):
        it = self._list.currentItem()
        return it.data(Qt.UserRole).filename if it is not None else None

    def select_filename(self, filename: str) -> bool:
        """Highlight the catalog entry whose file is `filename` (the font a glyph
        was generated with), so it's the default selection in the browser."""
        for i in range(self._list.count()):
            f = self._list.item(i).data(Qt.UserRole)
            if f.filename == filename:
                self._list.setCurrentRow(i)
                self._list.scrollToItem(self._list.item(i))
                return True
        return False

    def _refresh_marks(self):
        for i in range(self._list.count()):
            it = self._list.item(i)
            it.setText(self._label(it.data(Qt.UserRole)))

    def _use_clicked(self, item):
        """Use the clicked font: emit it if cached, else download then emit."""
        if item is None:
            return
        font = item.data(Qt.UserRole)
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

    def _download(self):
        """Use the current row (entry point for the standalone dialog / tests)."""
        self._use_clicked(self._list.currentItem())

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
