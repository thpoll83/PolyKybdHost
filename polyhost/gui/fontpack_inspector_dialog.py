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

from PyQt5.QtCore import Qt, QEvent, QSize, QTimer, pyqtSignal
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
# Green border for a glyph edited in this session (working copy, unsaved).
MODIFIED_RGB = (70, 215, 110)


def _border_pixmap(pm, rgb, width: int = 2):
    """A copy of `pm` with a `width`px solid border in `rgb` — marks an edited cell."""
    from PyQt5.QtGui import QPainter, QPen, QColor
    out = QPixmap(pm)
    p = QPainter(out)
    pen = QPen(QColor(*rgb)); pen.setWidth(width)
    p.setPen(pen)
    off = (width + 1) // 2
    p.drawRect(off, off, out.width() - 2 * off - 1, out.height() - 2 * off - 1)
    p.end()
    return out


def _pil_to_pixmap(img) -> QPixmap:
    """PIL image -> QPixmap, preserving RGB (for the OLED-simulated preview) and
    falling back to the Grayscale8 path for 'L' images."""
    if img.mode == "RGB":
        data = img.tobytes()
        qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg)
    return _pil_l_to_pixmap(img)


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


_FONT_ROLE = int(Qt.UserRole)          # the winner font (what the keyboard draws)
_CP_ROLE = int(Qt.UserRole) + 1
_SHADOW_ROLE = int(Qt.UserRole) + 2    # the overdrawn font beneath (a stack), or None
_WIN_PM_ROLE = int(Qt.UserRole) + 3    # the cell's normal (winner) pixmap
_SHADOW_PM_ROLE = int(Qt.UserRole) + 4 # the overdrawn preview pixmap (shown on hover)


def _stack_pixmap(pm, rgb=(210, 210, 210), width: int = 3, depth: int = 1, gap: int = 4):
    """Solid right+bottom "stack" border on `pm`.  `depth` = how many glyphs are
    overdrawn beneath: one L-shaped line per overdrawn glyph (capped at 3, offset
    inward like stacked cards) so a 2-deep stack reads differently from a 1-deep one."""
    from PyQt5.QtGui import QPainter, QPen, QColor
    out = QPixmap(pm)
    p = QPainter(out)
    pen = QPen(QColor(*rgb)); pen.setWidth(width); pen.setCapStyle(Qt.FlatCap)
    p.setPen(pen)
    w, h = out.width(), out.height()
    for i in range(max(1, min(depth, 3))):
        off = width // 2 + i * gap
        p.drawLine(w - 1 - off, 0, w - 1 - off, h - 1 - off)   # right edge
        p.drawLine(0, h - 1 - off, w - 1 - off, h - 1 - off)   # bottom edge
    p.end()
    return out

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
        self._stack_cache = None       # cp -> [fonts drawing it, lowest gidx first]
        self._modified = set()         # cps edited this session (drawn with a border)
        self._peek_row = None          # row whose slot is showing its overdrawn glyph(s)
        self._peek_frames = None       # the overdrawn preview pixmaps being cycled
        self._peek_idx = 0
        self._range_rows = []          # rows highlighted as the selected font's range
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
        # Filter viewport mouse events for two position-aware behaviours on the
        # bottom-right "stack" corner: hover shows the overdrawn glyph in the slot,
        # double-click edits it (double-click elsewhere edits the winner).
        self._view.setMouseTracking(True)
        self._view.viewport().setMouseTracking(True)
        self._view.viewport().installEventFilter(self)
        self._view.selectionModel().selectionChanged.connect(self._on_selection)
        v.addWidget(self._view, 1)

        self._peek_timer = QTimer(self)
        self._peek_timer.setSingleShot(True)
        self._peek_timer.timeout.connect(self._peek_step)
        # Cycles the in-slot overdrawn preview when a codepoint has >1 overdrawn glyph.
        self._cycle_timer = QTimer(self)
        self._cycle_timer.timeout.connect(self._cycle_advance)

    # ---- public API used by the dialog ----
    def set_mode(self, mode: str):
        self._mode = mode
        self._rebuild()

    def set_all_fonts(self, all_fonts, rebuild=False):
        """Adopt an updated merged ALL_FONTS view (after an edit in *any* bundle) so
        this tab's precedence — the overridden (grey) and covered (cyan) cells, which
        render from the winning font — reflects it.  Rebuilds now if `rebuild`, else
        lazily on next show (built_key cleared)."""
        self._all_fonts = list(all_fonts)
        self._winner_cache = None
        self._stack_cache = None
        self._built_key = None
        if rebuild and self._view is not None:
            self._rebuild()

    def apply_working(self, fonts, modified, all_fonts=None):
        """Swap in this bundle's edited working copy (so its new glyph(s) show, with
        `modified` cps bordered), adopt the merged view, and re-render now."""
        if self._view is None:
            return
        if all_fonts is not None:
            self._all_fonts = list(all_fonts)
        self._pack = fpr.Pack(self._pack.abi_version, self._pack.content_version,
                              len(fonts), 0, 0, True, list(fonts))
        self._modified = set(modified)
        self._winner_cache = None
        self._stack_cache = None
        self._built_key = None              # force a full rebuild
        self._rebuild()

    def selected(self):
        idx = self._view.currentIndex() if self._view else None
        if idx is not None and idx.isValid() and idx.data(_FONT_ROLE) is not None:
            return idx.data(_FONT_ROLE), idx.data(_CP_ROLE)
        return None

    # ---- internals ----
    def eventFilter(self, obj, ev):
        if self._view is not None and obj is self._view.viewport():
            t = ev.type()
            if t == QEvent.MouseButtonDblClick:
                idx = self._view.indexAt(ev.pos())
                if idx.isValid():
                    self._edit_at(idx, ev.pos())
                    return True                     # we handle the edit; don't also select
            elif t == QEvent.MouseMove:
                self._hover(ev.pos())
            elif t == QEvent.Leave:
                self._hover(None)                   # cursor left the grid → un-peek
        return super().eventFilter(obj, ev)

    def _in_stack_corner(self, idx, pos) -> bool:
        r = self._view.visualRect(idx)
        corner = 0.4 * min(r.width(), r.height())
        return pos.x() >= r.right() - corner and pos.y() >= r.bottom() - corner

    def _hover(self, pos):
        """While the cursor is on a stacked cell's bottom-right stack corner, show the
        overdrawn (dim) glyph in that slot — cycling through them when there is more
        than one; restore the winner when the cursor leaves."""
        target = None
        if pos is not None:
            idx = self._view.indexAt(pos)
            if (idx.isValid() and idx.data(_SHADOW_ROLE) is not None
                    and self._in_stack_corner(idx, pos)):
                target = idx.row()
        if target == self._peek_row:
            return
        self._restore_peek()                        # un-peek the previous slot
        self._peek_row = target
        if target is not None:
            it = self._model.item(target)
            frames = it.data(_SHADOW_PM_ROLE) if it is not None else None
            if frames:
                self._peek_frames, self._peek_idx = frames, 0
                it.setIcon(QIcon(frames[0]))
                if len(frames) > 1:                 # >1 overdrawn → cycle through them
                    self._cycle_timer.start(850)

    def _restore_peek(self):
        self._cycle_timer.stop()
        self._peek_frames = None
        self._peek_idx = 0
        if self._peek_row is not None:
            it = self._model.item(self._peek_row)
            if it is not None and it.data(_WIN_PM_ROLE) is not None:
                it.setIcon(QIcon(it.data(_WIN_PM_ROLE)))

    def _cycle_advance(self):
        if self._peek_row is None or not self._peek_frames:
            return
        it = self._model.item(self._peek_row)
        if it is None:
            return
        self._peek_idx = (self._peek_idx + 1) % len(self._peek_frames)
        it.setIcon(QIcon(self._peek_frames[self._peek_idx]))

    def _on_selection(self, *_):
        """Highlight the whole range the selected glyph's font covers (front-to-back:
        the cells this font is the winner for) — since the pack is organised in ranges."""
        from PyQt5.QtGui import QBrush, QColor
        for r in self._range_rows:                  # clear the previous range highlight
            it = self._model.item(r)
            if it is not None:
                it.setBackground(QBrush())
        self._range_rows = []
        idx = self._view.currentIndex()
        font = idx.data(_FONT_ROLE) if idx.isValid() else None
        if font is None:
            return
        gi = font.global_index
        brush = QBrush(QColor(28, 54, 74))          # subtle range tint (≠ selection green)
        for r in range(self._model.rowCount()):
            it = self._model.item(r)
            f = it.data(_FONT_ROLE)
            if f is not None and f.global_index == gi:
                it.setBackground(brush)
                self._range_rows.append(r)

    def _edit_at(self, idx, pos):
        """Emit edit for the winner, or for the overdrawn (stack) glyph when the click
        lands in the bottom-right stack corner of a stacked cell."""
        winner = idx.data(_FONT_ROLE)
        if winner is None:
            return
        shadow = idx.data(_SHADOW_ROLE)
        font = shadow if (shadow is not None and self._in_stack_corner(idx, pos)) else winner
        self.edit_requested.emit(font, idx.data(_CP_ROLE))

    @staticmethod
    def _pm(img, tint=None):
        """Cell image -> QPixmap.  An OLED-simulated cell is already RGB (keep its
        colour); otherwise apply the semantic `tint` (borrowed/shadow/peek) or the
        plain grayscale path."""
        if img.mode == "RGB":                       # OLED / keycap-cover mode
            return _pil_to_pixmap(img)
        if tint is not None:
            return _pil_l_to_tinted_pixmap(img, tint)
        return _pil_l_to_pixmap(img)

    def _cell_dims(self, scale: int):
        if self._mode in ("keycap", "oled", "keycap_cover"):
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

    def _stacks(self):
        """cp -> the front-to-back stack of fonts that draw it: every font (across all
        bundles) with a non-empty glyph there, lowest global index first.  stack[0] is
        the winner (what the keyboard draws); stack[1:] are overdrawn (hidden)."""
        if self._stack_cache is None:
            st = {}
            for f in sorted(self._all_fonts, key=lambda f: f.global_index):
                for cp in range(f.first, f.last + 1):
                    g = f.glyphs[cp - f.first]
                    if g["width"] and g["height"]:
                        st.setdefault(cp, []).append(f)
            self._stack_cache = st
        return self._stack_cache

    def _winners(self):
        """cp -> the font that actually renders it (stack[0])."""
        if self._winner_cache is None:
            self._winner_cache = {cp: s[0] for cp, s in self._stacks().items()}
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
                return self._pm(img, PEEK_RGB), sf
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
        self._cycle_timer.stop()                     # nothing peeked/highlighted after rebuild
        self._peek_row = None
        self._peek_frames = None
        self._range_rows = []
        cw, ch = self._cell_dims(scale)
        self._dims = (cw, ch, scale)
        self._view.setIconSize(QSize(cw, ch + 11))

        # ONE cell per codepoint (a continuous, deduped range).  Each cp shows the
        # winner (front-to-back precedence: lowest-global-index font with a glyph) —
        # white if this bundle draws it, cyan if borrowed from another bundle.  When
        # more than one font has the glyph, a "stack" (doubled right/bottom border)
        # marks the overdrawn one(s); double-click edits the winner, the stack corner
        # edits the one beneath.
        stacks = self._stacks()
        this_ids = {f.global_index for f in self._pack.fonts}
        cps = set()
        for f in self._pack.fonts:
            cps.update(range(f.first, f.last + 1))
        for cp in sorted(cps):
            stack = stacks.get(cp, [])
            winner = stack[0] if stack else None
            empty = winner is None
            if empty and hide_empty:
                continue
            shadow = stack[1] if len(stack) > 1 else None
            modified = cp in self._modified
            frames = None                            # overdrawn previews (in-slot on hover)
            if winner is not None:
                img = fprd.glyph_cell(winner, cp, cw, ch, scale=scale, mode=self._mode)
                cross = winner.global_index not in this_ids
                pm = self._pm(img, COVERED_RGB if cross else None)
                prim = winner
                tip = (f"U+{cp:04X} — drawn by {self._winner_desc(winner)}"
                       + ("  (another bundle)" if cross else ""))
                if shadow is not None:
                    n = len(stack) - 1
                    pm = _stack_pixmap(pm, depth=n)
                    frames = [_stack_pixmap(self._pm(
                                  fprd.glyph_cell(s, cp, cw, ch, scale=scale, mode=self._mode),
                                  SHADOW_RGB), depth=n)
                              for s in stack[1:]]
                    tip += (f"; {n} overdrawn: " + ", ".join(self._winner_desc(s)
                                                             for s in stack[1:])
                            + " (hover the stack corner to see, double-click there to edit)")
                if modified:
                    tip += "  (edited — unsaved)"
            else:
                prim = next((f for f in self._pack.fonts if f.covers(cp)), self._pack.fonts[0])
                img = fprd.glyph_cell(prim, cp, cw, ch, scale=scale, mode=self._mode)
                pm = self._pm(img)
                tip = f"U+{cp:04X}  (empty — no glyph)" + \
                      ("  (edited — unsaved)" if modified else "")
            if modified:
                pm = _border_pixmap(pm, MODIFIED_RGB)
            it = QStandardItem()
            it.setIcon(QIcon(pm))
            it.setEditable(False)
            it.setData(prim, _FONT_ROLE)
            it.setData(cp, _CP_ROLE)
            it.setData(shadow, _SHADOW_ROLE)
            if frames:                               # store frames for the hover swap/cycle
                it.setData(pm, _WIN_PM_ROLE)
                it.setData(frames, _SHADOW_PM_ROLE)
            it.setToolTip(tip)
            self._model.appendRow(it)
            if empty and peek:                       # truly-uncovered slots peek
                self._peek_queue.append((it, prim, cp))
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
        self._modified = {}         # bi -> set of edited cps (bordered in the grid)
        v = QVBoxLayout(self)
        if sources is None:
            sources = load_shipped_packs()
        self._sources = sources         # keep the exact inspected bundles for Extend

        self._modes = [("Glyph grid (native size)", "glyph"),
                       ("Keycap preview (72×40)", "keycap"),
                       ("Keycap OLED (raw pixels)", "oled"),
                       ("Keycap through cover", "keycap_cover")]
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
        from PyQt5.QtWidgets import QMessageBox
        from polyhost.gui.file_dialogs import get_open_file_name
        path, _ = get_open_file_name(self, "Open font pack", "",
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

    def _bundle_of(self, font) -> int | None:
        """The source index of the bundle that owns `font`, so a stack edit targets
        the overdrawn font's *own* bundle, not the current tab.  Prefer an exact
        object-identity match (unambiguous even if two opened .plyf reuse the same
        global_index set); fall back to global_index only if no instance matches."""
        for i, (_l, p) in enumerate(self._sources):
            if isinstance(p, fpr.Pack) and any(f is font for f in p.fonts):
                return i
        for i, (_l, p) in enumerate(self._sources):
            if isinstance(p, fpr.Pack) and any(f.global_index == font.global_index
                                               for f in p.fonts):
                return i
        return None

    def _on_edit(self, font, cp: int):
        bi = self._bundle_of(font)
        if bi is None:
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
        # Mark which codepoints changed and re-render the tab from the working copy so
        # the new glyph is visible (bordered) without re-opening the inspector.
        if edit:
            cps = {edit["cp"]}
        else:
            cps = {c for c in range(new.first, new.last + 1)
                   if new.glyphs[c - new.first]["width"] and new.glyphs[c - new.first]["height"]}
        self._modified.setdefault(bi, set()).update(cps)
        self._rebuild_all_fonts()
        self._propagate(bi)
        self._mark_pending(bi)

    def _rebuild_all_fonts(self):
        """Rebuild the merged ALL_FONTS view (by global index) honouring every
        bundle's working copy, so cross-bundle precedence sees the edits."""
        by = {}
        for j, (_l, p) in enumerate(self._sources):
            if not isinstance(p, fpr.Pack):
                continue
            for f in self._work.get(j, p.fonts):
                by[f.global_index] = f
        self._all_fonts = sorted(by.values(), key=lambda f: f.global_index)

    def _propagate(self, bi):
        """Push the merged view to every tab: the edited bundle re-renders its working
        copy (bordering modified cps) now; the other tabs adopt the view so their
        overridden/covered cells reflect the edit — the visible one rebuilds now, the
        rest lazily when next shown."""
        cur = self._tabs.currentIndex()
        for i in range(self._tabs.count()):
            t = self._tabs.widget(i)
            if not isinstance(t, _BundleTab):
                continue
            if i == bi:
                fonts = self._work.get(bi, self._sources[bi][1].fonts)
                t.apply_working(fonts, self._modified.get(bi, set()), self._all_fonts)
            else:
                t.set_all_fonts(self._all_fonts, rebuild=(i == cur))

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
            self._modified.pop(bi, None)
            self._rebuild_all_fonts()              # drop these edits from the merged view
            self._propagate(bi)                    # reverts bi's grid + refreshes the rest
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
        from PyQt5.QtWidgets import QMessageBox
        from polyhost.gui.file_dialogs import get_save_file_name
        path, _ = get_save_file_name(self, "Save font pack", f"{self._label}.plyf",
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
