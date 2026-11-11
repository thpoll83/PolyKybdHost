"""The Combos and Tap Dance tabs of the keycode browser (cmd 48, firmware protocol 33).

Both tabs edit one slot at a time and write it with `core.combos_set()`, which sends
the record and stores the whole set in the keyboard's flash on both halves. `core` is
a PolyCore in-process and a RemoteCore in client mode, so everything goes through the
core and nothing here touches the device.

A combo needs no key of its own: it acts on the keys it lists. A tap dance acts only
on a key that carries its keycode TD(n), so the Tap Dance tab has "Use on selected
key", like the Macros tab. Slots are numbered from 1, as the keycap legend
("Tap dance 1" is TD(0)).
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCompleter, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from polyhost.device.command_ids import Combos
from polyhost.gui import message_box
from polyhost.gui.ui_kit import px, set_button_icon
from polyhost.i18n import _, _f
from polyhost.services.keycode_text import keycode_tables, keycode_text, parse_keycode


def short_text(value: int) -> str:
    """A keycode for the slot list: `J`, `Esc`, `S(9)`, `MO(1)`."""
    text = keycode_text(value, empty="")
    return text.replace("KC_", "")


class KeycodeField(QLineEdit):
    """A line edit that reads a keycode the way polyctl does, with name completion."""

    _completer_model = None

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        if KeycodeField._completer_model is None:
            by_name, _unused = keycode_tables()
            KeycodeField._completer_model = sorted(by_name)
        completer = QCompleter(KeycodeField._completer_model, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.setCompleter(completer)

    def set_keycode(self, value: int):
        self.setText(keycode_text(value, empty=""))

    def keycode(self) -> int:
        """0 for an empty field; ValueError for text that names no keycode."""
        if not self.text().strip():
            return 0
        return parse_keycode(self.text())


class _SlotTab(QWidget):
    """A slot list on the left, the editor for the selected slot on the right."""

    keycodeSelected = pyqtSignal(str, str, int, int)

    def __init__(self, core, slots: int, parent=None):
        super().__init__(parent)
        self.core = core
        self._records: list[dict] = []
        self._slots = slots

        outer = QHBoxLayout(self)
        self.list = QListWidget()
        self.list.setMaximumWidth(px(230))
        self.list.currentRowChanged.connect(self._on_select)
        outer.addWidget(self.list)

        right = QVBoxLayout()
        outer.addLayout(right, 1)
        self.form = QFormLayout()
        right.addLayout(self.form)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color: palette(mid);")
        right.addWidget(self.note)
        right.addStretch(1)

        self.buttons = QHBoxLayout()
        self.save_btn = QPushButton(_("Save"))
        set_button_icon(self.save_btn, "save")
        self.save_btn.clicked.connect(self._on_save)
        self.buttons.addWidget(self.save_btn)
        self.clear_btn = QPushButton(_("Clear"))
        set_button_icon(self.clear_btn, "close")
        self.clear_btn.clicked.connect(self._on_clear)
        self.buttons.addWidget(self.clear_btn)
        right.addLayout(self.buttons)
        self.buttons.addStretch(1)

    # -- subclass hooks -----------------------------------------------------

    def _records_from(self, data: dict) -> list[dict]:
        raise NotImplementedError

    def _row_text(self, rec: dict) -> str:
        raise NotImplementedError

    def _show(self, rec: dict):
        raise NotImplementedError

    def _edited(self, slot: int) -> dict:
        """The record the fields describe. Raises ValueError with a reason."""
        raise NotImplementedError

    def _empty(self, slot: int) -> dict:
        raise NotImplementedError

    def _set_args(self, rec: dict) -> dict:
        raise NotImplementedError

    def _default_note(self) -> str:
        raise NotImplementedError

    # -- loading ------------------------------------------------------------

    def reload(self):
        """Read every slot from the keyboard. Called when the tab is shown."""
        ok, data = self.core.combos_get()
        if not ok or not data.get("available"):
            self.list.clear()
            self._records = []
            self._set_editable(False)
            self.note.setText(str(data) if not ok else _(
                "This firmware build has no runtime combos or tap dance "
                "(the DOOM developer build)."))
            return
        self._set_editable(True)
        self._records = self._records_from(data)
        self.note.setText(self._default_note())
        row = max(self.list.currentRow(), 0)
        self.list.blockSignals(True)
        self.list.clear()
        for rec in self._records:
            self.list.addItem(self._row_text(rec))
        self.list.blockSignals(False)
        if self._records:
            self.list.setCurrentRow(min(row, len(self._records) - 1))
            self._on_select(self.list.currentRow())

    def _set_editable(self, on: bool):
        for i in range(self.form.count()):
            w = self.form.itemAt(i).widget()
            if w is not None:
                w.setEnabled(on)
        for i in range(self.buttons.count()):
            w = self.buttons.itemAt(i).widget()
            if w is not None:
                w.setEnabled(on)

    def _on_select(self, row: int):
        if 0 <= row < len(self._records):
            self._show(self._records[row])

    # -- writing ------------------------------------------------------------

    def _write(self, rec: dict) -> bool:
        ok, msg = self.core.combos_set(**self._set_args(rec))
        if not ok:
            message_box.warning(self, _("Not saved"), str(msg))
            return False
        self._records[rec["slot"]] = rec
        self.list.item(rec["slot"]).setText(self._row_text(rec))
        if isinstance(msg, dict) and not msg.get("other_half", True):
            self.note.setText(_("Saved on this half only: the other half did not answer. "
                                "Save again once both halves are connected."))
        else:
            self.note.setText(self._default_note())
        return True

    def _on_save(self):
        row = self.list.currentRow()
        if row < 0:
            return
        try:
            rec = self._edited(row)
        except ValueError as e:
            message_box.warning(self, _("Not saved"), str(e))
            return
        self._write(rec)

    def _on_clear(self):
        row = self.list.currentRow()
        if row < 0:
            return
        if self._write(self._empty(row)):
            self._show(self._records[row])


class ComboTab(_SlotTab):
    """Two to four keys pressed together send another keycode."""

    def __init__(self, core, parent=None):
        super().__init__(core, Combos.COMBO_SLOTS, parent)
        self._term_ms = 0
        self.key_fields = []
        for i in range(Combos.MAX_KEYS):
            field = KeycodeField(_("optional") if i >= 2 else "")
            self.key_fields.append(field)
            self.form.addRow(_f("Key {n}", n=i + 1), field)
        self.result_field = KeycodeField()
        self.form.addRow(_("Sends"), self.result_field)

    def _default_note(self) -> str:
        if self._term_ms:
            return _f("Press the keys within {ms} ms of each other. A key is written as "
                      "on the keymap: KC_J, KC_ESC, S(KC_9), MO(1).", ms=self._term_ms)
        return _("Press the keys at the same time. A key is written as on the keymap: "
                 "KC_J, KC_ESC, S(KC_9), MO(1).")

    def _records_from(self, data: dict) -> list[dict]:
        self._term_ms = int(data.get("combo_term_ms", 0) or 0)
        return [dict(c) for c in data["combos"]]

    def _row_text(self, rec: dict) -> str:
        n = rec["slot"] + 1
        if not rec["keys"]:
            return _f("{n}: (empty)", n=n)
        keys = " + ".join(short_text(k) for k in rec["keys"])
        return f"{n}: {keys} → {short_text(rec['result'])}"

    def _show(self, rec: dict):
        keys = list(rec["keys"]) + [0] * Combos.MAX_KEYS
        for field, kc in zip(self.key_fields, keys):
            field.set_keycode(kc)
        self.result_field.set_keycode(rec["result"])

    def _edited(self, slot: int) -> dict:
        keys = []
        for i, field in enumerate(self.key_fields):
            try:
                kc = field.keycode()
            except ValueError:
                raise ValueError(_f("Key {n}: {text} is not a keycode.",
                                    n=i + 1, text=field.text().strip())) from None
            if kc:
                keys.append(kc)
        try:
            result = self.result_field.keycode()
        except ValueError:
            raise ValueError(_f("Sends: {text} is not a keycode.",
                                text=self.result_field.text().strip())) from None
        if len(keys) < 2 or not result:
            raise ValueError(_("A combo needs at least two keys and a keycode to send."))
        if len(set(keys)) != len(keys):
            raise ValueError(_("A combo cannot list the same key twice."))
        return {"slot": slot, "keys": keys, "result": result}

    def _empty(self, slot: int) -> dict:
        return {"slot": slot, "keys": [], "result": 0}

    def _set_args(self, rec: dict) -> dict:
        return {"combos": [rec]}


# The term spin box shows this value as "Tapping term" and stores it as 0.
_TERM_DEFAULT = Combos.TERM_MIN_MS - Combos.TERM_STEP_MS


class TapDanceTab(_SlotTab):
    """One key that sends different keycodes for a tap, a hold and a double tap."""

    _ACTIONS = ("on_tap", "on_hold", "on_double_tap", "on_tap_hold")

    def __init__(self, core, parent=None):
        super().__init__(core, Combos.TAP_DANCE_SLOTS, parent)
        labels = (_("Tap"), _("Hold"), _("Double tap"), _("Tap, then hold"))
        self.action_fields = {}
        for key, label in zip(self._ACTIONS, labels):
            field = KeycodeField(_("same as Tap") if key != "on_tap" else "")
            self.action_fields[key] = field
            self.form.addRow(label, field)
        self.term = QSpinBox()
        self.term.setRange(_TERM_DEFAULT, Combos.TERM_MAX_MS)
        self.term.setSingleStep(Combos.TERM_STEP_MS)
        self.term.setSuffix(_(" ms"))
        self.term.setSpecialValueText(_("Tapping term"))
        self.form.addRow(_("Decide after"), self.term)

        self.assign_btn = QPushButton(_("Use on selected key"))
        set_button_icon(self.assign_btn, "accept")
        self.assign_btn.clicked.connect(self._on_assign)
        self.buttons.insertWidget(2, self.assign_btn)

    def _default_note(self) -> str:
        return _("Place the tap dance on a key with \"Use on selected key\". An action "
                 "can be a key, a key with modifiers such as S(KC_9), or MO, TO or TG.")

    def _records_from(self, data: dict) -> list[dict]:
        return [dict(t) for t in data["tap_dances"]]

    def _row_text(self, rec: dict) -> str:
        n = rec["slot"] + 1
        if not any(rec[k] for k in self._ACTIONS):
            return _f("{n}: (empty)", n=n)
        parts = [short_text(rec["on_tap"])]
        if rec["on_hold"]:
            parts.append(_f("hold {key}", key=short_text(rec["on_hold"])))
        if rec["on_double_tap"]:
            parts.append(_f("2× {key}", key=short_text(rec["on_double_tap"])))
        return f"{n}: " + ", ".join(p for p in parts if p)

    def _show(self, rec: dict):
        for key, field in self.action_fields.items():
            field.set_keycode(rec[key])
        self.term.setValue(rec["term_ms"] or _TERM_DEFAULT)

    def _edited(self, slot: int) -> dict:
        rec = {"slot": slot}
        labels = {"on_tap": _("Tap"), "on_hold": _("Hold"),
                  "on_double_tap": _("Double tap"), "on_tap_hold": _("Tap, then hold")}
        for key, field in self.action_fields.items():
            try:
                kc = field.keycode()
            except ValueError:
                raise ValueError(_f("{action}: {text} is not a keycode.", action=labels[key],
                                    text=field.text().strip())) from None
            if not Combos.td_keycode_supported(kc):
                raise ValueError(_f("{action}: a tap dance can send a key, a key with "
                                    "modifiers, MO, TO or TG, not {text}.",
                                    action=labels[key], text=field.text().strip()))
            rec[key] = kc
        if not rec["on_tap"]:
            raise ValueError(_("A tap dance needs at least the Tap action."))
        term = self.term.value()
        rec["term_ms"] = 0 if term == _TERM_DEFAULT else term
        if not Combos.td_term_valid(rec["term_ms"]):
            raise ValueError(_f("The time must be {lo} to {hi} ms in steps of {step} ms.",
                                lo=Combos.TERM_MIN_MS, hi=Combos.TERM_MAX_MS,
                                step=Combos.TERM_STEP_MS))
        return rec

    def _empty(self, slot: int) -> dict:
        return {"slot": slot, "on_tap": 0, "on_hold": 0, "on_double_tap": 0,
                "on_tap_hold": 0, "term_ms": 0}

    def _set_args(self, rec: dict) -> dict:
        return {"tap_dances": [rec]}

    def _on_assign(self):
        """Hand TD(n) to the grid, as a keycode button does."""
        row = self.list.currentRow()
        if row < 0:
            return
        self.keycodeSelected.emit(_f("Tap dance {n}", n=row + 1), f"TD({row})",
                                  Combos.TD_KEYCODE_BASE + row, 0)
