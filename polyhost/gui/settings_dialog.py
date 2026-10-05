import string
from collections import defaultdict

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QDialogButtonBox,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QSizePolicy,
    QScrollArea, QPushButton, QComboBox
)

from polyhost import i18n
from polyhost.i18n import _, _f, N_
from polyhost.services.os_theme import THEME_AUTO, THEME_DARK, THEME_LIGHT
from polyhost.services.problem_scan import LEVEL_ERRORS, LEVEL_ERRORS_AND_WARNINGS


def language_choices():
    """(value, label) pairs for `ui_language`.

    Every language is listed in its own name and never translated, so someone
    who picked a language they cannot read still finds theirs. "Automatic"
    names the language it resolves to, which answers "why is it German?".
    """
    from polyhost.gui.i18n_qt import os_ui_languages
    resolved = i18n.language(i18n.resolve(i18n.SETTING_AUTO, os_ui_languages()))
    auto = _f("Automatic ({language})", language=resolved.endonym)
    return [(i18n.SETTING_AUTO, auto)] + [(lang.code, lang.endonym) for lang in i18n.LANGUAGES]


# Settings whose value is one of a fixed set get a dropdown rather than the
# free-text fallback: `ui_theme` is the first one a normal user is expected to
# touch, and a typo there silently falls back to "auto" instead of doing what
# they asked. Each entry is (stored value, shown label); a callable is
# evaluated when the dialog opens.
CHOICES = {
    "ui_theme": ((THEME_AUTO, N_("Automatic")), (THEME_LIGHT, N_("Light")), (THEME_DARK, N_("Dark"))),
    "ui_language": language_choices,
    "problem_scan_level": ((LEVEL_ERRORS, N_("Errors")),
                           (LEVEL_ERRORS_AND_WARNINGS, N_("Errors and warnings"))),
}

# The shown name of each settings GROUP (the key's first word) and of each
# setting (the rest). They used to be derived from the key at render time,
# which nothing can extract for translation; the derivation survives only as
# the fallback for a key missing here, and a test keeps that list empty.
GROUP_LABELS = {
    "General": N_("General"),
    "brightness": N_("Brightness"), "browser": N_("Browser"), "daemon": N_("Daemon"),
    "delay": N_("Delay"), "dev": N_("Dev"), "developer": N_("Developer"),
    "fontpack": N_("Fontpack"), "generic": N_("Generic"), "hid": N_("Hid"),
    "irradiance": N_("Irradiance"), "max": N_("Max"), "problem": N_("Problem"),
    "shortcut": N_("Shortcut"), "telemetry": N_("Telemetry"), "ui": N_("Ui"),
    "unicode": N_("Unicode"), "window": N_("Window"),
}

SETTING_LABELS = {
    "unicode_send_composition_mode": N_("Send Composition Mode"),
    "brightness_set_daylight_dependent": N_("Set Daylight Dependent"),
    "brightness_allow_online_irradiance_request": N_("Allow Online Irradiance Request"),
    "brightness_allow_online_location_lookup": N_("Allow Online Location Lookup"),
    "irradiance_min": N_("Min"),
    "irradiance_max": N_("Max"),
    "irradiance_prescaler": N_("Prescaler"),
    "brightness_gamma": N_("Gamma"),
    "generic_overlays_enabled": N_("Overlays Enabled"),
    "generic_overlays_fill_gaps": N_("Overlays Fill Gaps"),
    "shortcut_icons_enabled": N_("Icons Enabled"),
    "shortcut_icon_auto_fetch": N_("Icon Auto Fetch"),
    "max_hid_message_before_delay": N_("Hid Message Before Delay"),
    "delay_time_after_max_hid_messages": N_("Time After Max Hid Messages"),
    "hid_reconnect_retries": N_("Reconnect Retries"),
    "ui_theme": N_("Theme"),
    "ui_language": N_("Language"),
    "developer_mode": N_("Mode"),
    "dev_mock_enabled": N_("Mock Enabled"),
    "dev_mock_primary": N_("Mock Primary"),
    "dev_mock_protocol": N_("Mock Protocol"),
    "dev_run_window_detection_if_not_connected_to_poly_kybd":
        N_("Run Window Detection If Not Connected To Poly Kybd"),
    "dev_win_native_set_language": N_("Win Native Set Language"),
    "dev_legacy_plaintext_relay": N_("Legacy Plaintext Relay"),
    "daemon_mode": N_("Mode"),
    "window_report_network_enabled": N_("Report Network Enabled"),
    "fontpack_auto_flash": N_("Auto Flash"),
    "fontpack_path": N_("Path"),
    "browser_url_detection": N_("Url Detection"),
    "browser_report_local_enabled": N_("Report Local Enabled"),
    "browser_report_port": N_("Report Port"),
    "browser_report_token": N_("Report Token"),
    "telemetry_enabled": N_("Enabled"),
    "telemetry_endpoint": N_("Endpoint"),
    "telemetry_install_id": N_("Install Id"),
    "problem_scan_keyboard_console": N_("Scan Keyboard Console"),
    "problem_scan_host_logs": N_("Scan Host Logs"),
    "problem_scan_level": N_("Scan Level"),
}


def split_key(full_key):
    """(group, name) of a settings key, as the dialog groups it."""
    return tuple(full_key.split("_", 1)) if "_" in full_key else ("General", full_key)


def group_label(group):
    return _(GROUP_LABELS.get(group, string.capwords(group)))


def setting_label(full_key):
    derived = string.capwords(full_key, sep="_").replace("_", " ").split(" ", 1)[-1]
    return _(SETTING_LABELS.get(full_key, derived))


def _choices_for(key):
    choices = CHOICES.get(key)
    return choices() if callable(choices) else choices


def create_editor(value, key=None):
    choices = _choices_for(key)
    if choices:
        combo = QComboBox()
        for stored, label in choices:
            # A callable's labels are final; a static table's are N_-marked.
            combo.addItem(label if callable(CHOICES.get(key)) else _(label), stored)
        index = combo.findData(str(value))
        if index < 0:
            # A value outside the list (an old or hand-edited file) is kept
            # visible rather than silently replaced by the first entry on OK.
            combo.addItem(str(value), str(value))
            index = combo.count() - 1
        combo.setCurrentIndex(index)
        return combo
    if isinstance(value, bool):
        checkbox = QCheckBox()
        checkbox.setChecked(value)
        return checkbox
    elif isinstance(value, int):
        spinbox = QSpinBox()
        # ⚠️ A spin box CLAMPS the value it is given, and OK writes the clamped
        # value back. A 10_000 cap turned browser_report_port 50164 into 10000
        # on every OK, and the browser extension lost the host. Take the full
        # int range and never start the range above a stored negative value.
        spinbox.setRange(-2_147_483_648 if value < 0 else 0, 2_147_483_647)
        spinbox.setValue(value)
        return spinbox
    elif isinstance(value, float):
        doublebox = QDoubleSpinBox()
        doublebox.setDecimals(3)
        # No clamp, as above, and room to move past a stored value in either
        # direction rather than pinning it to an end of the range.
        doublebox.setRange(min(-1e9, value * 10) if value < 0 else 0.0,
                           max(1_000.0, abs(value) * 10))
        # Default step is 1.0, which silently clamps fine-grained float settings
        # (e.g. the 0.75 brightness prescaler) to 0.0 on a single scroll/click —
        # use a small step so these stay editable to their real precision.
        doublebox.setSingleStep(0.05)
        doublebox.setValue(value)
        return doublebox
    else:  # string fallback
        line_edit = QLineEdit()
        line_edit.setText(str(value))
        return line_edit


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("PolyKybd Settings"))
        self.edit_widgets = {}
        self._all_settings = {}

    def sizeHint(self):
        return QSize(640, 480)

    def setup(self, settings_dict, developer_mode=False, reset_glyph_script=None):
        self._all_settings = dict(settings_dict)
        self._reset_glyph_script = reset_glyph_script
        # No setWindowIcon here: the dialog inherits QApplication's, which
        # IconStateManager already sets to the right mark for whichever app
        # opened it (the P for the tray app, the F for the forwarder). Pinning
        # pcolor.png put the tray app's mark on the forwarder's Settings window.

        # Outer layout
        main_layout = QVBoxLayout(self)

        title_label = QLabel(_("Some settings might need a restart to take effect."))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_contents = QWidget()
        scroll_layout = QVBoxLayout(scroll_contents)

        grouped_settings = defaultdict(dict)
        for full_key, value in settings_dict.items():
            if full_key.startswith("dev_") and not developer_mode:
                continue
            group, _name = split_key(full_key)
            grouped_settings[group][full_key] = value

        # For each group, create a QGroupBox with a form layout
        for group_name, group_items in grouped_settings.items():
            group_box = QGroupBox(group_label(group_name))
            group_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            group_layout = QFormLayout()
            group_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            group_box.setLayout(group_layout)

            for full_key, value in group_items.items():
                label = QLabel(setting_label(full_key))
                label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                widget = create_editor(value, full_key)

                field_container = QWidget()
                field_layout = QHBoxLayout()
                field_layout.setContentsMargins(0, 0, 0, 0)
                field_layout.setAlignment(Qt.AlignRight)  # Right-align the widget inside the field cell
                field_layout.addWidget(widget)
                field_container.setLayout(field_layout)

                group_layout.addRow(label, field_container)
                self.edit_widgets[full_key] = widget

            # form_wrapper_layout.addWidget(group_box)
            scroll_layout.addWidget(group_box)

        scroll_layout.addStretch()  # force groups to fill width
        scroll.setWidget(scroll_contents)
        main_layout.addWidget(scroll)

        # Glyph-script reset — a direct device action (fires immediately, not tied
        # to OK/Cancel). Only shown when a callback is provided (device present /
        # firmware v9+). Puts the keycaps back to the normal language legends.
        if self._reset_glyph_script is not None:
            reset_btn = QPushButton(_("Reset glyph script to Standard"))
            reset_btn.setToolTip(_("Turn off any fantasy/alternative script override "
                                   "and show the normal language legends again."))
            reset_btn.clicked.connect(self._reset_glyph_script)
            main_layout.addWidget(reset_btn, alignment=Qt.AlignCenter)

        # The startup ("Eden") animation replay used to sit here as a button. It
        # is a one-off demo action, not a setting — it now lives only in
        # `polyctl replay-anim`.

        # Add buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons, alignment=Qt.AlignCenter)

    def get_updated_settings(self):
        updated = dict(self._all_settings)
        for key, widget in self.edit_widgets.items():
            if isinstance(widget, QCheckBox):
                updated[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                updated[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                updated[key] = widget.value()
            elif isinstance(widget, QComboBox):
                updated[key] = widget.currentData()
            elif isinstance(widget, QLineEdit):
                updated[key] = widget.text()
        return updated
