"""Composer tab for building QMK "special" keycodes.

The plain keycode tabs in KeycodeBrowser can only pick flat keycodes parsed
from keycodes.h. This widget builds the parameterised quantum keycodes —
layer switches (MO/TO/TG/DF/TT/OSL), one-shot mod (OSM), mod-tap (MT),
layer-tap (LT) and modified keycodes (Ctrl+key …) — from a behaviour +
layer/modifier/inner-key selection, with a live preview, and emits the same
keycodeSelected signal the browser uses so the device-write path is unchanged.
"""
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QSpinBox, QCheckBox, QRadioButton, QButtonGroup,
    QPushButton, QLabel,
)

from polyhost.gui.layout_dialog.qmk_keycode_helper import (
    decompose_keycode, create_nice_name,
    encode_mods, encode_layer_switch, encode_one_shot_mod,
    encode_mod_tap, encode_layer_tap, encode_modded,
    decode_for_composer, MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI, MOD_RIGHT,
)

# Behaviour definitions: key -> (label, needs_layer, needs_mods, needs_inner_key)
BEHAVIORS = [
    ("MO", "MO — Momentary layer", True, False, False),
    ("TO", "TO — Switch to layer", True, False, False),
    ("TG", "TG — Toggle layer", True, False, False),
    ("DF", "DF — Set default layer", True, False, False),
    ("TT", "TT — Tap-toggle layer", True, False, False),
    ("OSL", "OSL — One-shot layer", True, False, False),
    ("OSM", "OSM — One-shot modifier", False, True, False),
    ("LT", "LT — Layer-tap (hold layer / tap key)", True, False, True),
    ("MT", "MT — Mod-tap (hold mod / tap key)", False, True, True),
    ("MOD", "Modified key (Ctrl/Shift/… + key)", False, True, True),
]


class KeycodeComposer(QWidget):
    keycodeSelected = pyqtSignal(str, str, int, int)  # nice_name, name, keycode, font_hint

    def __init__(self, basic_keycodes: dict[str, int], num_layers: int = 9):
        super().__init__()
        # Inner-key choices: basic keycodes only (0x00–0xFF) — that is all MT/LT
        # and modified keycodes can carry in their low byte.
        self._basic = sorted(
            ((name, kc) for name, kc in basic_keycodes.items() if 0x00 <= kc <= 0xFF),
            key=lambda nk: nk[1],
        )
        # code -> name for verified previews of composed keycodes.
        self._code_to_name = {kc: name for name, kc in self._basic}
        self._num_layers = max(1, num_layers)

        outer = QVBoxLayout(self)

        form = QFormLayout()
        self.behavior_combo = QComboBox()
        for key, label, *_ in BEHAVIORS:
            self.behavior_combo.addItem(label, key)
        form.addRow("Behavior:", self.behavior_combo)

        self.layer_spin = QSpinBox()
        self.layer_spin.setRange(0, self._num_layers - 1)
        form.addRow("Layer:", self.layer_spin)

        # Modifier selection: Ctrl/Shift/Alt/GUI + a left/right side toggle.
        mod_box = QGroupBox("Modifiers")
        mod_layout = QHBoxLayout(mod_box)
        self.cb_ctrl = QCheckBox("Ctrl")
        self.cb_shift = QCheckBox("Shift")
        self.cb_alt = QCheckBox("Alt")
        self.cb_gui = QCheckBox("GUI")
        for cb in (self.cb_ctrl, self.cb_shift, self.cb_alt, self.cb_gui):
            mod_layout.addWidget(cb)
        self.rb_left = QRadioButton("Left")
        self.rb_right = QRadioButton("Right")
        self.rb_left.setChecked(True)
        self.side_group = QButtonGroup(self)
        self.side_group.addButton(self.rb_left)
        self.side_group.addButton(self.rb_right)
        mod_layout.addSpacing(12)
        mod_layout.addWidget(self.rb_left)
        mod_layout.addWidget(self.rb_right)
        form.addRow(mod_box)

        self.inner_combo = QComboBox()
        for name, kc in self._basic:
            display = name[3:] if name.startswith("KC_") else name
            self.inner_combo.addItem(display, kc)
        self._select_default_inner()
        form.addRow("Inner key:", self.inner_combo)

        outer.addLayout(form)

        self.preview = QLabel()
        self.preview.setStyleSheet("font-weight: bold; padding: 4px;")
        outer.addWidget(self.preview)

        self.apply_btn = QPushButton("Apply to selected key")
        outer.addWidget(self.apply_btn)
        outer.addStretch(1)

        # Wiring
        self.behavior_combo.currentIndexChanged.connect(self._on_behavior_changed)
        self.layer_spin.valueChanged.connect(self._update_preview)
        self.inner_combo.currentIndexChanged.connect(self._update_preview)
        for cb in (self.cb_ctrl, self.cb_shift, self.cb_alt, self.cb_gui):
            cb.toggled.connect(self._update_preview)
        self.rb_left.toggled.connect(self._update_preview)
        self.apply_btn.clicked.connect(self._on_apply)

        self._on_behavior_changed()

    # -- helpers -----------------------------------------------------------
    def set_layer_count(self, num_layers: int):
        self._num_layers = max(1, num_layers)
        self.layer_spin.setRange(0, self._num_layers - 1)
        self._update_preview()

    def load_from_keycode(self, value: int) -> bool:
        """Populate the controls from an existing keycode.

        Returns True if the keycode is one of the composable behaviours (and the
        controls were updated), False otherwise (plain key / LM / unsupported).
        """
        decoded = decode_for_composer(value)
        if decoded is None:
            return False
        behavior, layer, mods, inner = decoded
        idx = self.behavior_combo.findData(behavior)
        if idx < 0:
            return False

        # Suppress per-widget preview churn while we batch-set the controls.
        widgets = (self.behavior_combo, self.layer_spin, self.inner_combo,
                   self.cb_ctrl, self.cb_shift, self.cb_alt, self.cb_gui,
                   self.rb_left, self.rb_right)
        for w in widgets:
            w.blockSignals(True)
        try:
            self.behavior_combo.setCurrentIndex(idx)
            self.layer_spin.setValue(min(layer, self.layer_spin.maximum()))
            self.cb_ctrl.setChecked(bool(mods & MOD_CTRL))
            self.cb_shift.setChecked(bool(mods & MOD_SHIFT))
            self.cb_alt.setChecked(bool(mods & MOD_ALT))
            self.cb_gui.setChecked(bool(mods & MOD_GUI))
            (self.rb_right if mods & MOD_RIGHT else self.rb_left).setChecked(True)
            if inner:
                inner_idx = self.inner_combo.findData(inner)
                if inner_idx >= 0:
                    self.inner_combo.setCurrentIndex(inner_idx)
        finally:
            for w in widgets:
                w.blockSignals(False)

        # Refresh enabled states + preview once, now that everything is set.
        self._on_behavior_changed()
        return True

    def _select_default_inner(self):
        """Default the inner-key combo to KC_A if present."""
        for i in range(self.inner_combo.count()):
            if self.inner_combo.itemData(i) == 0x04:  # KC_A
                self.inner_combo.setCurrentIndex(i)
                return

    def _current_behavior(self):
        key = self.behavior_combo.currentData()
        for entry in BEHAVIORS:
            if entry[0] == key:
                return entry
        return BEHAVIORS[0]

    def _current_mods(self) -> int:
        return encode_mods(
            ctrl=self.cb_ctrl.isChecked(), shift=self.cb_shift.isChecked(),
            alt=self.cb_alt.isChecked(), gui=self.cb_gui.isChecked(),
            right=self.rb_right.isChecked(),
        )

    def _current_inner_kc(self) -> int:
        data = self.inner_combo.currentData()
        return int(data) if data is not None else 0

    def _encode(self):
        """Return the composed 16-bit keycode, or None if the selection is invalid."""
        key, _label, needs_layer, needs_mods, needs_inner = self._current_behavior()
        mods = self._current_mods()
        layer = self.layer_spin.value()
        inner = self._current_inner_kc()

        # MT/OSM/modified keycodes are meaningless with no modifier selected.
        if needs_mods and mods == 0:
            return None

        if key in ("MO", "TO", "TG", "DF", "TT", "OSL"):
            return encode_layer_switch(key, layer)
        if key == "OSM":
            return encode_one_shot_mod(mods)
        if key == "LT":
            return encode_layer_tap(layer, inner)
        if key == "MT":
            return encode_mod_tap(mods, inner)
        if key == "MOD":
            return encode_modded(mods, inner)
        return None

    # -- slots -------------------------------------------------------------
    def _on_behavior_changed(self):
        _key, _label, needs_layer, needs_mods, needs_inner = self._current_behavior()
        self.layer_spin.setEnabled(needs_layer)
        self.inner_combo.setEnabled(needs_inner)
        for cb in (self.cb_ctrl, self.cb_shift, self.cb_alt, self.cb_gui):
            cb.setEnabled(needs_mods)
        self.rb_left.setEnabled(needs_mods)
        self.rb_right.setEnabled(needs_mods)
        self._update_preview()

    def _update_preview(self):
        keycode = self._encode()
        if keycode is None:
            self.preview.setText("Select at least one modifier")
            self.apply_btn.setEnabled(False)
            return
        # Decode back for a verified human-readable preview.
        name = decompose_keycode(keycode, self._code_to_name)
        self.preview.setText(f"{name}   =   0x{keycode:04X}")
        self.apply_btn.setEnabled(True)

    def _on_apply(self):
        keycode = self._encode()
        if keycode is None:
            return
        name = decompose_keycode(keycode, self._code_to_name)
        nice_name = create_nice_name(name)
        self.keycodeSelected.emit(nice_name, name, keycode, 8)
