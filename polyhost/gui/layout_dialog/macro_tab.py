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
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from polyhost.device.command_ids import MacroStyle
from polyhost.services import macro_label as ml
from polyhost.services import macro_look as mk

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
        self._mid = None
        self._fonts: list = []
        self._font_source = "packs"
        self._ladder: list = []
        self._loaded = False
        self._icon = 0

        # A missing font only costs the preview, so the tab still edits macros on a
        # machine without the firmware checkout beside it. The packs ship with this
        # repo, so the icon half survives even when the firmware headers do not.
        try:
            self._font = ml.load_nano_font(ml.default_font_dir())
        except Exception:
            self._font = None
        try:
            self._mid = mk.load_ui_font(ml.default_font_dir(), "util_font.h",
                                        mk.MID_FONT_SYMBOL)
        except Exception:
            self._mid = None
        try:
            self._fonts, self._font_source = mk.load_render_fonts()
            self._ladder = mk.caption_ladder(mk.load_pack_fonts(), mid_font=self._mid,
                                             nano_font=self._font)
        except Exception:
            self._fonts, self._ladder = [], []
            self._font_source = "none"

        # The actions live OUTSIDE the scrolled column, in a fixed footer: the column
        # can be taller than the page is ever given (see the scroll note below), and
        # Save / Clear / Use-on-key falling below the fold makes the tab look like it
        # cannot do anything. Only the editing controls scroll.
        page = QVBoxLayout(self)
        outer = QHBoxLayout()
        page.addLayout(outer, 1)

        self.list = QListWidget()
        self.list.setMaximumWidth(190)
        self.list.currentRowChanged.connect(self._on_select)
        outer.addWidget(self.list)

        # Scrolled, because the column can genuinely need more height than it will
        # ever be given: the keycode browser caps itself at 400 px, and the two
        # word-wrapped notes below report a ONE-LINE minimum to the layout, so a
        # narrow window silently under-allocates them and they print over each
        # other and over the preview. A scrollbar that appears only when it is
        # needed is the honest version of that.
        panel = QWidget()
        right = QVBoxLayout(panel)
        right.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        right.addWidget(self._caption("KEYCAP"))
        # EVERYTHING that composes the keycap sits in one column beside the preview,
        # and the label shares its line with the meter. Not cosmetic: the browser caps
        # itself at 400 px, so this page is handed ~351 px on every open -- always
        # short, never occasionally -- and the fixed-size preview cannot give the
        # deficit back. Stacked full-width, the meter row was drawn over the bottom of
        # the keycap, which is exactly where the label renders. Beside the preview the
        # four controls share its 80 px and cost no height at all, which is what keeps
        # the column off a scrollbar.
        top_row = QHBoxLayout()
        left_col = QVBoxLayout()

        name_row = QHBoxLayout()
        self.label_edit = QLineEdit()
        self.label_edit.setMaxLength(ml.LABEL_MAX_CHARS)
        self.label_edit.setPlaceholderText("work mail")
        self.label_edit.textChanged.connect(self._on_label_changed)
        name_row.addWidget(self.label_edit, 3)

        self.width_meter = QProgressBar()
        self.width_meter.setRange(0, ml.PANEL_W)
        self.width_meter.setTextVisible(True)
        name_row.addWidget(self.width_meter, 2)
        left_col.addLayout(name_row)

        self.style_box = QComboBox()
        # A macro owns its whole keycap, so the cell can be more than a legend. Order
        # IS the wire value.
        self.style_box.addItem("Number above the label", MacroStyle.INDEX.value)
        self.style_box.addItem("Icon above the label", MacroStyle.ICON.value)
        self.style_box.addItem("Label only, as large as it fits", MacroStyle.TEXT.value)
        self.style_box.addItem("Icon only, filling the key", MacroStyle.ICON_ONLY.value)
        self.style_box.currentIndexChanged.connect(self._on_style_changed)
        left_col.addWidget(self.style_box)

        icon_row = QHBoxLayout()
        self.icon_btn = QPushButton("Choose icon…")
        self.icon_btn.clicked.connect(self._on_pick_icon)
        icon_row.addWidget(self.icon_btn, 1)
        self.icon_clear = QPushButton("Clear")
        self.icon_clear.clicked.connect(self._on_clear_icon)
        icon_row.addWidget(self.icon_clear)
        left_col.addLayout(icon_row)
        left_col.addStretch(1)
        top_row.addLayout(left_col, 1)

        self.preview = QLabel()
        self.preview.setFixedSize(ml.PANEL_W * PREVIEW_SCALE, ml.PANEL_H * PREVIEW_SCALE)
        self.preview.setToolTip("How the keycap will look")
        top_row.addWidget(self.preview)
        right.addLayout(top_row)

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

        # The pool is shared by every macro, so this is the one readout on the page
        # that does NOT describe the macro being edited -- it belongs with the actions
        # rather than in the per-macro column, and it costs that column no height.
        self.storage = QProgressBar()
        self.storage.setTextVisible(True)
        self.storage.setToolTip(
            "All the macros share one pool on the keyboard, so a long one leaves "
            "less for the others")
        # Sized, not left to the sizeHint: the hint is ~107 px, which clips the text
        # the bar exists to show. Bounded above so it cannot crowd the buttons.
        self.storage.setMinimumWidth(260)
        self.storage.setMaximumWidth(340)
        buttons.addWidget(self.storage, 1)
        page.addLayout(buttons)

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
        # Short, because it now sits beside the buttons rather than under its own
        # caption -- the long sentence wrapped to two lines and clipped there. The
        # tooltip carries it instead.
        self.storage.setFormat(f"{used} / {cap} bytes  ·  %p%")

    # -- selection ----------------------------------------------------------

    def _on_select(self, row: int):
        if not (0 <= row < len(self._macros)):
            return
        self._current = row
        m = self._macros[row]
        self._icon = m.get("icon", 0)
        style = m.get("style", 0)
        self.style_box.blockSignals(True)
        self.style_box.setCurrentIndex(
            style if 0 <= style < self.style_box.count() else 0)
        self.style_box.blockSignals(False)
        self._refresh_icon_button()
        self.label_edit.setText(m["label"])
        self._preview_timer.start()
        if m["text"] is None:
            # Not expressible as text. Showing it as text and saving would silently
            # drop the chords and delays, so the field is locked instead.
            self.text_edit.setText("")
            self.text_edit.setEnabled(False)
            self.body_note.setText(
                f"{len(m['steps'])} steps including keys or delays — not plain text. "
                f"Nothing writes one yet, so it is shown and left alone rather than "
                f"flattened; the label and keycap style are still editable.")
        else:
            self.text_edit.setEnabled(True)
            self.text_edit.setText(m["text"])
            self.body_note.setText(f"{m['bytes']} bytes")

    # -- label preview ------------------------------------------------------

    def _on_label_changed(self, _text: str):
        self._preview_timer.start()

    def _on_style_changed(self, _i: int):
        self._refresh_icon_button()
        self._preview_timer.start()

    def _refresh_icon_button(self):
        icon_style = self.style_box.currentData() in (MacroStyle.ICON.value,
                                                      MacroStyle.ICON_ONLY.value)
        self.icon_btn.setEnabled(icon_style)
        self.icon_clear.setEnabled(icon_style and bool(self._icon))
        if not self._icon:
            self.icon_btn.setText("Choose icon…")
        else:
            drawable = mk.find_glyph(self._fonts, self._icon) is not None
            # Say so when the keyboard cannot draw it: the firmware falls back to the
            # index, so a silently-unchanged keycap would otherwise read as a bug.
            #
            # ⚠️ Only claim that when the lookup could see the RESIDENT fonts. Falling
            # back to the shipped packs leaves them out, so a resident-only glyph reads
            # as absent when the keyboard draws it perfectly well -- and a confident
            # wrong warning is worse than none.
            warn = " (no glyph)" if self._font_source == "headers" else " (unverified)"
            self.icon_btn.setText(f"U+{self._icon:04X}" + ("" if drawable else warn))

    def _on_pick_icon(self):
        from polyhost.gui.layout_dialog.macro_icon_dialog import MacroIconDialog

        dlg = MacroIconDialog(self._icon, self)
        if dlg.exec_() and dlg.codepoint() is not None:
            self._icon = dlg.codepoint()
            self._refresh_icon_button()
            self._preview_timer.start()

    def _on_clear_icon(self):
        self._icon = 0
        self._refresh_icon_button()
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
        # The meter measures the CAPTION band, which the label-only style does not use --
        # there the whole cell is the caption and the ladder decides what fits.
        self.width_meter.setEnabled(
            self.style_box.currentData() not in (MacroStyle.TEXT.value,
                                                 MacroStyle.ICON_ONLY.value))
        self.preview.setPixmap(self._render(r.text))

    # -- keycap composition -------------------------------------------------

    def _render(self, label: str) -> QPixmap:
        """Draw the keycap the way render_macro_key() composes it, for this style."""
        img = QImage(ml.PANEL_W, ml.PANEL_H, QImage.Format_RGB32)
        img.fill(QColor(8, 10, 14))
        lit = QColor(207, 231, 245).rgb()
        style = self.style_box.currentData()

        if style == MacroStyle.TEXT.value and label and self._ladder:
            plan = mk.plan_caption(label, self._ladder)
            if plan is not None:
                fonts, base, box, _name = plan
                self._plot(img, label, fonts, base, lit,
                           x0=(ml.PANEL_W - (box[1] - box[0] + 1)) // 2 - box[0],
                           baseline=(ml.PANEL_H - (box[3] - box[2] + 1)) // 2 - box[2])
                return self._scaled(img)
            # Nothing on the ladder fits: the firmware falls through to a captioned
            # style rather than drawing an empty keycap, so the preview does too.

        mark, mark_fonts, mark_base, mark_glyph = self._mark(style)
        # ICON_ONLY draws the icon alone in the whole cell -- the caption is kept in
        # storage but not drawn, so it takes the same branch an uncaptioned key does.
        # A missing glyph leaves mark_glyph None and falls back to the captioned index.
        if style == MacroStyle.ICON_ONLY.value and mark_glyph is not None:
            label = ""
        if not label:
            if mark and mark_fonts:
                box = mk.bbox(mark, mark_fonts, mark_base)
                if box:
                    self._plot(img, mark, mark_fonts, mark_base, lit,
                               x0=(ml.PANEL_W - (box[1] - box[0] + 1)) // 2 - box[0],
                               baseline=(ml.PANEL_H - (box[3] - box[2] + 1)) // 2 - box[2])
            return self._scaled(img)

        cap = mk.bbox(label, [self._font], 0)
        if cap is None:
            return self._scaled(img)
        cap_base = ml.PANEL_H - 1 - cap[3]
        free_rows = cap_base + cap[2]
        self._plot(img, label, [self._font], 0, lit,
                   x0=(ml.PANEL_W - (cap[1] - cap[0] + 1)) // 2 - cap[0],
                   baseline=cap_base)

        if mark and mark_fonts:
            drawn = self._draw_mark(img, lit, mark, mark_fonts, mark_base,
                                    free_rows, mark_glyph)
            if not drawn and mark_glyph is not None:
                # An icon that fits at no size falls back to the index, which always
                # does -- the same fallback a missing glyph takes, so an icon can
                # never leave the keycap without a mark.
                idx, idx_fonts, idx_base, _ = self._index_mark()
                if idx and idx_fonts:
                    self._draw_mark(img, lit, idx, idx_fonts, idx_base, free_rows, None)
        return self._scaled(img)

    def _draw_mark(self, img: QImage, lit: int, mark: str, fonts, base: int,
                   free_rows: int, glyph) -> bool:
        """Place the mark in the rows the caption left; report whether it landed.

        Mirrors draw_macro_mark() in poly_keymap.c, including the HALVING: a pack
        emoji renders at 40 px while a captioned key leaves about 29 rows, so drawing
        only at native size showed NOTHING for four picker icons out of five -- and
        because this preview mirrors the firmware, it was silent on both ends.
        """
        box = mk.bbox(mark, fonts, base)
        if box is None:
            return False
        h = box[3] - box[2] + 1
        if h < free_rows:
            self._plot(img, mark, fonts, base, lit,
                       x0=(ml.PANEL_W - (box[1] - box[0] + 1)) // 2 - box[0],
                       baseline=(free_rows - h) // 2 - box[2])
            return True
        if glyph is None:      # text marks (the index) are never rescaled
            return False
        hw, hh = (glyph["width"] + 1) // 2, (glyph["height"] + 1) // 2
        if hh >= free_rows:
            return False
        self._plot_half(img, fonts[0], glyph, lit,
                        x=(ml.PANEL_W - hw) // 2, y=(free_rows - hh) // 2)
        return True

    def _index_mark(self):
        """The fallback mark: "M3" in the mid face, which fits any caption."""
        if self._mid is None:
            return "", [], 0, None
        mid = self._macros[self._current]["id"] if self._macros else 0
        return f"M{mid}", [self._mid], 0, None

    def _mark(self, style):
        """What goes above the caption: a chosen glyph, or the macro's index.

        An icon the keyboard has no glyph for falls back to the index, exactly as the
        firmware does -- so a choice made against a richer font pack still names its
        macro here rather than drawing nothing. The glyph comes back too, because a
        tall one is drawn at half size (see _draw_mark).
        """
        if style in (MacroStyle.ICON.value, MacroStyle.ICON_ONLY.value) and self._icon:
            hit = mk.find_glyph(self._fonts, self._icon)
            if hit is not None:
                # Through the glyph's OWN font: kdisp_write_gfx_char baseline-aligns to
                # fonts[0], so drawing a tall pack glyph through the whole pool shifts
                # it down by the difference (the language-flag gap-at-top regression).
                return chr(self._icon), [hit[0]], 0, hit[1]
        return self._index_mark()

    def _plot(self, img: QImage, text: str, fonts, base: int, lit: int,
              x0: int, baseline: int):
        x = x0
        for ch in text:
            hit = mk.find_glyph(fonts, ord(ch) + base)
            if hit is None:
                continue
            f, g = hit
            bo, cb = g["bitmapOffset"], (g["height"] + 7) >> 3   # column-native
            for xx in range(g["width"]):
                col = bo + xx * cb
                for yy in range(g["height"]):
                    if f.bitmap[col + (yy >> 3)] & (1 << (yy & 7)):
                        vx, vy = x + g["xOffset"] + xx, baseline + g["yOffset"] + yy
                        if 0 <= vx < ml.PANEL_W and 0 <= vy < ml.PANEL_H:
                            img.setPixel(vx, vy, lit)
            x += g["xAdvance"]

    def _plot_half(self, img: QImage, font, g, lit: int, x: int, y: int):
        """2x2-OR downsample at a literal top-left -- kdisp_draw_glyph_half_at().

        OR rather than decimation because it keeps thin strokes a sampled downscale
        drops, and the halved extents round UP or an odd-width glyph loses its last
        column.
        """
        bo, w, h = g["bitmapOffset"], g["width"], g["height"]
        cb = (h + 7) >> 3                                   # column-native
        for dy in range((h + 1) // 2):
            for dx in range((w + 1) // 2):
                on = False
                for oy in range(2):
                    for ox in range(2):
                        sx, sy = dx * 2 + ox, dy * 2 + oy
                        if sx >= w or sy >= h:
                            continue
                        if font.bitmap[bo + sx * cb + (sy >> 3)] & (1 << (sy & 7)):
                            on = True
                            break
                    if on:
                        break
                if on and 0 <= x + dx < ml.PANEL_W and 0 <= y + dy < ml.PANEL_H:
                    img.setPixel(x + dx, y + dy, lit)

    @staticmethod
    def _scaled(img: QImage) -> QPixmap:
        return QPixmap.fromImage(
            img.scaled(ml.PANEL_W * PREVIEW_SCALE, ml.PANEL_H * PREVIEW_SCALE,
                       Qt.IgnoreAspectRatio, Qt.FastTransformation))

    # -- actions ------------------------------------------------------------

    def _on_save(self):
        if not self._macros:
            return
        m = self._macros[self._current]
        params = {"label": self.label_edit.text(),
                  "style": self.style_box.currentData(),
                  "icon": self._icon}
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
