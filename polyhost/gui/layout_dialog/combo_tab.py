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
from polyhost.device.poly_kybd import COMBOS_MIN_PROTOCOL
from polyhost.gui import message_box
from polyhost.gui.menu_fetch import MenuFetcher, ok_value
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


class _Unavailable:
    """What _read() returns when the status snapshot already says no."""

    def __init__(self, status: dict):
        self.status = status


class _SlotTab(QWidget):
    """A slot list on the left, the editor for the selected slot on the right."""

    keycodeSelected = pyqtSignal(str, str, int, int)

    def __init__(self, core, slots: int, parent=None):
        super().__init__(parent)
        self.core = core
        self._records: list[dict] = []
        self._writing = False
        self._reload_after_write = False
        self._slots = slots
        self._fetcher = MenuFetcher(self)

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
    #
    # Both the read and the write run off the GUI thread through MenuFetcher: a read
    # is up to 33 device round trips, and in client mode each is an RPC with no
    # timeout, so a stalled daemon or keyboard would otherwise freeze the editor.
    # The editor stays disabled while a call is in flight.

    def reload(self):
        """Read every slot from the keyboard. Called when the tab is shown. During a
        save the read waits for it: a read started before the write ends could show
        the old record after the saved one."""
        if self._writing:
            self._reload_after_write = True
            return
        if self._fetcher.fetch("combos", self._read, self._on_loaded):
            self._set_editable(False)
            self.note.setText(_("Reading the keyboard…"))

    def _read(self):
        """Off the GUI thread. The status snapshot is no device I/O; it answers the
        cases that have a translated explanation before any round trip."""
        status = self.core.get_status() or {}
        if self._status_says_no(status):
            return _Unavailable(status)
        result = self.core.combos_get()
        if not ok_value(result)[0]:
            # The snapshot can be older than the refusal (a keyboard that just
            # reconnected): ask again, so a known cause still gets its own text.
            status = self.core.get_status() or {}
            if self._status_says_no(status):
                return _Unavailable(status)
        return result

    @staticmethod
    def _status_says_no(status: dict) -> bool:
        return (not status.get("connected", True) or bool(status.get("safe_mode"))
                or not (status.get("capabilities") or {}).get("combos", True))

    def _unavailable_text(self, status: dict) -> str:
        if not status.get("connected", True):
            return _("The keyboard is not connected.")
        if status.get("safe_mode"):
            return _("The keyboard runs in restricted mode (its firmware is newer than "
                     "this app), so combos and tap dance are off.")
        return _f("Combos and tap dance need keyboard firmware with protocol {n} or "
                  "newer. Update the firmware to use them.", n=COMBOS_MIN_PROTOCOL)

    def _on_loaded(self, result):
        if isinstance(result, _Unavailable):
            ok, data, text = False, None, self._unavailable_text(result.status)
        else:
            ok, data = ok_value(result)
            if not ok:
                text = _f("Could not read the keyboard: {reason}", reason=data)
            elif not isinstance(data, dict) or not data.get("available"):
                ok, text = False, _("This firmware build has no runtime combos or tap "
                                    "dance (the DOOM developer build).")
        if not ok:
            self.list.clear()
            self._records = []
            self._set_editable(False)
            self.note.setText(text)
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

    def _write(self, rec: dict):
        args = self._set_args(rec)
        self._set_editable(False)
        self._writing = True
        self._fetcher.call(lambda: self.core.combos_set(**args),
                           lambda result, rec=rec: self._on_written(rec, result))

    def _on_written(self, rec: dict, result):
        self._writing = False
        self._apply_written(rec, result)
        if self._reload_after_write:
            self._reload_after_write = False
            self.reload()

    def _apply_written(self, rec: dict, result):
        self._set_editable(True)
        ok, msg = ok_value(result)
        if not ok:
            message_box.warning(self, _("Not saved"), str(msg))
            return
        self._records[rec["slot"]] = rec
        self.list.item(rec["slot"]).setText(self._row_text(rec))
        if self.list.currentRow() == rec["slot"]:
            self._show(rec)
        if isinstance(msg, dict) and not msg.get("other_half", True):
            self.note.setText(_("Saved on this half only: the other half did not answer. "
                                "Save again once both halves are connected."))
        else:
            self.note.setText(self._default_note())

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
        self._write(self._empty(row))


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
        # The firmware's default for each empty action (base/combo_store.h).
        placeholders = {"on_tap": "", "on_hold": _("same as Tap"),
                        "on_double_tap": _("Tap twice"),
                        "on_tap_hold": _("Tap, then hold Tap")}
        for key, label in zip(self._ACTIONS, labels):
            field = KeycodeField(placeholders[key])
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
        if rec["on_tap_hold"]:
            parts.append(_f("tap, then hold {key}", key=short_text(rec["on_tap_hold"])))
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
        if not any(rec[k] for k in self._ACTIONS):
            raise ValueError(_("A tap dance needs at least one action."))
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
