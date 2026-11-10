"""Tray > "Tap-Hold Timing…": the tapping term and the Flow Tap term (cmd 44, v29+).

The values are stored on the keyboard, not in settings.yaml, so the dialog reads
them from the device when it opens and writes them back on OK. It goes through
``core.get_tap_terms`` / ``core.set_tap_terms``, which are RPC calls in client mode.
Ranges: ``TapTerms`` in ``device/command_ids.py``.
"""

from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLabel, QSpinBox,
                             QVBoxLayout)

from polyhost.device.command_ids import TapTerms
from polyhost.gui.ui_kit import style_button_box
from polyhost.i18n import _, N_

_INTRO = N_(
    "A key with a tap and a hold action types its tap action when you release it "
    "before the tapping term, and acts as its hold action when you hold it longer.<br><br>"
    "A tap-hold key pressed within the Flow Tap term after the previous key "
    "always types its tap action, so fast typing does not trigger a modifier. "
    "0 turns Flow Tap off.<br><br>"
    "The keyboard stores both values.")


class TapTermsDialog(QDialog):
    def __init__(self, terms, parent=None):
        """``terms`` is the dict from ``core.get_tap_terms()``."""
        super().__init__(parent)
        self.setWindowTitle(_("Tap-Hold Timing"))

        intro = QLabel(_(_INTRO))
        intro.setWordWrap(True)

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

        # QSpinBox's step applies to the arrows only; a typed 205 would stay on
        # screen while values() saves 200. Snap the field itself when editing ends,
        # so what the user sees is what is saved.
        for box in (self.tapping, self.flow_tap):
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
        layout.addWidget(buttons)

    def restore_defaults(self):
        self.tapping.setValue(TapTerms.DEFAULT_TAPPING_MS)
        if self.flow_tap.isEnabled():
            self.flow_tap.setValue(TapTerms.DEFAULT_FLOW_TAP_MS)

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
