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
from collections import deque

from PyQt5.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QListView,
    QTabWidget, QDoubleSpinBox, QComboBox, QCheckBox, QPushButton, QApplication,
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


# Amber tint for "peek" previews (rendered from a *source* font, not in the pack).
PEEK_RGB = (255, 168, 0)
# Dim grey for a glyph that exists but is overridden by a higher-priority pack font
# (front-to-back precedence — it never renders on the keyboard).
SHADOW_RGB = (105, 105, 105)
# Cyan for a slot that's empty in this font but *is* drawn by another pack font.
COVERED_RGB = (90, 170, 255)


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

    def __init__(self, label: str, pack, parent=None, all_fonts=None):
        super().__init__(parent)
        self._label = label
        self._pack = pack
        # Every font across all bundles (for range-aware peek); fall back to this
        # bundle's fonts when not supplied (standalone / tests).
        self._all_fonts = list(all_fonts) if all_fonts is not None else (
            list(pack.fonts) if isinstance(pack, fpr.Pack) else [])
        self._winner_cache = None      # cp -> font that actually renders it (lowest gidx)
        self._mode = "glyph"
        self._built_key = None         # (mode, scale, hide_empty, peek) last built
        self._settings_map = None      # lazy: global index -> render settings
        self._catalog_files = None     # lazy: download-catalog basenames (peek fallback)
        self._last_peek_count = 0      # previews rendered so far in the peek pass
        self._peek_queue = deque()     # (item, font, cp) empties awaiting a preview
        self._peek_gen = 0             # bumped on rebuild to cancel an in-flight pass
        self._dims = (8, 8, 1)         # (cell_w, cell_h, scale) of the current build
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
        self._zoom.setDecimals(0)              # whole-number scale (int() in _rebuild)
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

        self._peek_timer = QTimer(self)
        self._peek_timer.setSingleShot(True)
        self._peek_timer.timeout.connect(self._peek_step)

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

    def _catalog(self):
        """Download-catalog font basenames (noto-fonts.yaml), so peek can also offer a
        catalog font that no bundle uses (e.g. NotoSansMath) — adding such a font is
        then just a one-line catalog entry, no code change."""
        if self._catalog_files is None:
            try:
                from polyhost.services import font_downloader as fdl
                self._catalog_files = [f.filename for f in fdl.load_catalog()]
            except Exception:                       # noqa: BLE001
                self._catalog_files = []
        return self._catalog_files

    def _winners(self):
        """cp -> the font that actually renders it: the lowest-global-index font
        (across all bundles) with a non-empty glyph there (the firmware's
        front-to-back precedence)."""
        if self._winner_cache is None:
            win = {}
            for f in sorted(self._all_fonts, key=lambda f: f.global_index):
                for cp in range(f.first, f.last + 1):
                    g = f.glyphs[cp - f.first]
                    if g["width"] and g["height"] and cp not in win:
                        win[cp] = f
            self._winner_cache = win
        return self._winner_cache

    def _winner_desc(self, font) -> str:
        opts = self._settings().get(str(font.global_index))
        sf = opts.get("source_file") if opts else None
        return f"{sf} (g{font.global_index})" if sf else f"g{font.global_index}"

    @staticmethod
    def _is_color(opts) -> bool:
        return bool(opts.get("grayscale")) or int(opts.get("bits") or 1) == 32

    @staticmethod
    def _is_emoji(opts) -> bool:
        """An emoji source (NotoColorEmoji / NotoEmoji) by file name — both the
        colour and the b/w (NotoEmoji-Medium) variants count, since both render a
        codepoint in the emoji style rather than as a clean symbol."""
        return "emoji" in (opts.get("source_file") or "").lower()

    def _peek_candidates(self, primary, cp):
        """`(opts, src_path, source_file)` source fonts to try for slot `cp`, deduped
        by source.  Ordered by (style, tier, range, colour, global index):

        * style — when the slot's own font is *not* an emoji font, emoji sources rank
          LAST, so a symbol that also lives in an emoji font (even the low-gidx b/w
          NotoEmoji) previews from the clean symbol font, never the emoji.  For an
          emoji slot this is a no-op (every candidate keeps its existing order);
        * tier — the slot's own font, then the rest of this bundle, then every other
          font in the pack (so an emoji bundle keeps previewing from its own colour
          fonts, but a symbol gap can still be filled from another bundle);
        * range — fonts whose codepoint range actually *owns* `cp` first (prefer
          what's used in that range, the merged ALL_FONTS view), by global index;
        * colour — within a group, monochrome sources before colour, so a symbol that
          also exists in NotoColorEmoji previews from a clean outline, not a dithered
          colour emoji.

        Finally, any *downloaded* font from the catalog (noto-fonts.yaml) that no
        bundle uses is appended as a last-resort candidate (default render options) —
        so a font added to the catalog (e.g. NotoSansMath) is usable in peek with no
        code change, even though it's in no pack."""
        from polyhost.services import font_downloader as fdl
        cache = fdl.default_cache_dir()
        smap = self._settings()
        by_gidx = {f.global_index: f for f in self._all_fonts}
        bundle_ids = {f.global_index for f in self._pack.fonts}
        primary_emoji = self._is_emoji(smap.get(str(primary.global_index)) or {})

        def tier(gi):
            return 0 if gi == primary.global_index else 1 if gi in bundle_ids else 2

        # Enumerate EVERY source in the manifest (not just bundle fonts) — some
        # sources (e.g. NotoSansSymbols) are used only by resident fonts not present
        # in any bundle, yet still fill pack gaps.  Use the bundle font's range for
        # the in-range preference when we have it; otherwise treat as range-unknown.
        rows = []
        for k, opts in smap.items():
            if not opts or not opts.get("source_file"):
                continue
            gi = int(k)
            f = by_gidx.get(gi)
            in_range = bool(f) and f.first <= cp <= f.last
            # Defer emoji sources only when the slot's own font isn't itself emoji.
            style = 1 if (self._is_emoji(opts) and not primary_emoji) else 0
            rows.append((style, tier(gi), not in_range, self._is_color(opts), gi, opts))
        rows.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[4]))

        seen, out = set(), []
        for *_key, opts in rows:
            src = os.path.join(cache, opts["source_file"])
            if src in seen or not os.path.exists(src):
                continue
            seen.add(src)
            out.append((opts, src, opts["source_file"]))
        # Catalog fallback: any downloaded catalog font not already covered by the
        # manifest (default options, ranked last), so an unused-but-downloaded font is
        # still a peek candidate where it has the glyph.
        for fname in self._catalog():
            src = os.path.join(cache, fname)
            if src in seen or not os.path.exists(src):
                continue
            seen.add(src)
            out.append(({"source_file": fname, "size": 20}, src, fname))
        return out

    def _peek_pixmap(self, font, cp, cw, ch, scale):
        """Render empty slot `cp` from a source font as an amber preview, trying the
        slot's own font, then the bundle, then the whole pack (range/colour ordered).
        A cheap cached-face glyph check picks the right source before paying the
        render cost.  Returns `(pixmap, source_file)` or None."""
        from polyhost.services import fontpack_extend as ext
        for opts, src, sf in self._peek_candidates(font, cp):
            if not ext.source_has_glyph(src, cp):   # cheap precheck (cached face)
                continue
            try:
                pf = ext.peek_source_glyph(src, cp, opts, global_index=font.global_index)
            except Exception:                   # noqa: BLE001 — one bad glyph != dead grid
                continue
            if pf is not None:
                img = fprd.glyph_cell(pf, cp, cw, ch, scale=scale, mode=self._mode)
                return _pil_l_to_tinted_pixmap(img, PEEK_RGB), sf
        return None

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
        # Cancel any in-flight peek pass (a new generation invalidates the old timer).
        self._peek_gen += 1
        self._peek_timer.stop()
        self._peek_queue = deque()
        self._last_peek_count = 0
        self._model.clear()
        cw, ch = self._cell_dims(scale)
        self._dims = (cw, ch, scale)
        self._view.setIconSize(QSize(cw, ch + 11))

        # Build all cells up front (instant even for the ~1200-glyph emoji bundle),
        # then fill source peek previews incrementally.  Front-to-back precedence:
        # each cp is really drawn by the lowest-global-index font that has it, so we
        # tag overridden glyphs and fill empty-but-covered slots from the winner.
        winners = self._winners()
        for font in sorted(self._pack.fonts, key=lambda f: f.global_index):
            for cp in range(font.first, font.last + 1):
                g = font.glyphs[cp - font.first]
                empty = g["width"] == 0 or g["height"] == 0
                if empty and hide_empty:
                    continue
                win = winners.get(cp)
                tip = f"U+{cp:04X}"
                if not empty and win is not None and win.global_index != font.global_index:
                    # has a glyph but a higher-priority font wins → shadowed
                    img = fprd.glyph_cell(font, cp, cw, ch, scale=scale, mode=self._mode)
                    pm = _pil_l_to_tinted_pixmap(img, SHADOW_RGB)
                    tip += f"  (overridden by {self._winner_desc(win)})"
                elif not empty:
                    img = fprd.glyph_cell(font, cp, cw, ch, scale=scale, mode=self._mode)
                    pm = _pil_l_to_pixmap(img)
                elif win is not None:
                    # empty here, but another pack font draws it → show that, tinted
                    img = fprd.glyph_cell(win, cp, cw, ch, scale=scale, mode=self._mode)
                    pm = _pil_l_to_tinted_pixmap(img, COVERED_RGB)
                    tip += f"  (drawn by {self._winner_desc(win)} — none in this font)"
                else:
                    img = fprd.glyph_cell(font, cp, cw, ch, scale=scale, mode=self._mode)
                    pm = _pil_l_to_pixmap(img)
                    tip += "  (empty — no glyph)"
                it = QStandardItem()
                it.setIcon(QIcon(pm))
                it.setEditable(False)
                it.setData(font, _FONT_ROLE)
                it.setData(cp, _CP_ROLE)
                it.setToolTip(tip)
                self._model.appendRow(it)
                if empty and win is None and peek:   # only truly-uncovered slots peek
                    self._peek_queue.append((it, font, cp))
        if self._peek_queue:
            self._peek_timer.start(0)

    # Peek previews render a couple per event-loop tick so the (heavy, color) emoji
    # rendering stays responsive and any rebuild cancels the rest via _peek_gen.
    _PEEK_CHUNK = 2

    def _peek_step(self):
        gen = self._peek_gen
        cw, ch, scale = self._dims
        for _ in range(self._PEEK_CHUNK):
            if not self._peek_queue:
                return
            it, font, cp = self._peek_queue.popleft()
            res = self._peek_pixmap(font, cp, cw, ch, scale)
            if gen != self._peek_gen:                 # a rebuild superseded us
                return
            if res is not None:
                pm, sf = res
                it.setIcon(QIcon(pm))
                it.setToolTip(f"U+{cp:04X}  (preview from {sf} — not in pack)")
                self._last_peek_count += 1
        if self._peek_queue:
            self._peek_timer.start(0)

    def _drain_peek(self):
        """Render all queued peek previews synchronously (for tests)."""
        while self._peek_queue:
            self._peek_step()

    def cell_count(self) -> int:
        return self._model.rowCount() if self._view else 0


class FontPackInspectorDialog(QDialog):
    def __init__(self, sources=None, parent=None, flash_cb=None):
        """`sources`: list of (label, Pack) pairs; defaults to the shipped bundles.
        `flash_cb(bundle_index, plyf_bytes)`: optional, enables the Flash button in
        the "Save as…" dialog (the tray passes a device-flash callback)."""
        super().__init__(parent)
        self.setWindowTitle("PolyKybd — Font Pack Inspector")
        self.resize(1100, 800)
        self._flash_cb = flash_cb
        # In-memory working copies of edited bundles (keyed by source index): glyph
        # edits from the editor accumulate here; the "Save as…" dialog writes them.
        self._work = {}             # bi -> working list[PackFont]
        self._pending = {}          # bi -> [change description strings]
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
        self._open_btn = QPushButton("Open .plyf…")
        self._open_btn.setToolTip("Load a .plyf font-pack file (e.g. one you saved "
                                  "elsewhere) as a new tab to inspect")
        self._open_btn.clicked.connect(self._open_file)
        row.addWidget(self._open_btn)
        self._edit_btn = QPushButton("Edit…")
        self._edit_btn.setToolTip("Replace the selected glyph (double-clicking a glyph "
                                  "does the same)")
        self._edit_btn.clicked.connect(self._edit_selected)
        row.addWidget(self._edit_btn)
        self._extend_btn = QPushButton("Extend…")
        self._extend_btn.setToolTip("Build new glyphs from a font and add them to a "
                                    "bundle (in memory)")
        self._extend_btn.clicked.connect(lambda: self._open_extend())
        row.addWidget(self._extend_btn)
        self._saveas_btn = QPushButton("Save as…")
        self._saveas_btn.setToolTip("Review the current bundle's pending edits and "
                                    "save them to a .plyf (or flash) at a chosen version")
        self._saveas_btn.clicked.connect(self._save_as)
        self._saveas_btn.setEnabled(False)
        row.addWidget(self._saveas_btn)
        v.addLayout(row)

        # All fonts across every valid bundle — peek uses their ranges to prefer the
        # source that actually owns a codepoint (the merged ALL_FONTS view).  Kept on
        # the instance so an Open'd bundle extends the same merged view.
        self._all_fonts = [f for _l, p in sources if isinstance(p, fpr.Pack) for f in p.fonts]

        self._tabs = QTabWidget()
        for label, pack in sources:
            self._tabs.addTab(self._make_tab(label, pack), label)
        self._tabs.currentChanged.connect(self._render_current)
        # The tab widget is always shown (so Open .plyf… has somewhere to add a tab);
        # the glyph-level controls just stay disabled until at least one bundle exists.
        v.addWidget(self._tabs, 1)
        self._empty_note = QLabel("No font-pack bundles found — use “Open .plyf…”.")
        self._empty_note.setStyleSheet("color:#999; padding:6px;")
        v.addWidget(self._empty_note)
        self._sync_empty_state()
        if self._tabs.count():
            self._render_current()

    def _make_tab(self, label, pack):
        tab = _BundleTab(label, pack, all_fonts=self._all_fonts)
        tab.edit_requested.connect(self._on_edit)
        return tab

    def _sync_empty_state(self):
        has = self._tabs.count() > 0
        self._mode_combo.setEnabled(has)
        self._edit_btn.setEnabled(has)
        self._empty_note.setVisible(not has)

    def _open_file(self):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(self, "Open font pack", "",
                                              "Font pack (*.plyf);;All files (*)")
        if not path:
            return
        label = fpr._stem(path)
        try:
            pack = fpr.decode_pack_file(path, name_hint=label)
        except Exception as e:                       # noqa: BLE001
            QMessageBox.critical(self, "Open failed",
                                 f"Could not decode '{path}':\n{e}")
            return
        # Extend the shared merged view + the Extend sources so peek/precedence and the
        # extend dialog see the loaded bundle too.
        self._all_fonts.extend(pack.fonts)
        self._sources.append((label, pack))
        idx = self._tabs.addTab(self._make_tab(label, pack), label)
        self._sync_empty_state()
        self._tabs.setCurrentIndex(idx)
        crc = "ok" if pack.crc_ok else "BAD — file may be truncated/corrupt"
        QMessageBox.information(self, "Opened",
                                f"Loaded '{label}.plyf'\nabi v{pack.abi_version} · content "
                                f"v{pack.content_version} · {pack.font_count} fonts · "
                                f"{pack.codepoint_count()} glyphs · crc {crc}\n\n"
                                "Note: a .plyf carries no bundle name — this tab is named "
                                "after the file.")

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

    def _base_label(self, bi: int) -> str:
        """The bundle's own label (the tab text may carry a '● ' pending marker)."""
        return self._sources[bi][0]

    def _on_edit(self, font, cp: int):
        bi = self._tabs.currentIndex()
        self._open_extend(prefill={"bundle": self._base_label(bi), "first": cp,
                                   "last": cp, "global_index": font.global_index,
                                   "font_first": font.first, "font_last": font.last})

    def _open_extend(self, prefill=None):
        from polyhost.gui.fontpack_extend_dialog import FontPackExtendDialog
        dlg = FontPackExtendDialog(parent=self, prefill=prefill, sources=self._sources)
        if dlg.exec_() == QDialog.Accepted and dlg.result_font is not None:
            self._commit_edit(dlg.result_label, dlg.result_font, dlg.result_edit)

    # ---- working copies (edits accumulate here; Save as… writes them) ----
    def _working(self, bi: int):
        """Working-copy font list for bundle `bi` (shallow copy of the loaded fonts on
        first edit; splice/replace return new PackFonts, so the loaded pack is safe)."""
        if bi not in self._work:
            self._work[bi] = list(self._sources[bi][1].fonts)
        return self._work[bi]

    def _commit_edit(self, label: str, new, edit):
        """Merge an editor result into the named bundle's working copy and record it."""
        from PyQt5.QtWidgets import QMessageBox
        bi = next((i for i, (l, p) in enumerate(self._sources)
                   if l == label and isinstance(p, fpr.Pack)), None)
        if bi is None:
            QMessageBox.critical(self, "Edit", f"Unknown bundle {label!r}.")
            return
        fonts = self._working(bi)
        try:
            if edit:
                existing = next((f for f in fonts
                                 if f.global_index == edit["global_index"]), None)
                if existing is None or not existing.covers(edit["cp"]) or not new.glyphs:
                    raise ValueError("Edit target no longer matches the bundle")
                merged = fpr.replace_glyph(existing, edit["cp"], new.glyphs[0], new.bitmap)
                self._work[bi] = fpr.splice_font(
                    fpr.Pack(1, 0, len(fonts), 0, 0, True, fonts), merged)
                desc = f"edit U+{edit['cp']:04X} (g{edit['global_index']})"
            else:
                self._work[bi] = fpr.splice_font(
                    fpr.Pack(1, 0, len(fonts), 0, 0, True, fonts), new)
                desc = (f"font g{new.global_index}: U+{new.first:04X}–U+{new.last:04X} "
                        f"({new.glyph_count} slot(s))")
        except Exception as e:                       # noqa: BLE001
            QMessageBox.critical(self, "Edit failed", str(e))
            return
        self._pending.setdefault(bi, []).append(desc)
        self._mark_pending(bi)

    def _mark_pending(self, bi: int):
        """Reflect a bundle's pending-edit count in its tab title + the Save as button."""
        label = self._base_label(bi)
        n = len(self._pending.get(bi, []))
        self._tabs.setTabText(bi, f"● {label}" if n else label)
        self._saveas_btn.setEnabled(any(self._pending.values()))

    def _save_as(self):
        from PyQt5.QtWidgets import QMessageBox
        bi = self._tabs.currentIndex()
        if not (0 <= bi < len(self._sources)) or not isinstance(self._sources[bi][1], fpr.Pack):
            return
        label, base = self._sources[bi]
        if not self._pending.get(bi):
            QMessageBox.information(self, "Save as",
                                    f"No pending edits in '{label}'. Double-click a glyph "
                                    "(or Extend…) and confirm with OK first.")
            return
        dlg = FontPackSaveDialog(label, base, self._working(bi), self._pending[bi],
                                 flash_cb=self._flash_cb, bundle_index=bi, parent=self)
        dlg.exec_()
        if dlg.discarded:
            self._work.pop(bi, None)
            self._pending.pop(bi, None)
            self._mark_pending(bi)


class FontPackSaveDialog(QDialog):
    """Review a bundle's in-memory working copy and write it: metadata, the pending
    edit list, an editable save-as ``content_version`` (default current+1, one bump for
    all edits), and Save .plyf… / Flash / Discard.  (This is the accumulate/save side
    moved out of the glyph editor, which is now just OK/Cancel.)"""

    def __init__(self, label, base_pack, working_fonts, pending, flash_cb=None,
                 bundle_index=0, parent=None):
        from PyQt5.QtWidgets import QFormLayout, QSpinBox, QListWidget
        super().__init__(parent)
        self.setWindowTitle(f"Save font pack — {label}")
        self.resize(460, 440)
        self._label, self._base = label, base_pack
        self._fonts, self._flash_cb, self._bi = working_fonts, flash_cb, bundle_index
        self.discarded = False

        v = QVBoxLayout(self)
        self._meta = QLabel(); self._meta.setWordWrap(True)
        self._meta.setStyleSheet("color:#9ad;")
        v.addWidget(self._meta)

        form = QFormLayout()
        self._version = QSpinBox(); self._version.setRange(0, 65535)
        self._version.setValue(base_pack.content_version + 1)
        self._version.setToolTip("content_version written/flashed. Default = current+1 "
                                 "so a connected keyboard re-flashes it; one bump covers "
                                 "all the edits.")
        self._version.valueChanged.connect(self._refresh)
        form.addRow("Save as version", self._version)
        v.addLayout(form)

        v.addWidget(QLabel("Pending edits:"))
        lst = QListWidget(); lst.addItems(list(pending)); lst.setMaximumHeight(150)
        v.addWidget(lst, 1)

        row = QHBoxLayout()
        save = QPushButton("Save .plyf…"); save.clicked.connect(self._save)
        row.addWidget(save)
        if flash_cb is not None:
            fl = QPushButton("Flash to device"); fl.clicked.connect(self._flash)
            row.addWidget(fl)
        disc = QPushButton("Discard edits"); disc.clicked.connect(self._discard)
        row.addWidget(disc)
        row.addStretch(1)
        close = QPushButton("Close"); close.clicked.connect(self.reject)
        row.addWidget(close)
        v.addLayout(row)
        self._refresh()

    def _bytes(self) -> bytes:
        return fpr.encode_pack(self._fonts, self._version.value())

    def _refresh(self, *_):
        nonempty = sum(1 for f in self._fonts for g in f.glyphs
                       if g["width"] and g["height"])
        try:
            size = len(self._bytes())
        except Exception:                            # noqa: BLE001
            size = 0
        self._meta.setText(
            f"<b>{self._label}</b> — abi v{self._base.abi_version} · current content "
            f"v{self._base.content_version}<br>working: {len(self._fonts)} fonts · "
            f"{nonempty} glyphs · {size:,} B → save as v{self._version.value()}")

    def _save(self):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getSaveFileName(self, "Save font pack", f"{self._label}.plyf",
                                              "Font pack (*.plyf)")
        if not path:
            return
        try:
            data = self._bytes()
            with open(path, "wb") as f:
                f.write(data)
        except Exception as e:                       # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(e))
            return
        QMessageBox.information(self, "Saved",
                                f"Saved {path}\ncontent v{self._version.value()} · "
                                f"{len(data):,} B")

    def _flash(self):
        from PyQt5.QtWidgets import QMessageBox
        if self._flash_cb is None:
            return
        if QMessageBox.question(self, "Flash", f"Flash '{self._label}' (content v"
                                f"{self._version.value()}) to the keyboard?") \
                != QMessageBox.Yes:
            return
        try:
            self._flash_cb(self._bi, self._bytes())
        except Exception as e:                       # noqa: BLE001
            QMessageBox.critical(self, "Flash failed", str(e))
            return
        QMessageBox.information(self, "Flash", "Flash started — watch the tray/log.")
        self.accept()

    def _discard(self):
        from PyQt5.QtWidgets import QMessageBox
        if QMessageBox.question(self, "Discard edits",
                                f"Discard all pending edits to '{self._label}'?") \
                != QMessageBox.Yes:
            return
        self.discarded = True
        self.accept()


def main(argv=None):
    app = QApplication(argv if argv is not None else sys.argv)
    dlg = FontPackInspectorDialog()
    dlg.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
