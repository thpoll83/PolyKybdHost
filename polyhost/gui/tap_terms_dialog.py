"""Tray > "Tap-Hold Timing…": the tapping term and the Flow Tap term (cmd 44, v29+),
and Auto Shift (v30+).

The values are stored on the keyboard, not in settings.yaml, so the dialog reads
them from the device when it opens and writes them back on OK. It goes through
``core.get_tap_terms`` / ``core.set_tap_terms``, which are RPC calls in client mode.
Ranges: ``TapTerms`` in ``device/command_ids.py``.
"""

from PyQt5.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
                             QSpinBox, QVBoxLayout)

from polyhost.device.command_ids import TapTerms
from polyhost.gui.ui_kit import WrapLabel, style_button_box
from polyhost.i18n import _, N_

_INTRO = N_(
    "A key with a tap and a hold action types its tap action when you release it "
    "before the tapping term, and acts as its hold action when you hold it longer.<br><br>"
    "A tap-hold key pressed within the Flow Tap term after the previous key "
    "always types its tap action, so fast typing does not trigger a modifier. "
    "0 turns Flow Tap off.<br><br>"
    "The keyboard stores both values.")

_AUTO_SHIFT_INTRO = N_(
    "With Auto Shift on, holding a letter, digit or symbol key longer than the "
    "Auto Shift timeout types its shifted character.")


class TapTermsDialog(QDialog):
    def __init__(self, terms, parent=None):
        """``terms`` is the dict from ``core.get_tap_terms()``."""
        super().__init__(parent)
        self.setWindowTitle(_("Tap-Hold Timing"))

        intro = WrapLabel(_(_INTRO))

        self.tapping = QSpinBox()
        self.tapping.setRange(TapTerms.TAPPING_MIN_MS, TapTerms.TAPPING_MAX_MS)
        self.tapping.setSingleStep(TapTerms.STEP_MS)
        # TRANSLATORS: unit after a number of milliseconds in a spin box.
        self.tapping.setSuffix(_(" ms"))
        self.tapping.setValue(int(terms.get("tapping_term", TapTerms.DEFAULT_TAPPING_MS)))

        self.flow_tap = QSpinBox()
        self.flow_tap.setRange(TapTerms.FLOW_TAP_MIN_MS, TapTerms.FLOW_TAP_MAX_MS)
        self.flow_tap.setSingleStep(TapTerms.STEP_MS)
        self.flow_tap.setSuffix(_(" ms"))
        # TRANSLATORS: shown in the Flow Tap spin box when its value is 0.
        self.flow_tap.setSpecialValueText(_("Off"))
        self.flow_tap.setValue(int(terms.get("flow_tap_term", TapTerms.DEFAULT_FLOW_TAP_MS)))
        if not terms.get("flow_tap_available", True):
            self.flow_tap.setEnabled(False)
            self.flow_tap.setToolTip(_("This keyboard's firmware has no Flow Tap."))

        self.auto_shift_available = bool(terms.get("auto_shift_available", False))
        # TRANSLATORS: check box that turns the keyboard's Auto Shift on.
        self.auto_shift = QCheckBox(_("Auto Shift"))
        self.auto_shift.setChecked(bool(terms.get("auto_shift", False)))
        self.auto_shift_ms = QSpinBox()
        self.auto_shift_ms.setRange(TapTerms.AUTO_SHIFT_MIN_MS, TapTerms.AUTO_SHIFT_MAX_MS)
        self.auto_shift_ms.setSingleStep(TapTerms.STEP_MS)
        self.auto_shift_ms.setSuffix(_(" ms"))
        self.auto_shift_ms.setValue(int(terms.get("auto_shift_ms", TapTerms.DEFAULT_AUTO_SHIFT_MS)))
        if not self.auto_shift_available:
            for w in (self.auto_shift, self.auto_shift_ms):
                w.setEnabled(False)
                w.setToolTip(_("This keyboard's firmware has no Auto Shift. Update the firmware."))
        else:
            self.auto_shift_ms.setEnabled(self.auto_shift.isChecked())
            # noinspection PyUnresolvedReferences
            self.auto_shift.toggled.connect(self.auto_shift_ms.setEnabled)

        # QSpinBox's step applies to the arrows only; a typed 205 would stay on
        # screen while values() saves 200. Snap the field itself when editing ends,
        # so what the user sees is what is saved.
        for box in (self.tapping, self.flow_tap, self.auto_shift_ms):
            # noinspection PyUnresolvedReferences
            box.editingFinished.connect(lambda b=box: b.setValue(self._snap(b.value())))

        form = QFormLayout()
        form.addRow(_("Tapping term:"), self.tapping)
        form.addRow(_("Flow Tap term:"), self.flow_tap)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel
                                   | QDialogButtonBox.RestoreDefaults)

        style_button_box(buttons)
        # noinspection PyUnresolvedReferences
        buttons.accepted.connect(self.accept)
        # noinspection PyUnresolvedReferences
        buttons.rejected.connect(self.reject)
        # noinspection PyUnresolvedReferences
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self.restore_defaults)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        auto_intro = WrapLabel(_(_AUTO_SHIFT_INTRO))
        layout.addSpacing(8)
        layout.addWidget(auto_intro)
        auto_form = QFormLayout()
        auto_form.addRow(self.auto_shift)
        auto_form.addRow(_("Auto Shift timeout:"), self.auto_shift_ms)
        layout.addLayout(auto_form)
        layout.addWidget(buttons)


    def restore_defaults(self):
        self.tapping.setValue(TapTerms.DEFAULT_TAPPING_MS)
        if self.flow_tap.isEnabled():
            self.flow_tap.setValue(TapTerms.DEFAULT_FLOW_TAP_MS)
        if self.auto_shift_available:
            self.auto_shift.setChecked(False)
            self.auto_shift_ms.setValue(TapTerms.DEFAULT_AUTO_SHIFT_MS)

    @staticmethod
    def _snap(value):
        """A typed value is not forced onto the 10 ms grid by QSpinBox; the
        firmware NACKs anything off it, so round to the nearest step."""
        step = TapTerms.STEP_MS
        return int(round(value / step)) * step

    def values(self):
        """(tapping_term, flow_tap_term) in ms; flow_tap_term is None when the
        firmware has no Flow Tap, so the stored value is left unchanged."""
        flow = self._snap(self.flow_tap.value()) if self.flow_tap.isEnabled() else None
        return self._snap(self.tapping.value()), flow

    def auto_shift_values(self):
        """(on, timeout_ms), or (None, None) when the firmware has no Auto Shift,
        so the stored values are left unchanged. The timeout is returned even
        while Auto Shift is off, so the keyboard keeps it for the next time."""
        if not self.auto_shift_available:
            return None, None
        return self.auto_shift.isChecked(), self._snap(self.auto_shift_ms.value())
