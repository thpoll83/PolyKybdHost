"""The step editor -- build a macro out of chords, delays and text, or record one.

Why a modal rather than another row on the Macros tab: **recording needs the keyboard
to itself.** While it is armed every keystroke belongs to the macro, so it cannot share
a window with a label field that also wants them. Everything else here follows from
that -- once there is a window, the step table may as well live in it too.

The table is the authority and the summary line is a view of it, never the other way
round: a summary that could be edited would need parsing, and a parser is option 3.

⚠️ Recording reads the character a key produced, not the physical key -- see
`polyhost/services/macro_keys.py` for what that costs and why. Each captured step names
the keycode it stored, so a wrong one is visible and editable rather than silent.
"""

from __future__ import annotations

from PyQt5.QtCore import QElapsedTimer, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from polyhost.services import macro_body as mb
from polyhost.services import macro_keys as mk

# The kinds a row can hold, in the order the combo offers them. `char` is deliberately
# absent: a character is added as a run of text, not one row at a time.
KINDS = [("tap", "Tap"), ("down", "Hold"), ("up", "Release"), ("delay", "Wait")]
KIND_LABEL = dict(KINDS)

# Below this the gap between two keystrokes is the user typing, not a pause they meant.
# Above it, recording timing keeps the rhythm; a macro that replays a 4 ms gap as a step
# is just noise in the list and bytes on the keyboard.
MIN_RECORDED_GAP_MS = 40

COL_KIND, COL_KEY, COL_MS = 0, 1, 2


class MacroStepsDialog(QDialog):
    """Edit one macro's body as a list of steps. `result_steps` holds the outcome."""

    def __init__(self, steps: list[mb.Step] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Macro steps")
        self.result_steps: list[mb.Step] = []
        self._recording = False
        self._clock = QElapsedTimer()
        # Ordinary focus, so the dialog itself receives key events while recording
        # rather than whichever child last had them.
        self.setFocusPolicy(Qt.StrongFocus)

        page = QVBoxLayout(self)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Action", "Key", "ms"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        head = self.table.horizontalHeader()
        # ⚠️ ResizeToContents measures the cell's ITEM, not a cell WIDGET, so the two
        # combo columns come out sized for an empty cell and clip ("Rele"). Measure the
        # widest label ourselves and leave the section fixed.
        fm = self.table.fontMetrics()
        head.setSectionResizeMode(COL_KIND, QHeaderView.Fixed)
        self.table.setColumnWidth(
            COL_KIND, max(fm.horizontalAdvance(l) for _, l in KINDS + [("", "Type")]) + 42)
        head.setSectionResizeMode(COL_KEY, QHeaderView.Stretch)
        head.setSectionResizeMode(COL_MS, QHeaderView.Fixed)
        self.table.setColumnWidth(COL_MS, fm.horizontalAdvance("65535 ms") + 34)
        self.table.itemSelectionChanged.connect(self._refresh_buttons)
        page.addWidget(self.table, 1)

        row = QHBoxLayout()
        self.add_btn = QPushButton("Add step")
        self.add_btn.clicked.connect(self._on_add)
        row.addWidget(self.add_btn)
        self.text_btn = QPushButton("Add text…")
        self.text_btn.setToolTip("Append a run of characters the macro should type")
        self.text_btn.clicked.connect(self._on_add_text)
        row.addWidget(self.text_btn)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._on_remove)
        row.addWidget(self.remove_btn)
        self.up_btn = QPushButton("↑")
        self.up_btn.clicked.connect(lambda: self._move(-1))
        row.addWidget(self.up_btn)
        self.down_btn = QPushButton("↓")
        self.down_btn.clicked.connect(lambda: self._move(1))
        row.addWidget(self.down_btn)
        row.addStretch(1)

        # The recorder. A toggle rather than a modal-within-a-modal: the table stays
        # visible while it fills, which is what makes it obvious what was captured.
        self.record_btn = QPushButton("Record")
        self.record_btn.setCheckable(True)
        self.record_btn.setToolTip(
            "Press the keys you want, then click Stop. Esc stops recording.")
        self.record_btn.toggled.connect(self._on_record_toggled)
        row.addWidget(self.record_btn)
        self.timing_box = QComboBox()
        self.timing_box.addItem("no timing", False)
        self.timing_box.addItem("with timing", True)
        self.timing_box.setToolTip(
            "Record the real pauses between keystrokes as Wait steps.\n"
            "Off by default: most macros want to run as fast as the keyboard can.")
        row.addWidget(self.timing_box)
        page.addLayout(row)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color: palette(mid);")
        page.addWidget(self.summary)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        page.addWidget(buttons)

        for step in (steps or []):
            self._append_row(step)
        self._refresh()
        self.resize(560, 420)

    # -- the table is the model ---------------------------------------------

    def steps(self) -> list[mb.Step]:
        """Read the table back as steps. The widgets ARE the model.

        A parallel list would be a second copy to keep in step with the table, which is
        the shape this repo keeps getting caught by -- and the table already holds
        everything a step is.
        """
        out: list[mb.Step] = []
        for r in range(self.table.rowCount()):
            kind = self.table.cellWidget(r, COL_KIND).currentData()
            if kind == "delay":
                out.append(mb.Step("delay", ms=int(self.table.cellWidget(r, COL_MS).value())))
            elif kind == "char":
                item = self.table.item(r, COL_KEY)
                out.append(mb.Step("char", code=int(item.data(Qt.UserRole))))
            else:
                code = mk.value_for(self.table.item(r, COL_KEY).text())
                out.append(mb.Step(kind, code=code or 0))
        return out

    def _append_row(self, step: mb.Step, at: int | None = None) -> int:
        r = self.table.rowCount() if at is None else at
        self.table.insertRow(r)

        kind_box = QComboBox()
        for value, label in KINDS:
            kind_box.addItem(label, value)
        if step.kind == "char":
            # A character has no Action of its own -- it is text, shown read-only so it
            # cannot be turned into a keycode row that means something else.
            kind_box.addItem("Type", "char")
            kind_box.setCurrentIndex(kind_box.count() - 1)
            kind_box.setEnabled(False)
        else:
            kind_box.setCurrentIndex(max(0, [k for k, _ in KINDS].index(step.kind)
                                         if step.kind in KIND_LABEL else 0))
        kind_box.currentIndexChanged.connect(lambda _i, box=kind_box: self._on_kind_changed(box))
        self.table.setCellWidget(r, COL_KIND, kind_box)

        if step.kind == "char":
            item = QTableWidgetItem(repr(chr(step.code)))
            item.setData(Qt.UserRole, step.code)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        else:
            item = QTableWidgetItem(mk.name_for(step.code) if step.kind != "delay" else "")
        self.table.setItem(r, COL_KEY, item)

        self._sync_row(r, ms=int(step.ms))
        return r

    def _sync_row(self, r: int, ms: int = 0):
        """Give the row only the editor its kind uses.

        A Wait with a Key box and a Tap with a ms box both invite an entry that is
        silently discarded on save, which is the shape of edit that gets reported as
        "it did not keep what I typed".

        ⚠️ The ms box is ADDED and REMOVED, not shown and hidden: `setVisible(False)`
        on a cell widget does not stop the table drawing it, so hiding left a live
        spin box on every Tap row.
        """
        kind = self.table.cellWidget(r, COL_KIND).currentData()
        spin = self.table.cellWidget(r, COL_MS)
        if kind == "delay" and spin is None:
            spin = QSpinBox()
            spin.setRange(0, 0xFFFF)
            spin.setSuffix(" ms")
            spin.setValue(ms)
            spin.valueChanged.connect(self._refresh)
            self.table.setCellWidget(r, COL_MS, spin)
        elif kind != "delay" and spin is not None:
            self.table.removeCellWidget(r, COL_MS)

        item = self.table.item(r, COL_KEY)
        if kind == "delay":
            item.setText("")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        elif kind != "char":
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            if not item.text():
                item.setText("KC_A")

    def _on_kind_changed(self, box):
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, COL_KIND) is box:
                self._sync_row(r)
                break
        self._refresh()

    # -- editing ------------------------------------------------------------

    def _selected(self) -> int:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return rows[0].row() if rows else -1

    def _on_add(self):
        at = self._selected()
        r = self._append_row(mb.Step("tap", code=mk.value_for("KC_A") or 0),
                             at=None if at < 0 else at + 1)
        self.table.selectRow(r)
        self._refresh()

    def _on_add_text(self):
        text, ok = QInputDialog.getText(self, "Add text", "Characters to type:")
        if not ok or not text:
            return
        try:
            mb.encode_text(text)          # refuse here, not silently at save
        except mb.MacroError as e:
            self.summary.setText(str(e))
            return
        at = self._selected()
        for i, ch in enumerate(text):
            self._append_row(mb.Step("char", code=ord(ch)),
                             at=None if at < 0 else at + 1 + i)
        self._refresh()

    def _on_remove(self):
        r = self._selected()
        if r >= 0:
            self.table.removeRow(r)
            self._refresh()

    def _move(self, delta: int):
        r = self._selected()
        t = r + delta
        if r < 0 or not 0 <= t < self.table.rowCount():
            return
        steps = self.steps()
        steps[r], steps[t] = steps[t], steps[r]
        self._reload(steps)
        self.table.selectRow(t)

    def _reload(self, steps: list[mb.Step]):
        self.table.setRowCount(0)
        for step in steps:
            self._append_row(step)
        self._refresh()

    def _refresh(self, *_):
        self.summary.setText(mk.describe(self.steps()) or "No steps yet.")
        self._refresh_buttons()

    def _refresh_buttons(self):
        has = self._selected() >= 0
        for b in (self.remove_btn, self.up_btn, self.down_btn):
            b.setEnabled(has and not self._recording)
        for b in (self.add_btn, self.text_btn):
            b.setEnabled(not self._recording)
        self.timing_box.setEnabled(not self._recording)

    # -- recording ----------------------------------------------------------

    def _on_record_toggled(self, on: bool):
        self._recording = on
        self.record_btn.setText("Stop" if on else "Record")
        if on:
            self._clock.restart()
            # The grab is what makes this work at all: without it the keystrokes go to
            # whichever widget has focus and the table fills with nothing.
            self.grabKeyboard()
            self.summary.setText("Recording — press keys, then click Stop (or Esc).")
        else:
            self.releaseKeyboard()
            self._refresh()
        self._refresh_buttons()

    def keyPressEvent(self, event):
        if not self._recording:
            # Enter must not accept the dialog from inside the table -- it is how you
            # commit a cell edit.
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                return
            return super().keyPressEvent(event)
        if event.key() == Qt.Key_Escape:
            self.record_btn.setChecked(False)
            return
        self._capture(event, "down")

    def keyReleaseEvent(self, event):
        if not self._recording:
            return super().keyReleaseEvent(event)
        self._capture(event, "up")

    def _capture(self, event, kind: str):
        # Auto-repeat is the OS reporting one held key over and over. Recording it would
        # fill the list with hundreds of rows for a key the user simply held down.
        if event.isAutoRepeat():
            return
        code = mk.qt_key_to_keycode(int(event.key()), event.text() or "")
        if code is None:
            self.summary.setText(
                f"No basic keycode for that key — skipped. "
                f"(Recorded {self.table.rowCount()} step(s) so far.)")
            return
        gap = int(self._clock.restart())
        if self.timing_box.currentData() and gap >= MIN_RECORDED_GAP_MS \
                and self.table.rowCount() > 0:
            self._append_row(mb.Step("delay", ms=min(gap, 0xFFFF)))
        self._append_row(mb.Step(kind, code=code))
        self.table.scrollToBottom()
        self.summary.setText(
            f"Recording — {self.table.rowCount()} step(s). Stop (or Esc) when done.")

    # -- finishing ----------------------------------------------------------

    def _on_accept(self):
        if self._recording:
            self.record_btn.setChecked(False)
        steps = self.steps()
        try:
            mb.encode_steps(steps)        # the same check the save path will make
        except mb.MacroError as e:
            self.summary.setText(str(e))
            return
        self.result_steps = steps
        self.accept()

    def closeEvent(self, event):
        # A grabbed keyboard outlives the widget if it is not released, and the app then
        # appears to stop responding to the keyboard entirely.
        if self._recording:
            self.releaseKeyboard()
            self._recording = False
        super().closeEvent(event)


def main():  # pragma: no cover - developer launcher
    import sys
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.theme import apply_dark_palette
    app = QApplication(sys.argv)
    apply_dark_palette(app)
    dlg = MacroStepsDialog([mb.Step("down", code=0xE0), mb.Step("tap", code=0x06),
                            mb.Step("up", code=0xE0)])
    if dlg.exec_():
        print(mk.describe(dlg.result_steps))


if __name__ == "__main__":  # pragma: no cover
    main()
