"""The Macros tab of the keycode browser.

Authoring and placement live in the same view on purpose: you write the macro, then
click the key, and the browser is already open on it. It is a tab rather than a separate
window because the browser is already a QTabWidget whose "Layers && Mods" page BUILDS
keycodes rather than just listing them -- a macro page is the same shape.

Two widgets here do real work rather than decorate:

* the meter beside the label is in PIXELS, not characters, and the preview renders the
  label through the firmware's own font. The keycap truncates by measured width, so a
  character count would promise letters that will not be drawn -- and the preview is
  also the only place the ASCII-only limit explains itself, since an umlaut simply does
  not appear.
* the storage bar. The bodies share one buffer, so a long macro takes room from the
  others; without it the failure mode is a confusing refusal when you save the ninth
  macro because the third is enormous.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from polyhost.device.command_ids import MacroStyle
from polyhost.services import macro_label as ml
from polyhost.gui.layout_dialog.macro_keycap_render import MacroKeycapRenderer
from polyhost.services import macro_look as mk

# QK_MACRO_0. The firmware owns this range outright -- via.c is the only core dispatcher
# for it and VIA_ENABLE is unset -- so a macro key is an ordinary keycode assignment.
QK_MACRO = 0x7700

# 3, not 2: the icon controls sit under the preview now, and two buttons need a
# sensible width to share. It also makes the half-size icon legible at a glance,
# which is the thing the preview exists to show.
PREVIEW_SCALE = 3

# One line with the byte count -- both describe the body, and on its own the caveat
# wrapped to two rows in a column the browser already under-allocates.
BODY_CAVEAT = "stored unencrypted, readable by anything on the USB"


class MacroTab(QWidget):
    """Lists the keyboard's macros, edits one, and hands the keycode to the grid."""

    keycodeSelected = pyqtSignal(str, str, int, int)
    # A macro's look changed on the device. The keymap editor draws these keycaps
    # on its key tiles from its OWN copy of the list, so without this a caption edit
    # shows here and on the keyboard while the tile keeps the picture it drew when
    # the dialog opened.
    macrosChanged = pyqtSignal()

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
        # None means "the body is whatever the text field says". A list means the body
        # is steps and the text field is showing a read-only summary of them -- one of
        # the two is the truth at any moment, never both.
        self._steps: list | None = None

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
        # One renderer for the tab; the editor builds its own from the same fonts.
        self._keycap = MacroKeycapRenderer(self._fonts, self._font, self._mid, self._ladder)

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

        # EVERYTHING that composes the keycap sits in one column beside the preview,
        # and the label shares its line with the meter. Not cosmetic: the browser caps
        # itself at 400 px, so this page is handed ~351 px on every open -- always
        # short, never occasionally -- and the fixed-size preview cannot give the
        # deficit back. Stacked full-width, the meter row was drawn over the bottom of
        # the keycap, which is exactly where the label renders.
        #
        # The fields are named INLINE, at the ordinary widget size, rather than under
        # 10 px letter-spaced captions: a caption costs a row of its own AND was too
        # small to read at a glance, and "Keycap:" in front of the field it names says
        # the same thing in the space the field already occupies. All THREE rows carry
        # one -- the style box read as a stray control while its neighbours were named,
        # and it was the only thing in the column not starting on the fields' x.
        top_row = QHBoxLayout()
        left_col = QVBoxLayout()

        name_row = QHBoxLayout()
        name_row.addWidget(self._field_label("Keycap:"))
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
        style_row = QHBoxLayout()
        style_row.addWidget(self._field_label("Style:"))
        style_row.addWidget(self.style_box, 1)
        left_col.addLayout(style_row)

        # The body field sits here rather than under the whole top row: the preview is
        # three keycaps tall and the two rows above are one each, so the column had a
        # hole in it while the body -- the field most edits actually touch -- sat below
        # the fold, further from the fields it belongs with than from the buttons.
        types_row = QHBoxLayout()
        types_row.addWidget(self._field_label("Types:"))
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("tom@example.com")
        types_row.addWidget(self.text_edit, 1)
        # Chords, delays and held modifiers do not fit a single line of text, so they
        # get an editor of their own -- and recording needs a window that can take the
        # keyboard away from this field. See macro_steps_dialog.
        self.steps_btn = QPushButton("Steps…")
        self.steps_btn.setToolTip(
            "Build the macro out of key presses, chords and pauses — or record them")
        self.steps_btn.clicked.connect(self._on_edit_steps)
        types_row.addWidget(self.steps_btn)
        left_col.addLayout(types_row)

        left_col.addStretch(1)
        top_row.addLayout(left_col, 1)

        # The icon controls live UNDER the preview, with the picture they change: the
        # button reads back the chosen codepoint, so it is a readout as much as a
        # control and belongs beside what it draws. The preview is scaled up to give
        # the pair a sensible width to sit in.
        preview_col = QVBoxLayout()
        self.preview = QLabel()
        self.preview.setFixedSize(ml.PANEL_W * PREVIEW_SCALE, ml.PANEL_H * PREVIEW_SCALE)
        self.preview.setToolTip("How the keycap will look")
        preview_col.addWidget(self.preview)

        icon_row = QHBoxLayout()
        icon_row.setContentsMargins(0, 0, 0, 0)
        self.icon_btn = QPushButton("Choose icon…")
        self.icon_btn.clicked.connect(self._on_pick_icon)
        icon_row.addWidget(self.icon_btn, 1)
        self.icon_clear = QPushButton("Clear")
        self.icon_clear.clicked.connect(self._on_clear_icon)
        icon_row.addWidget(self.icon_clear)
        preview_col.addLayout(icon_row)
        preview_col.addStretch(1)
        top_row.addLayout(preview_col)
        right.addLayout(top_row)

        # The size and the caveat share ONE line: both describe the body, neither
        # needs a row of its own, and the caveat wrapped to two lines when it had one.
        # Not a scary modal, just the truth: people will store passwords here anyway.
        self.body_note = QLabel()
        self.body_note.setWordWrap(True)
        self.body_note.setStyleSheet("color: palette(mid);")
        right.addWidget(self.body_note)

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
    def _field_label(text: str) -> QLabel:
        """A field name, at the ordinary widget size.

        All three are given the SAME minimum width -- measured off the longest of
        them -- so the fields start on one x. Without it "Keycap:", "Style:" and
        "Types:" each measure differently and the boxes step across the column.
        """
        lbl = QLabel(text)
        lbl.setMinimumWidth(lbl.fontMetrics().horizontalAdvance("Keycap:") + 6)
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
            # Not expressible as text: showing it as text and saving would silently drop
            # the chords and delays. The field turns into a read-only summary and the
            # Steps… button is the way in.
            self._show_steps(m["steps"], m["bytes"])
        else:
            self._steps = None
            self.text_edit.setReadOnly(False)
            self.text_edit.setEnabled(True)
            self.text_edit.setText(m["text"])
            self.body_note.setText(f"{m['bytes']} bytes  ·  {BODY_CAVEAT}")

    def _show_steps(self, steps: list, size: int | None = None):
        """Put the tab into step mode: the field summarises, the dialog edits.

        Read-only rather than disabled, because a disabled field reads as "this macro
        cannot be edited" when the truth is "not here".
        """
        from polyhost.services import macro_body, macro_keys
        self._steps = list(steps)
        decoded = [macro_body.Step(**st) for st in self._steps]
        self.text_edit.setEnabled(True)
        self.text_edit.setReadOnly(True)
        self.text_edit.setText(macro_keys.describe(decoded))
        note = f"{len(self._steps)} step(s)"
        if size is not None:
            note = f"{size} bytes  ·  {note}"
        self.body_note.setText(f"{note} — press Steps… to edit  ·  {BODY_CAVEAT}")

    def _on_edit_steps(self):
        """Open the step editor on whatever the body currently is.

        Plain text opens as one Type row per character rather than as an empty list --
        a macro is usually *extended* into a chord, and starting from nothing would
        throw away what is already in the field.
        """
        from polyhost.services import macro_body
        from polyhost.gui.layout_dialog.macro_steps_dialog import MacroStepsDialog

        if self._steps is not None:
            steps = [macro_body.Step(**st) for st in self._steps]
        else:
            try:
                steps = macro_body.decode(macro_body.encode_text(self.text_edit.text()))
            except macro_body.MacroError as e:
                self._error("That text cannot become steps", str(e))
                return

        dlg = MacroStepsDialog(steps, parent=self)
        if not dlg.exec_():
            return
        result = dlg.result_steps
        # Back to plain text when it IS plain text, so an edit that removes the last
        # chord hands the ordinary field back rather than leaving the macro in a mode
        # it no longer needs.
        text = macro_body.to_text(result)
        if text is not None:
            self._steps = None
            self.text_edit.setReadOnly(False)
            self.text_edit.setText(text)
            self.body_note.setText(f"{len(result)} bytes  ·  {BODY_CAVEAT}")
        else:
            self._show_steps([{"kind": st.kind, "code": st.code, "ms": st.ms}
                              for st in result])
        self._preview_timer.start()

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
        """Thin adapter: read the widgets, hand the values to the shared renderer.

        The composition itself moved to `macro_keycap_render` unchanged, so the keymap
        editor can draw the same keycap on a key tile. Everything that varies per
        keycap is an argument now; the fonts live in the renderer.
        """
        mid = self._macros[self._current]["id"] if self._macros else 0
        img = self._keycap.render(label, self.style_box.currentData(),
                                  icon=self._icon, index=mid)
        return self._scaled(img)

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
        # The body goes only when it CHANGED. `macro_set` rewrites the whole shared
        # buffer to place one body, so a label-only edit that re-sent it would cost
        # every other macro a rewrite for nothing -- and the core's own docstring says
        # omitting the body is how a look-only edit avoids exactly that. The text path
        # sent it unconditionally before this, which quietly defeated it.
        if self._steps is not None:
            if self._steps != m["steps"]:
                params["steps"] = self._steps
        elif self.text_edit.text() != (m["text"] or ""):
            params["text"] = self.text_edit.text()
        ok, msg = self.core.macro_set(m["id"], **params)
        if not ok:
            self._error("Could not save the macro", msg)
            return
        self.reload()
        self.macrosChanged.emit()

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
